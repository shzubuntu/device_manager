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

logger = logging.getLogger('devices.execute')

def filter_empty_strings(lst):
    """
    过滤列表中的空字符串。

    该函数接受一个列表作为输入，返回一个新的列表，其中不包含空字符串。

    参数:
    lst (list): 输入的列表，列表中的元素应为字符串。

    返回:
    list: 过滤后的列表，不包含空字符串。
    """
    return [item for item in lst if item]
    
# 巡检页面websocket交互
class BaseexecuteConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #self.device_group_name = "inspection_group"
        self.progress_tracker = {}
        self.progress_lock = Lock() # 用于保护进度更新的锁
        self.main_loop = asyncio.get_event_loop()  # 保存主事件循环引用
        # 调整线程池大小（根据实际需求）
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=20,
            thread_name_prefix="DeviceWorker-"
        )
        # 新增报告存储结构
        self.execute_type = 'inspect'
        self.reports  = {} # 存储所有报告信息
        self.execute_dir = os.path.join(settings.DIR_INFO['REPORT_DIR'],self.execute_type) # 巡检记录及报告输出目录
        self.current_report_id  = None # 当前巡检ID

    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        # 关闭线程池
        self.thread_pool.shutdown(wait=False)
        
    async def report_init(self,device_ids,command_ids,server_commands,network_commands):
        # 生成唯一巡检ID
        report_id = str(uuid.uuid4()) 
        self.current_report_id  = report_id
        # 初始化巡检目录
        self.execute_dir = os.path.join(self.execute_dir,report_id)
        if not os.path.exists( self.execute_dir):
            os.makedirs( self.execute_dir)
        # 初始化巡检报告信息
        self.reports[report_id]  = {
            'report_dir': self.execute_dir, # 报告目录
            'start_time': datetime.now().isoformat(), 
            'devices': device_ids,
            'commands': command_ids,
            "server_commands": server_commands,
            "network_commands": network_commands,
            'results': [],
            'status': 'running',
            'items':{}
        }
        logger.info(f"巡检任务初始化，巡检ID：{report_id}，巡检信息:{json.dumps(self.reports[report_id],indent=2)}")
        # 巡检任务进度跟踪
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
            if data['type'] == 'inspect.start':
                logger.info(f"收到巡检请求：{json.dumps(data,indent=2)}")
                device_ids = data['devices']
                command_ids = data['commands']
                server_commands = data['server_commands']
                network_commands = data['network_commands']
                #初始化巡检报告信息
                #await self.report_init(device_ids,command_ids,server_commands,network_commands)
                # 在这里执行巡检逻辑
                #await self.execute_commands(device_ids, command_ids,server_commands,network_commands)
                #await self.send(json.dumps({ 
                #    'type': 'report.created', 
                #    'report_id': self.current_report_id
                #}))
                await self.handle_execute(device_ids, command_ids,server_commands,network_commands)
            elif data['type'] == 'inspect.again':
                # 在历史巡检记录页面点击再次执行按钮的操作
                logger.info(f"收到历史巡检再次执行请求：{json.dumps(data,indent=2)}")
                his_inspection_id = data['id']
                # 在这里执行巡检逻辑
                history_dir = os.path.join(self.execute_dir, his_inspection_id)
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
                await self.handle_execute(device_ids, command_ids,server_commands,network_commands)
        except Exception as e:
            await self.send_error_message(str(e))
    async def handle_execute(self, device_ids, command_ids,server_commands,network_commands):
        #处理空字符串
        device_ids = filter_empty_strings(device_ids)
        command_ids = filter_empty_strings(command_ids)
        server_commands = filter_empty_strings(server_commands)
        network_commands = filter_empty_strings(network_commands)
        #初始化巡检报告信息
        await self.report_init(device_ids,command_ids,server_commands,network_commands)
        # 执行巡检
        await self.execute_commands(device_ids, command_ids,server_commands,network_commands)
        # 发送完成消息
        await self.send(json.dumps({ 
            'type': 'report.created', 
            'report_id': self.current_report_id
        }))
    async def execute_commands(self, device_ids, command_ids,server_commands,network_commands):
        try:
            logger.info(f"开始执行任务，设备列表：{device_ids}，命令列表：{command_ids}，server_commands:{server_commands},network_commands:{network_commands}")
            device_tasks = [
                asyncio.create_task(
                    self.process_device_with_pool(device_id, command_ids,server_commands,network_commands),
                    name=f"Device-{device_id}"
                ) for device_id in device_ids
            ]
            
            await asyncio.gather(*device_tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"执行错误: {str(e)}")
            await self.send_error_message(f"执行错误: {str(e)}")
        finally:
            logger.info("所有任务执行完成")
            await self.send_completion_message()
            #生成巡检记录文件json文件存放在巡检目录下
            inspect_record = {
                "device_ids":';'.join(device_ids),
                "command_ids": ';'.join(command_ids),
                "server_commands": ';'.join(server_commands),
                "network_commands": ';'.join(network_commands),
                "start_time": self.reports[self.current_report_id]['start_time'],
                "end_time": self.reports[self.current_report_id]['end_time'],
                "status": self.reports[self.current_report_id]['status'],
            }
            # 生成巡检记录文件
            with open(os.path.join(self.execute_dir,"index.json"),'w') as f:
                f.write(json.dumps(inspect_record))

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

    def _process_device_sync(self, device_id, command_ids,server_commands,network_commands):
        """同步设备处理核心"""
        try:
            # 同步获取设备凭证和命令
            device_info = self._get_device_credentials_sync(device_id)
            commands =[]
            # 同步获取命令名称
            #command_ids = [cmd for cmd in command_ids if cmd] # 删除空字符串
            if len(command_ids)>0:
                # 获取命令信息
                logger.debug(f"获取命令ID {command_ids} 的信息")
                command_info = self._get_command_credentials_sync(command_ids)
                logger.debug(f"获取命令ID {command_ids} 的信息成功{command_info}")
                # 根据os_type筛选命令
                commands = [command['command_text'] for command in command_info if command['os_type'] == device_info['os_type']]
                logger.debug(f"根据os_type筛选命令成功{commands}")
            if device_info['device_type'] in ['switch', 'router', 'firewall']:
                commands = commands + network_commands # 合并命令
                commands = list(set(commands)) # 去重
                #commands = [cmd for cmd in commands if cmd] # 删除空字符串
                self._handle_network_device_sync(device_info, commands)
            else:
                commands = commands + server_commands # 合并命令
                commands = list(set(commands)) # 去重
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
            logger.error(f"设备 {device_id} 处理失败: {str(e)}")
            raise RuntimeError(f"设备处理失败: {str(e)}")

    def _get_command_credentials_sync(self, command_ids):
        """同步获取命令名称"""
        try:
            commands = []
            cached_commands = cache.get('commands')
            if cached_commands:
                logger.debug("命令命中缓存")
                for command_id in command_ids:
                    for command in cached_commands:
                        if str(command.id) == command_id:
                            commands.append({
                                'os_type': command.os_type.name,
                                "command_text": command.command_text
                            })
            else:
                logger.debug("命令未命中缓存，从数据库获取数据")
                commands_objs = Command.objects.filter(id__in=command_ids)
                for command in commands_objs:
                    commands.append({
                        'os_type': command.os_type.name,
                        "command_text":command.command_text
                    })
            return commands
        except Command.DoesNotExist:
            logger.error(f"命令ID {command_id} 不存在")
            raise RuntimeError(f"命令ID {command_id} 不存在")
        except Exception as e:
            logger.error(f"获取命令ID {command_id} 失败: {str(e)}")
            raise RuntimeError(f"获取命令ID {command_id} 失败: {str(e)}")

    def _get_device_credentials_sync(self, device_id):
        """同步获取设备凭证"""
        try:
            device = None
            cache_devices = cache.get('devices_list')
            device_id = int(device_id)
            if cache_devices:
                for item in cache_devices:
                    if item.id == device_id:
                        logger.debug(f"设备ID {device_id} 命中缓存")
                        device = item
            else:
                device = Device.objects.get(id=device_id)
                logger.debug(f"设备ID {device_id} 未命中缓存")
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
            logger.error(f"设备ID {device_id} 不存在")
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
                session_log=os.path.join(self.execute_dir,f"{device_info['name']}__{device_info['ip']}.log")
            )
            logger.info(f"成功连接到网络设备 {device_info['name']} ({device_info['ip']}),执行命令列表：{commands}")
            # 串行执行命令
            for cmd in commands:
                logger.debug(f"{device_info['name']} 执行命令{cmd}")
                try:
                    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    output = conn.send_command(cmd)
                    end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
                    self._send_error_sync(f"{device_info['name']}命令 {cmd} 执行失败: {str(e)}")
                finally:
                    with self.progress_lock:
                        self.progress_tracker['completed_commands'] += 1
                    self.send_instant_progress_update()
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
        session_log=os.path.join(self.execute_dir,f"{device_info['name']}__{device_info['ip']}.log")
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
            #对commands进行转换，如果cmd中有__，则表示是命令集，需要读取命令集文件中的所有命令
            # for cmd in commands:
            #     if '__' in cmd:
            #         cmd_file = f"{cmd}.conf"
            #         cmd_file_path = os.path.join(settings.DIR_INFO['CONF_DIR'], 'netconf',f"{cmd_file}.conf")
            #         if os.path.exists(cmd_file_path):
            #             with open(cmd_file_path, 'r') as f:
            #                 commands.extend(f.readlines())
            logger.info(f"成功连接到通用SSH设备 {device_info['name']} ({device_info['ip']}),执行命令列表：{commands}")
            # 串行执行命令
            for cmd in commands:
                try:
                    logger.debug(f"{device_info['name']} {device_info['ip']} 执行命令{cmd}")
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
        logger.error(error_msg)
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
                report_data,
                self.execute_type
            )
            # 直接发送给当前连接
            await self.send(text_data=json.dumps({
                "type": "execute.complete", 
                "message": "所有任务执行完成",
                "report_id": report_id
            }))
            logger.info(f"所有任务执行完成，报告ID：{report_id}，报告信息:{json.dumps(report_data,indent=2)}")
    def generate_report_file(self, report_id, data,execute_type):
        #生成报告
        generator = ReportGenerator()
        # 生成html报告
        generator.generate_report_file(report_id, data,execute_type, output_format='html')
        # 清理巡检记录缓存，因为巡检记录是根据巡检报告获取的
        cache.delete('devices_inspections')
        # 清理命令缓存，生成报告的同时也生成了解析结果，与命令界面的解析结果现实有关系
        cache.delete('commands')


    async def send_error_message(self, error_msg):
        logger.error(error_msg)
        await self.send(text_data=json.dumps({
            "type": "error",
            "message": error_msg
        }))

    async def command_result(self, event):
        await self.send(text_data=json.dumps(event))

    async def progress_update(self, event):
        await self.send(text_data=json.dumps(event))

    async def inspection_complete(self, event):
        await self.send(text_data=json.dumps(event))

