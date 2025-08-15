import json
import asyncio
import os
from channels.generic.websocket import AsyncWebsocketConsumer
import paramiko
from io import StringIO
from django.conf import settings
from datetime import datetime
import re
import serial
from asgiref.sync import sync_to_async
from devices.models import Device 
import socket
#from netmiko import ConnectHandler

# terminal_simple页面websocket交互
class TerminalSimpleConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 清理之前的连接
        if hasattr(self, 'read_task') and self.read_task:
            self.read_task.cancel()
            try:
                await self.read_task
            except asyncio.CancelledError:
                pass
                
        if hasattr(self, 'channel') and self.channel:
            self.channel.close()
            
        if hasattr(self, 'ssh') and self.ssh:
            self.ssh.close()

        if hasattr(self, 'logfile_handler') and self.logfile_handler:
            self.logfile_handler.close()
            
        self.ssh = None
        self.channel = None
        self.read_task = None
        self.logfile_handler = None
        self.current_command = ""  # 用于存储当前正在拼接的命令
        self.COMMAND_BLACKLIST = ['rm -rf /', 'reboot', 'shutdown -h now','ip addr', 'vim','nano']
        
        self.device_id = self.scope['url_route']['kwargs']['device_id']
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'read_task') and self.read_task:
            self.read_task.cancel()
            try:
                await self.read_task
            except asyncio.CancelledError:
                pass
                
        if hasattr(self, 'channel') and self.channel:
            self.channel.close()
            
        if hasattr(self, 'ssh') and self.ssh:
            self.ssh.close()

        if hasattr(self, 'logfile_handler') and self.logfile_handler:
            self.logfile_handler.close()

        self.ssh = None
        self.channel = None
        self.logfile_handler = None

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            
            if data['type'] == 'auth':
                #print("SSHConsumer收到前端的SSH连接认证请求",data)
                # 获取设备信息
                device = await self.get_device(self.device_id)
                # 建立SSH连接
                self.ssh = paramiko.SSHClient()
                self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                if hasattr(device, 'ssh_key') and device.ssh_key:
                    key = paramiko.RSAKey.from_private_key(StringIO(device.ssh_key))
                    self.ssh.connect(
                        hostname=device.ip_address,
                        port=device.port,
                        username=device.username,
                        pkey=key
                    )
                else:
                    #处理交换机类设备的SSH连接请求songhz
                    if device.device_type == 'switch':
                        self.ssh.connect(
                            hostname=device.ip_address,
                            username=device.username,
                            password=device.password,
                            look_for_keys=False,
                            allow_agent=False
                        )
                    else:
                        self.ssh.connect(
                            hostname=device.ip_address,
                            port=device.port,
                            username=device.username,
                            password=device.password
                        )
                # 打开SSH通道
                self.channel = self.ssh.invoke_shell(term='xterm', width=80, height=50)
                self.channel.setblocking(0)
                
                # 启动异步读取循环
                self.read_task = asyncio.create_task(self.read_ssh_output())

                #启动日志记录
                logfile_path = os.path.join(settings.BASE_DIR,'logs/')
                timestr = datetime.now().strftime('%Y%m%d_%H%M%S')
                logfilename = 'ssh_%s_%s__%s.log'%(device.name,device.ip_address,timestr)
                logfileUrl = logfile_path+logfilename

                self.logfile_handler = open(logfileUrl, 'a')
                
                await self.send(text_data=json.dumps({
                    'type': 'status',
                    'message': 'SSH连接成功\n\r',
                    'sshid': '会话id:%s'%timestr
                }))
                
            elif data['type'] == 'input':
                if self.channel:
                    self.channel.send(data['data'])
                #增加命令黑名单
                '''
                char = data['data']
                self.current_command += char
                if char in ['\n','\r']:  # 遇到换行符，认为命令输入结束
                    command = self.current_command.strip()
                    print('当前执行的命令',self.current_command,'@@@',command)
                    self.current_command = ""  # 清空当前命令存储

                    # 检查命令是否在黑名单中
                    if command in self.COMMAND_BLACKLIST:
                        
                        await self.send(text_data=json.dumps({
                            'type': 'error',
                            'message': f'\n\r命令 "{command}" 在黑名单中，禁止执行'
                        })) 
                        self.channel.send('\x7F'*len(command))
                        self.channel.send('\n')

                else:
                    print('发送收到的前端输入给SSH',data['data'])
                    self.channel.send(data['data'])
                '''
            elif data['type'] == 'upload':
                # 文件上传处理
                sftp = self.ssh.open_sftp()
                local_path = os.path.join(settings.MEDIA_ROOT, data['filename'])
                with open(local_path, 'wb') as f:
                    f.write(data['content'].encode('utf-8'))
                sftp.put(local_path, data['remote_path'])
                sftp.close()
                os.remove(local_path)
                
                await self.send(text_data=json.dumps({
                    'type': 'status',
                    'message': f'文件上传成功: {data["remote_path"]}'
                }))
                
            elif data['type'] == 'download':
                # 文件下载处理
                sftp = self.ssh.open_sftp()
                local_path = os.path.join(settings.MEDIA_ROOT, data['filename'])
                sftp.get(data['remote_path'], local_path)
                sftp.close()
                
                with open(local_path, 'rb') as f:
                    content = f.read().decode('utf-8')
                os.remove(local_path)
                
                await self.send(text_data=json.dumps({
                    'type': 'file',
                    'filename': data['filename'],
                    'content': content
                }))
                    
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e),
                'sshid': '',
            }))

    async def get_device(self, device_id):
        # 这里需要实现从数据库获取设备信息的逻辑
        # 由于Django ORM是同步的，需要使用sync_to_async
        return await sync_to_async(Device.objects.get)(id=device_id)

    async def read_ssh_output(self):
        while True:
            await asyncio.sleep(0.1)
            if self.channel and self.channel.recv_ready():
                try:
                    raw_data = self.channel.recv(1024)
                    try:
                        data = raw_data.decode('utf-8')
                        # 清理控制字符
                        data_temp = data.replace('\r\n','\n')
                        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                        cleaned_lines = [ansi_escape.sub('', line) for line in data_temp.splitlines()]  # 去掉每一行的换行符
                        cleaned_text = '\n'.join(cleaned_lines)  # 重新组合为单个字符串
                        if self.logfile_handler:
                            self.logfile_handler.write(cleaned_text)  # 添加换行符以保持行分隔
                            self.logfile_handler.flush()
                    except UnicodeDecodeError:
                        data = raw_data.decode('utf-8', errors='replace')
                    await self.send(json.dumps({
                        'type': 'output',
                        'data': data  # 发送处理后的数据
                    }))
                except Exception as e:
                    await self.send(json.dumps({
                        'type': 'error',
                        'message': f'读取输出失败: {str(e)}'
                    }))


