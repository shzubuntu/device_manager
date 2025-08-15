from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from io import StringIO
from datetime import datetime
import os
import paramiko
import asyncio
import re
import json
import serial
import socket
from devices.models import Device
import logging
logger = logging.getLogger('devices.terminal')
# 新增基类（放在原有类上方）
class BaseTerminalConsumer(AsyncWebsocketConsumer):
    ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    # 公共属性初始化
    async def base_connect(self):
        self.ssh = None
        self.channel = None
        self.read_task = None
        self.logfile_handler = None
        self.serial_port = None
        self.current_command = ""
        #self.COMMAND_BLACKLIST = ['rm -rf /', 'reboot', 'shutdown -h now','ip addr', 'vim','nano']
        self.COMMAND_BLACKLIST = []

    # 公共SSH连接逻辑
    async def connect_ssh(self, device:dict, timeout=10):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        connect_args = {
            'hostname': device['ip_address'],
            'port': device['port'],
            'username': device['username'],
            'timeout': timeout
        }
        logger.info(f'尝试连接设备{device["username"]}@{device["ip_address"]}:{device["port"]}')

        if 'ssh_key' in device and device['ssh_key']:
            connect_args['pkey'] = paramiko.RSAKey.from_private_key(StringIO(device['ssh_key']))
        else:
            connect_args['password'] = device['password']
            if device['device_type'] == 'switch':
                connect_args.update({'look_for_keys': False, 'allow_agent': False})

        self.ssh.connect(**connect_args)
        logger.info(f'设备{device["username"]}@{device["ip_address"]}:{device["port"]}连接成功')
        return self.ssh.invoke_shell(term='xterm')
    
    # 改进3：优化资源清理逻辑
    async def base_disconnect(self, close_code):
        # 统一清理顺序和方式
        cleanup_order = [
            ('read_task', self._cancel_task),
            ('channel', self._close_channel),
            ('ssh', self._close_ssh),
            ('logfile_handler', self._close_logfile),
            ('serial_port', self._close_serial)
        ]

        for attr, cleaner in cleanup_order:
            if hasattr(self, attr) and getattr(self, attr):
                try:
                    await cleaner(getattr(self, attr))
                except Exception as e:
                    print(f"清理 {attr} 时出错: {str(e)}")
                setattr(self, attr, None)
    # 公共日志处理
    def create_logfile(self, prefix, device:dict, port=None):
        timestr = datetime.now().strftime('%Y%m%d_%H%M%S')
        #log_dir = os.path.join(settings.BASE_DIR, 'logs')
        log_dir = settings.DIR_INFO['LOG_DIR']
        device_name = device.get('name','temp')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        if port:
            safe_port = port.replace('/', '-')
            log_name = f"{prefix}_{safe_port}__{timestr}.log"
        else:
            log_name = f"{prefix}_{device_name}_{device['ip_address']}__{timestr}.log"

        log_path = os.path.join(log_dir, log_name)
        return open(log_path, 'a'), log_name
    # 新增通用日志写入方法
    def write_log(self, data):
        if self.logfile_handler:
            cleaned_data = self.clean_control_chars(data)
            cleaned_data = cleaned_data.replace('\x07', '')  # 去除响铃字符
            self.logfile_handler.write(cleaned_data)
            self.logfile_handler.flush()
    # 改进1：增加通用文件传输方法
    async def handle_file_transfer(self, data, operation_type):
        sftp = None
        try:
            loop = asyncio.get_event_loop()
            sftp = self.ssh.open_sftp()
            local_path = os.path.join(settings.MEDIA_ROOT, data['filename'])

            if operation_type == 'upload':
                logger.info(f'尝试上传文件{local_path}到{data["remote_path"]}')
                # 异步执行文件写入
                await loop.run_in_executor(None, lambda: 
                    open(local_path, 'wb').write(data['content'].encode('utf-8')))
                await loop.run_in_executor(None, sftp.put, local_path, data['remote_path'])
            else:
                logger.info(f'尝试下载文件{data["remote_path"]}到{local_path}')
                await loop.run_in_executor(None, sftp.get, data['remote_path'], local_path)
                content = await loop.run_in_executor(None, 
                    lambda: open(local_path, 'rb').read().decode('utf-8'))

            # 异步清理临时文件
            await loop.run_in_executor(None, os.remove, local_path)
            return content if operation_type == 'download' else f'文件上传成功: {data["remote_path"]}'
        
        except Exception as e:
            logger.error(f'文件传输错误: {str(e)}')
            raise Exception(f'文件传输错误: {str(e)}')
        finally:
            if sftp:
                logger.info('关闭SFTP连接')
                sftp.close()

    # 改进2：统一控制字符清理逻辑
    def clean_control_chars(self, data):
        return self.ANSI_ESCAPE.sub('', data.replace('\r\n', '\n'))

    async def _cancel_task(self, task):
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def _close_channel(self, channel):
        channel.close()

    def _close_ssh(self, ssh):
        logger.info('关闭SSH连接')
        ssh.close()

    def _close_logfile(self, handler):
        handler.close()

    async def _close_serial(self, serial_port):
        if serial_port.is_open:
            logger.info('关闭串口连接')
            await sync_to_async(serial_port.close)()
    # 在基类中添加统一错误处理
    async def send_error(self, error_type, message, sshid=''):
        """统一错误消息发送"""
        logger.error(f'Error [{error_type}]: {message}')
        await self.send(text_data=json.dumps({
            'type': 'error',
            'subtype': error_type,
            'message': message,
            'sshid': sshid
        }))

    async def send_status(self, message, **kwargs):
        """统一状态消息发送"""
        response = {
            'type': 'status',
            'message': message
        }
        response.update(kwargs)
        await self.send(text_data=json.dumps(response))

    async def send_output(self, data):
        """统一输出数据发送方法"""
        await self.send(text_data=json.dumps({
            'type': 'output',
            'data': data
        }))
    async def send_alert(self, data):
        """统一输出告警信息发送方法"""
        logger.info(f'Alert: {data}')
        await self.send(text_data=json.dumps({
            'type': 'security',
            'data': data
        }))
    # 新增文件发送方法
    async def send_file(self, filename, content):
        """统一文件发送方法"""
        logger.info(f'发送文件{filename}')
        await self.send(text_data=json.dumps({
            'type': 'file',
            'filename': filename,
            'content': content
        }))
    async def handle_ssh_input(self, data):
        """处理SSH输入数据"""
        try:
            #await sync_to_async(self.channel.send)(data['data'])
            #"""
            # 命令黑名单检测逻辑（与 TerminalSimpleConsumer 保持一致）
            char = data['data']
            self.current_command += char
            if char in ['\n', '\r']:  # 命令结束符检测
                command = self.current_command.strip()
                self.current_command = ""
                if command in self.COMMAND_BLACKLIST:
                    logger.warning(f'禁止执行黑名单命令：%s'%command)
                    await self.send_alert(f'\n\r禁止执行黑名单命令：%s\n'%command)
                    # 发送退格字符清除命令
                    await sync_to_async(self.channel.send)('\x7F' * len(command))
                    await sync_to_async(self.channel.send)('\n')
                else:
                    await sync_to_async(self.channel.send)(data['data'])
            else:
                await sync_to_async(self.channel.send)(data['data'])
            #"""   
        except Exception as e:
            await self.send_error(
                'ssh_input', 
                f'SSH输入失败: {str(e)}', 
                sshid=getattr(self, 'sshid', '')
            )
            raise
    # 优化SSH输出读取
    async def read_ssh_output(self):
        while True:
            await asyncio.sleep(0.1)
            if self.channel and self.channel.recv_ready():
                try:
                    raw_data = self.channel.recv(1024)
                    try:
                        data = raw_data.decode('utf-8')
                        self.write_log(data)  # 使用通用日志写入方法
                    except UnicodeDecodeError:
                        data = raw_data.decode('utf-8', errors='replace')
                    
                    await self.send_output(data)
                except Exception as e:
                    await self.send_error('ssh_read', f'读取输出失败: {str(e)}')
    async def handle_ssh_connection(self, data):
        """处理SSH连接请求"""
        try:
            self.channel = await self.connect_ssh(data)
            self.channel.setblocking(0)
            # 使用基类方法创建日志文件
            self.logfile_handler, log_name = self.create_logfile("ssh", data)
            # 启动SSH输出读取任务
            self.read_task = asyncio.create_task(self.read_ssh_output())
            await self.send_status(
                'SSH_CONNECTED',
                sshid=f'会话id:{log_name.split("__")[-1].replace(".log","")}',
                info= f'{log_name.split("__")[-1].replace(".log","")}',
                logfilename=log_name,  # 发送日志文件名
            )
        except ObjectDoesNotExist:
            await self.send_error('auth', '设备不存在', sshid='')
        except Exception as e:
            await self.send_error('ssh_connect', f'SSH连接1失败: {str(e)}', sshid='')
            if self.channel:
                self._close_channel(self.channel)
                self.channel = None
    async def send_initial_break(self):
        """发送初始化中断信号（可被子类重写）"""
        pass
    async def get_device(self, device_id):
        # 这里需要实现从数据库获取设备信息的逻辑
        # 由于Django ORM是同步的，需要使用sync_to_async
        return await sync_to_async(Device.objects.get)(id=device_id)