class InspectionConsumer(BaseexecuteConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.execute_type = 'inspect'
        self.execute_dir = os.path.join(settings.DIR_INFO['REPORT_DIR'],self.execute_type) # 巡检记录及报告输出目录

class ConfigConsumer(BaseexecuteConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  
        self.execute_type = 'config'
        self.execute_dir = os.path.join(settings.DIR_INFO['REPORT_DIR'],self.execute_type) # 巡检记录及报告输出目录
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            logger.info(f"收到前端的消息{json.dumps(data,indent=2)}")
            if data['type'] == 'config.start':
                device_ids = data['devices']
                command_ids = data['commands']
                server_commands = data['server_commands']
                network_commands = data['network_commands']
                logger.info(f"收到配置下发命令{json.dumps(data,indent=2)}")
                await self.handle_execute(device_ids, command_ids,server_commands,network_commands)
            elif data['type'] == 'config.again':
                # 在历史配置下发记录页面点击再次执行按钮的操作
                his_Config_id = data['id']
                # 在这里执行配置下发逻辑
                history_dir = os.path.join(self.execute_dir,his_Config_id)
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
                await self.handle_execute(device_ids, command_ids,server_commands,network_commands)
        except Exception as e:
            await self.send_error_message(str(e))

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
            logger.error(f"命令ID {commands_id} 不存在")
            raise RuntimeError(f"命令ID {commands_id} 不存在")
        except Exception as e:
            logger.error(f"获取命令ID {commands_id} 失败: {str(e)}")
            raise RuntimeError(f"获取命令ID {commands_id} 失败: {str(e)}")
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
                session_log=os.path.join(self.execute_dir,f"{device_info['name']}__{device_info['ip']}.log")
            )
            # 串行执行命令
            logger.info(f"开始执行网络命令{json.dumps(commands,indent=4)}")
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
        session_log=os.path.join(self.execute_dir,f"{device_info['name']}__{device_info['ip']}.log")
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
            logger.info(f"成功连接到通用SSH设备 {device_info['name']} ({device_info['ip']}),执行命令列表：{commands}")
            commands_arr = []
            for cmd_name in commands:
                commands_arr+=commands[cmd_name]
            commands = commands_arr
            # 串行执行命令
            for cmd in commands:
                try:
                    logger.debug(f"{device_info['name']} {device_info['ip']} 执行命令{cmd}")
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
    def generate_report_file(self, report_id, data,execute_type):
        #生成报告
        generator = ReportGenerator()
        # 生成html报告
        generator.generate_report_file(report_id, data,execute_type, output_format='html')
        # 清理配置下发记录缓存，因为配置下发记录是根据配置下发报告获取的
        cache.delete('devices_configs')