# 独立控制台页面websocket交互
class TerminalSingleConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        #self.terminal = None
        self.channel = None
        self.read_task = None
        self.logfile_handler = None
        self.serial_port = None  # 添加串口属性
        await self.accept()

    async def disconnect(self, close_code):
        # 关闭串口连接
        if self.serial_port:
            self.serial_port.close()
            self.serial_port = None

        # 现有的断开连接逻辑
        if hasattr(self, 'read_task') and self.read_task:
            self.read_task.cancel()
            try:
                await self.read_task
            except asyncio.CancelledError:
                pass
                
        if hasattr(self, 'channel') and self.channel:
            self.channel.close()
            
        if hasattr(self, 'ssh') and self.ssh:
            self.ssh.close()

        if hasattr(self, 'logfile_handler') and self.logfile_handler:
            self.logfile_handler.close()
    
    async def get_device(self, device_id):
        # 这里需要实现从数据库获取设备信息的逻辑
        # 由于Django ORM是同步的，需要使用sync_to_async
        
        return await sync_to_async(Device.objects.get)(id=device_id)

    async def receive(self, text_data):
        data = json.loads(text_data)
        
        if data['type'] == 'auth':
            protocol = data.get('protocol', 'ssh')  # 默认为ssh
            
            if protocol == 'serial':
                await self.handle_serial_connection(data)
            elif protocol == 'ssh':
                await self.handle_ssh_connection(data)
                
        elif data['type'] == 'input':
            if self.serial_port:
                # 处理串口输入
                try:
                    await self.handle_serial_input(data['data'])
                except Exception as e:
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
                    await self.send(json.dumps({
                        'type': 'error',
                        'message': f'SSH输入错误: {str(e)}'
                    }))

    async def handle_serial_connection(self, data):
        """处理串口连接"""
        try:
            # 配置串口参数
            port = data['port']
            baudrate = int(data['baudRate'])
            databits = int(data['dataBits'])
            parity = data['parity']

            # 创建串口连接
            self.serial_port = await sync_to_async(serial.Serial)(
                port=port,
                baudrate=baudrate,
                bytesize=databits,
                parity=parity,
                timeout=1
            )

            if not self.serial_port.is_open:
                await sync_to_async(self.serial_port.open)()

            # 创建日志文件
            current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
            # 处理串口名称，移除斜杠
            safe_port_name = port.replace('/', '-')
            log_filename = f"serial_{safe_port_name}__{current_time}.log"
            
            # 使用 settings.BASE_DIR 获取项目根目录
            log_dir = os.path.join(settings.BASE_DIR, 'logs')
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            log_path = os.path.join(log_dir, log_filename)
            self.logfile_handler = open(log_path, 'a', encoding='utf-8')

            # 发送连接成功消息
            await self.send(json.dumps({
                'type': 'status',
                'message': '连接成功',
                'info': f'Serial-{port}',
                'logfilename': log_filename
            }))
            # 启动串口读取循环
            self.read_task = asyncio.create_task(self.read_serial())
            
            # 连接成功后发送回车键
            await self.handle_serial_input('\n')

        except Exception as e:
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

    async def read_serial(self):
        """串口数据读取循环"""
        try:
            while self.serial_port and self.serial_port.is_open:
                if await sync_to_async(lambda: self.serial_port.in_waiting)():
                    data = await sync_to_async(self.serial_port.read)(
                        await sync_to_async(lambda: self.serial_port.in_waiting)()
                    )
                    decoded_data = data.decode(errors='replace')  # 不去掉换行符
                    # 清理控制字符
                    data_temp = decoded_data.replace('\r\n','\n')
                    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                    cleaned_lines = [ansi_escape.sub('', line) for line in data_temp.splitlines()]  # 去掉每一行的换行符
                    cleaned_text = '\n'.join(cleaned_lines)  # 重新组合为单个字符串
                    
                    # 写入日志文件
                    if self.logfile_handler:
                        self.logfile_handler.write(cleaned_text)  # 添加换行符以保持行分隔
                        self.logfile_handler.flush()
                    
                    # 发送数据到前端
                    await self.send(json.dumps({
                        'type': 'output',
                        'data': decoded_data
                    }))
                
                await asyncio.sleep(0.1)
                
        except Exception as e:
            await self.send(json.dumps({
                'type': 'error',
                'message': f'串口读取错误: {str(e)}'
            }))
            if self.serial_port and self.serial_port.is_open:
                await sync_to_async(self.serial_port.close)()
                self.serial_port = None

    async def handle_ssh_connection(self, data):
        """处理 SSH 连接"""
        try:
            # 获取设备信息
            device_id = data['device_id']
            ip_address = data['ip']
            username = data['username']
            password = data['password']  # 仍然需要获取密码以进行连接
            port = data.get('port', 22)
            device_type = data.get('device_type', 'switch')
            ssh_key = data.get('ssh_key', None)
            protocol = data.get('protocol', 'ssh')
            name = data.get('name', ip_address)  # 获取设备名称，默认为 IP 地址
            device = None
            if device_id:
                device = await self.get_device(device_id)
            else:
                # 使用 get_or_create_device 方法
                device = await sync_to_async(Device.get_or_create_device)(
                    name=name,
                    ip_address=ip_address,
                    username=username,
                    password=password,  # 传递密码
                    device_type=device_type,
                    port=port,
                    ssh_key=ssh_key,
                    protocol=protocol
                )

            # 继续处理 SSH 连接逻辑
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if device.device_type == 'switch':
                print("SSHConsumer判断设备类型为交换机开始连接")
                #print(device.ip_address,device.username,device.password)
                self.ssh.connect(
                    hostname=device.ip_address,
                    username=device.username,
                    password=device.password,
                    look_for_keys=False,
                    allow_agent=False
                )
            else:
                self.ssh.connect(
                    hostname=device.ip_address,
                    port=device.port,
                    username=device.username,
                    password=device.password
                )

            # 获取通道
            self.channel = self.ssh.invoke_shell(term='xterm')
            self.channel.setblocking(0)

            # 创建日志文件
            current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_filename = f"ssh_{device.username}_{device.ip_address}__{current_time}.log"
            log_path = os.path.join(settings.BASE_DIR, 'logs')
            if not os.path.exists(log_path):
                os.makedirs(log_path)
            log_file = os.path.join(log_path, log_filename)
            self.logfile_handler = open(log_file, 'a', encoding='utf-8')

            # 发送连接成功消息
            await self.send(json.dumps({
                'type': 'status',
                'message': '连接成功',
                'info': current_time,
                'logfilename': log_filename,  # 发送日志文件名
                'device_id': device.id  # 发送新创建的设备 ID
            }))

            # 启动读取任务
            self.read_task = asyncio.create_task(self.read_ssh_output())

        except Exception as e:
            await self.send(json.dumps({
                'type': 'error',
                'message': str(e)
            }))
            if hasattr(self, 'ssh'):
                self.ssh.close()

    async def handle_ssh_input(self, data):
        """处理 SSH 输入"""
        if self.channel:
            self.channel.send(data['data'])

    async def read_ssh_output(self):
        """读取 SSH 输出"""
        while True:
            await asyncio.sleep(0.1)
            if self.channel and self.channel.recv_ready():
                try:
                    raw_data = self.channel.recv(1024)
                    try:
                        data = raw_data.decode('utf-8')
                        # 记录日志
                        # 清理控制字符,如tab键
                        data_temp = data.replace('\r\n','\n')
                        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                        cleaned_lines = [ansi_escape.sub('', line) for line in data_temp.splitlines()]  # 去掉每一行的换行符
                        cleaned_text = '\n'.join(cleaned_lines)  # 重新组合为单个字符串
                        if self.logfile_handler:
                            self.logfile_handler.write(cleaned_text)  # 添加换行符以保持行分隔
                            self.logfile_handler.flush()
                    except UnicodeDecodeError:
                        data = raw_data.decode('utf-8', errors='replace')
                    await self.send(json.dumps({
                        'type': 'output',
                        'data': data  # 发送处理后的数据
                    }))
                except Exception as e:
                    await self.send(json.dumps({
                        'type': 'error',
                        'message': f'读取输出失败: {str(e)}'
                    }))