# 修改原有类继承基类（替换原有类定义）
class TerminalSimpleConsumer(BaseTerminalConsumer):
    async def connect(self):
        await self.base_connect()
        self.device_id = self.scope['url_route']['kwargs']['device_id']
        await self.accept()

    async def disconnect(self, close_code):
        await self.base_disconnect(close_code)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data['type'] == 'auth':
                device = await self.get_device(self.device_id)
                #将device转换成字典
                device = device.__dict__
                # 使用基类的SSH连接方法
                self.channel = await self.connect_ssh(device)
                self.channel.setblocking(0)  # 保持非阻塞设置
                
                # 使用基类日志创建方法
                self.logfile_handler, log_name = self.create_logfile("ssh", device=device)
                
                # 启动异步读取循环（需要将 read_ssh_output 移至基类）
                self.read_task = asyncio.create_task(self.read_ssh_output())
                
                # 发送连接成功消息
                logger.info(f'会话id:{log_name.split("__")[-1].replace(".log","")}')
                await self.send(text_data=json.dumps({
                    'type': 'status',
                    'message': 'SSH连接成功\n\r',
                    'sshid': f'会话id:{log_name.split("__")[-1].replace(".log","")}'
                }))
                
            elif data['type'] == 'input':
                if self.channel:
                    await self.handle_ssh_input(data)
            elif data['type'] in ['upload', 'download']:
                try:
                    result = await self.handle_file_transfer(data, data['type'])
                    if data['type'] == 'upload':
                        await self.send_status(
                            f'文件上传成功: {data["remote_path"]}',
                            operation=data['type']
                        )
                    else:
                        await self.send_file(data['filename'], result)
                except Exception as e:
                    await self.send_error('file_transfer', str(e))
                    
        except Exception as e:
            await self.send_error('system', str(e), sshid=getattr(self, 'sshid', ''))
            

