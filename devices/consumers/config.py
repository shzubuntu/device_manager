import json
import os
from datetime import datetime
import uuid
from threading import Lock

import asyncio
import concurrent.futures
from django.conf import settings
from django.core.cache import cache
from channels.generic.websocket import AsyncWebsocketConsumer
import paramiko
from netmiko import ConnectHandler

from devices.models import Device, Command
from devices.tools.report import ReportGenerator
import logging

logger = logging.getLogger('devices.config')

def filter_empty_strings(lst):
    """
    过滤列表中的空字符串。
    """
    return [item for item in lst if item]
    
# 配置下发页面websocket交互
class ConfigConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #self.device_group_name = "Config_group"
        self.progress_tracker = {}
        self.progress_lock = Lock() # 用于保护进度更新的锁
        self.main_loop = asyncio.get_event_loop()  # 保存主事件循环引用
        # 调整线程池大小（根据实际需求）
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=20,
            thread_name_prefix="DeviceWorker-"
        )
        # 新增报告存储结构
        self.reports  = {}  # {Config_id: {metadata, results}}
        self.Config_dir = ''
        self.current_report_id  = None

    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        # 关闭线程池
        self.thread_pool.shutdown(wait=False)
        
    async def report_init(self,device_ids,command_ids,server_commands,network_commands):
        # 生成唯一配置下发ID
        report_id = str(uuid.uuid4()) 
        self.current_report_id  = report_id
        # 初始化配置下发目录
        self.Config_dir = os.path.join(settings.DIR_INFO['REPORT_DIR'],'config',report_id)
        if not os.path.exists( self.Config_dir):
            os.makedirs( self.Config_dir)
        # 初始化配置下发报告信息
        self.reports[report_id]  = {
            'report_dir': self.Config_dir, # 报告目录
            'start_time': datetime.now().isoformat(), 
            'devices': device_ids,
            'commands': command_ids,
            "server_commands": server_commands,
            "network_commands": network_commands,
            'results': [],
            'status': 'running',
            'items':{}
        }
        # 配置下发任务进度跟踪
        self.progress_tracker = {
            'total': len(device_ids),
            'completed': 0,
            'total_commands': len(command_ids)*len(device_ids),
            'completed_commands': 0,
            'failed_commands': 0,
            'failed_devices': 0,
        }

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data['type'] == 'config.start':
                device_ids = data['devices']
                command_ids = data['commands']
                server_commands = data['server_commands']
                network_commands = data['network_commands']
                logger.info("收到配置下发命令",json.dumps(data,indent=2))
                await self.handle_config(device_ids, command_ids,server_commands,network_commands)
            elif data['type'] == 'execute':
                # 在历史配置下发记录页面点击再次执行按钮的操作
                his_Config_id = data['id']
                # 在这里执行配置下发逻辑
                history_dir = os.path.join(settings.DIR_INFO['REPORT_DIR'],'config',his_Config_id)
                history_data = os.path.join(history_dir,'index.json')
                device_ids = []
                command_ids = []
                server_commands = []
                network_commands = []
                with open(history_data, 'r', encoding='utf-8') as file:
                    # 读取并解析 JSON 文件
                    data = json.load(file)
                    device_ids = data.get('device_ids').split(';')
                    command_ids = data.get('command_ids').split(';')
                    server_commands = data.get('server_commands').split(';')
                    network_commands = data.get('network_commands').split(';')
                await self.handle_config(device_ids, command_ids,server_commands,network_commands)
        except Exception as e:
            await self.send_error_message(str(e))
    async def handle_config(self, device_ids, command_ids,server_commands,network_commands):
        #处理空字符串
        device_ids = filter_empty_strings(device_ids)
        command_ids = filter_empty_strings(command_ids)
        server_commands = filter_empty_strings(server_commands)
        network_commands = filter_empty_strings(network_commands)
        #初始化配置下发报告信息
        await self.report_init(device_ids,command_ids,server_commands,network_commands)
        # 执行配置下发
        await self.execute_commands(device_ids, command_ids,server_commands,network_commands)
        # 发送完成消息
        await self.send(json.dumps({ 
            'type': 'report.created', 
            'report_id': self.current_report_id
        }))
    async def execute_commands(self, device_ids, command_ids,server_commands,network_commands):
        try:
            device_tasks = [
                asyncio.create_task(
                    self.process_device_with_pool(device_id, command_ids,server_commands,network_commands),
                    name=f"Device-{device_id}"
                ) for device_id in device_ids
            ]
            
            await asyncio.gather(*device_tasks, return_exceptions=True)
            
        except Exception as e:
            await self.send_error_message(f"执行错误: {str(e)}")
        finally:
            await self.send_completion_message()
            #生成配置下发记录文件json文件存放在配置下发目录下
            config_record = {
                "device_ids":';'.join(device_ids),
                "command_ids": ';'.join(command_ids),
                "server_commands": ';'.join(server_commands),
                "network_commands": ';'.join(network_commands),
                "start_time": self.reports[self.current_report_id]['start_time'],
                "end_time": self.reports[self.current_report_id]['end_time'],
                "status": self.reports[self.current_report_id]['status'],
            }
            # 生成配置下发记录文件
            with open(os.path.join(self.Config_dir,"index.json"),'w') as f:
                f.write(json.dumps(config_record))

    async def process_device_with_pool(self, device_id, command_ids,server_commands,network_commands):
        """设备处理入口"""
        loop = asyncio.get_running_loop()
        try:
            await asyncio.wrap_future(
                self.thread_pool.submit(
                    self._process_device_sync,
                    device_id,
                    command_ids,
                    server_commands,
                    network_commands
                )
            )
        except Exception as e:
            error_msg = f"设备 {device_id} 处理失败: {str(e)}"
            await self.send_error_message(error_msg)

    def _process_device_sync(self, device_id, commands_ids,server_commands,network_commands):
        """同步设备处理核心"""
        try:
            # 同步获取设备凭证和命令
            device_info = self._get_device_credentials_sync(device_id)
            os_type = device_info['os_type']
            
            if len(commands_ids)>0:
                commands_info = self._get_command_credentials_sync(commands_ids)
                # 根据os_type筛选命令
                commands = {k: v for k, v in commands_info.items() if os_type in k}
            if device_info['device_type'] in ['switch', 'router', 'firewall']:
                network_commands = filter_empty_strings(network_commands)
                if len(network_commands)>0:
                    commands['temp_network_commands'] = network_commands
                self._handle_network_device_sync(device_info, commands)
            else:
                server_commands = filter_empty_strings(server_commands)
                if len(server_commands)>0:
                    commands['temp_server_commands'] = server_commands
                #commands = [cmd for cmd in commands if cmd] # 删除空字符串
                self._handle_generic_device_sync(device_info, commands)
            #填充报告中的items信息
            
            if device_info['os_type'] not in self.reports[self.current_report_id]['items']:
                self.reports[self.current_report_id]['items'][device_info['os_type']] = {
                    'commands':commands,
                    'devices':[device_info['name']]
                }
            else:
                self.reports[self.current_report_id]['items'][device_info['os_type']]['devices'].append(device_info['name'])
        except Exception as e:
            raise RuntimeError(f"设备处理失败: {str(e)}")

    def _get_command_credentials_sync(self, commands_ids):
        """
        同步获取命令名称
        {
            "hp_comware__ntp":[
                "cmd1",
                "cmd2"
            ],
            "hp_comware__clock":[
                "cmd1",
                "cmd2"
            ]
        }
        
        """
        try:
            commands_dict = {}
            for commands_id in commands_ids:
                commands = []
                config_file = os.path.join(settings.DIR_INFO['CONF_DIR'],"netconf",f"{commands_id}.conf")
                if os.path.exists(config_file):
                    with open(config_file, 'r', encoding='utf-8') as file:
                        # 读取并解析 JSON 文件
                        for line in file:
                            commands.append(line.strip())
                if commands_id not in commands_dict:
                    commands_dict[commands_id] = commands
            return commands_dict
        except Command.DoesNotExist:
            raise RuntimeError(f"命令ID {commands_id} 不存在")

    def _get_device_credentials_sync(self, device_id):
        """同步获取设备凭证"""
        try:
            device = Device.objects.get(id=device_id)
            return {
                'device_type': device.device_type,
                'os_type': device.os_type,
                'ip': device.ip_address,
                'username': device.username,
                'password': device.password,
                'port': device.port or 22,
                'name': device.name
            }
        except Device.DoesNotExist:
            raise RuntimeError(f"设备ID {device_id} 不存在")

    def _handle_network_device_sync(self, device_info, commands):
        """处理网络设备（命令串行）"""
        conn = None
        try:
            conn = ConnectHandler(
                device_type=device_info['os_type'] if 'huawei' not in device_info['os_type'] else 'huawei',
                host=device_info['ip'],
                username=device_info['username'],
                password=device_info['password'],
                port=device_info['port'],
                timeout=20,
                session_log=os.path.join(self.Config_dir,f"{device_info['name']}__{device_info['ip']}.log")
            )
            # 串行执行命令
            logger.info("开始执行网络命令",json.dumps(commands,indent=4))
            for command_id in commands:
                command_name = command_id.split('__')[1]
                cmd = commands[command_id]
                try:
                    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    output = conn.send_config_set(cmd)
                    end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    self.send_instant_result(
                        device_info['name'],
                        device_info['ip'],
                        device_info['device_type'],
                        device_info['os_type'],
                        command_id,
                        output,
                        start_time,
                        end_time
                    )
                except Exception as e:
                    with self.progress_lock:
                        self.progress_tracker['failed_commands'] += 1
                    self._send_error_sync(f"{device_info['name']}命令 {cmd} 执行失败: {str(e)}")
                finally:
                    with self.progress_lock:
                        self.progress_tracker['completed_commands'] += 1
                    self.send_instant_progress_update()
                    conn.save_config()
        except Exception as e:
            with self.progress_lock:
                self.progress_tracker['failed_devices'] += 1
            self._send_error_sync(f"网络设备连接失败: {str(e)}")
            raise RuntimeError(f"网络设备连接失败: {str(e)}")
        finally:
            with self.progress_lock:
                self.progress_tracker['completed'] += 1
            self.send_instant_progress_update()
            if conn:
                conn.disconnect()

    def _handle_generic_device_sync(self, device_info, commands):
        """处理通用SSH设备（命令串行）"""
        ssh = paramiko.SSHClient()
        session_log=os.path.join(self.Config_dir,f"{device_info['name']}__{device_info['ip']}.log")
        logfile_handler = open(session_log,'w')
        try:
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=device_info['ip'],
                port=device_info['port'],
                username=device_info['username'],
                password=device_info['password'],
                timeout=15
            )
            
            # 串行执行命令
            for cmd in commands:
                try:
                    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    stdin, stdout, stderr = ssh.exec_command(cmd)
                    end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    output = stdout.read().decode() or stderr.read().decode()
                    #记录日志
                    logfile_handler.write(f"Command: {cmd}\n{output}\n")
                    logfile_handler.flush()
                    self.send_instant_result(
                        device_info['name'],
                        device_info['ip'],
                        device_info['device_type'],
                        device_info['os_type'],
                        cmd,
                        output,
                        start_time,
                        end_time
                    )
                except Exception as e:
                    with self.progress_lock:
                        self.progress_tracker['failed_commands'] += 1
                    self._send_error_sync(f"SSH命令 {cmd} 失败: {str(e)}")
                finally:
                    with self.progress_lock:
                        self.progress_tracker['completed_commands'] += 1
                    self.send_instant_progress_update()
        except Exception as e:
            with self.progress_lock:
                self.progress_tracker['failed_devices'] += 1
            self._send_error_sync(f"SSH连接失败: {str(e)}")
            raise RuntimeError(f"SSH连接失败: {str(e)}")
        finally:
            with self.progress_lock:
                self.progress_tracker['completed'] += 1
            self.send_instant_progress_update()
            logfile_handler.close()
            if ssh:
                ssh.close()

    def _send_error_sync(self, error_msg):
        """错误信息同理"""
        asyncio.run_coroutine_threadsafe(
            self.send_error_message(error_msg),
            self.main_loop
        )
    
    def send_instant_result(self, device_name, device_ip, device_type,os_type, command, result, start_time, end_time):
        # 记录结果到报告
        if self.current_report_id: 
            self.reports[self.current_report_id]['results'].append({ 
                'device': device_name,
                'device_ip': device_ip,
                'os_type': os_type,
                'command': command,
                'result': result,
                'timestamp': datetime.now().isoformat(),
                'start_time': start_time,
                'end_time': end_time,
                'status': 'success'
            })

        # 发送即时结果
        asyncio.run_coroutine_threadsafe(
            self.command_result({
                "type": "command.result",
                "device_name": device_name,
                "device_type": device_type,
                "os_type": os_type,
                "device_ip": device_ip,
                "command": command,
                "result": result,
                'send_time':datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }),
            self.main_loop
        )
        
    def send_instant_progress_update(self):
        asyncio.run_coroutine_threadsafe(
            self.progress_update({
                "type": "progress.update",
                "total": self.progress_tracker['total'],
                "completed": self.progress_tracker['completed'],
                "total_commands": self.progress_tracker['total_commands'],
                'completed_commands': self.progress_tracker['completed_commands'],
                'send_time':datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }),
            self.main_loop
        )

    async def send_completion_message(self):
        report_id = self.current_report_id 
        if report_id in self.reports: 
            # 生成报告文件
            report_data = self.reports[report_id] 
            report_data['end_time'] = datetime.now().isoformat()
            report_data['status'] = 'completed'
            
            # 异步生成报告文件
            await asyncio.get_event_loop().run_in_executor( 
                None, 
                self.generate_report_file, 
                report_id,
                report_data
            )
            
            """
            # 发送配置下发完成消息给所有页面
            await self.channel_layer.group_send( 
                self.device_group_name, 
                {
                    "type": "Config.complete", 
                    "message": "所有设备配置下发完成",
                    "report_id": report_id
                }
            )
            """
            # 直接发送给当前连接
            await self.send(text_data=json.dumps({
                "type": "execute.complete", 
                "message": "所有设备配置下发完成",
                "report_id": report_id
            }))
    def generate_report_file(self, report_id, data):
        #生成报告
        generator = ReportGenerator()
        # 生成html报告
        generator.generate_config_report(report_id, data, output_format='html')
        # 清理配置下发记录缓存，因为配置下发记录是根据配置下发报告获取的
        cache.delete('devices_configs')


    async def send_error_message(self, error_msg):
        await self.send(text_data=json.dumps({
            "type": "error",
            "message": error_msg
        }))

    async def command_result(self, event):
        await self.send(text_data=json.dumps(event))

    async def progress_update(self, event):
        await self.send(text_data=json.dumps(event))

    async def Config_complete(self, event):
        await self.send(text_data=json.dumps(event))