# 独立控制台页面继承基类
class TerminalSingleConsumer(BaseTerminalConsumer):
    async def connect(self):
        await self.base_connect()
        await self.accept()

    async def disconnect(self, close_code):
        await self.base_disconnect(close_code)

    async def receive(self, text_data):
        data = json.loads(text_data)
        
        if data['type'] == 'auth':
            protocol = data.get('protocol', 'ssh')  # 默认为ssh
            
            if protocol == 'serial':
                logger.info(f'收到串口连接请求:{data}')
                await self.handle_serial_connection(data)
            elif protocol == 'ssh':
                logger.info(f'收到SSH连接请求:{data}')
                await self.handle_ssh_connection(data)
                
        elif data['type'] == 'input':
            if self.serial_port:
                # 处理串口输入
                try:
                    await self.handle_serial_input(data['data'])
                except Exception as e:
                    logger.error(f'串口写入错误: {str(e)}')
                    await self.send(json.dumps({
                        'type': 'error',
                        'message': f'串口写入错误: {str(e)}'
                    }))
            else:
                # 现有的SSH输入处理
                try:
                    if self.channel:
                        await self.handle_ssh_input(data)
                except socket.error as e:
                    await self.send(json.dumps({
                        'type': 'status',
                        'message': 'SSH_CLOSED'
                    }))
                except Exception as e:
                    logger.error(f'SSH输入错误: {str(e)}')
                    await self.send(json.dumps({
                        'type': 'error',
                        'message': f'SSH输入错误: {str(e)}'
                    }))
    async def send_initial_break(self):
        """发送串口连接后的初始化回车"""
        await self.handle_serial_input('\n')

    async def handle_serial_connection(self, data):
        """处理串口连接"""
        try:
            # 配置串口参数
            port = data['port']
            baudrate = int(data['baudRate'])
            databits = int(data['dataBits'])
            parity = data['parity']

            # 创建串口连接
             # 使用异步执行器创建串口连接
            self.serial_port = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    bytesize=databits,
                    parity=parity,
                    timeout=1
                )
            )
            logger.info(f'串口{port}连接成功')
            if not self.serial_port.is_open:
                await sync_to_async(self.serial_port.open)()

            # 使用基类方法创建日志文件
            self.logfile_handler, log_filename = self.create_logfile("serial", port=port)
            
            # 发送连接成功消息
            # 使用统一状态发送方法
            await self.send_status(
                '连接成功',
                info=f'Serial-{port}',
                logfilename=log_filename
            )
            # 启动串口读取循环
            self.read_task = asyncio.create_task(self.read_serial_output())
            
            # 连接成功后发送回车键
            await self.send_initial_break()

        except Exception as e:
            logger.error(f'串口连接失败: {str(e)}')
            await self.send(json.dumps({
                'type': 'error',
                'message': f'串口连接错误: {str(e)}'
            }))
            if self.serial_port and self.serial_port.is_open:
                await sync_to_async(self.serial_port.close)()
                self.serial_port = None

    async def handle_serial_input(self, data):
        """处理串口输入数据"""
        if self.serial_port and self.serial_port.is_open:
            await sync_to_async(self.serial_port.write)(data.encode())

    async def read_serial_output(self):
        """串口数据读取循环"""
        try:
            while self.serial_port and self.serial_port.is_open:
                if await sync_to_async(lambda: self.serial_port.in_waiting)():
                    data = await sync_to_async(self.serial_port.read)(
                        await sync_to_async(lambda: self.serial_port.in_waiting)()
                    )
                    decoded_data = data.decode(errors='replace')
                    self.write_log(decoded_data)  # 使用基类日志方法
                    await self.send_output(decoded_data)
                
                await asyncio.sleep(0.1)
                
        except Exception as e:
            await self.send_error('serial_read', str(e))
            if self.serial_port:
                await self._close_serial(self.serial_port)
