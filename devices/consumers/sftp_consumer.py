import json
import os
from channels.generic.websocket import AsyncWebsocketConsumer
import paramiko
from io import StringIO
from django.conf import settings
from pathlib import Path
import logging

logger = logging.getLogger('devices.sftp_consumer')

# 远程文件管理页面websocket交互
class SftpConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        logger.info("SFTPConsumer建立连接sftp")
        await self.accept()
        self.local_base = Path.home()
        self.remote_ssh = None
        self.remote_sftp = None

    async def disconnect(self, close_code):
        if self.remote_sftp:
            self.remote_sftp.close()
        if self.remote_ssh:
            self.remote_ssh.close()

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            logger.info(f"收到前台的信息{json.dumps(data,indent=2)}")
            
            if data['type'] == 'init_remote':
                # 初始化远程连接
                device = await self.get_device(data['device_id'])
                self.remote_ssh = paramiko.SSHClient()
                self.remote_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                if device.ssh_key:
                    key = paramiko.RSAKey.from_private_key(StringIO(device.ssh_key))
                    self.remote_ssh.connect(
                        hostname=device.ip_address,
                        port=device.port,
                        username=device.username,
                        pkey=key
                    )
                else:
                    #处理交换机类设备的SSH连接请求
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
                
                self.remote_sftp = self.remote_ssh.open_sftp()
                
                await self.send(text_data=json.dumps({
                    'type': 'status',
                    'message': '远程连接成功\n\r'
                }))
            
            elif data['type'] == 'list_dir':
                is_local = data.get('is_local', True)
                path = data.get('path', '')
                
                if is_local:
                    base = self.local_base
                    target = base / path
                    
                    if not target.exists():
                        logger.error(f"Directory not found: {target}")
                        raise FileNotFoundError(f"Directory not found: {target}")
                    
                    if not target.is_dir():
                        logger.error(f"Not a directory: {target}")
                        raise NotADirectoryError(f"Not a directory: {target}")
                    
                    items = []
                    for item in target.iterdir():
                        items.append({
                            'name': item.name,
                            'is_dir': item.is_dir(),
                            'size': item.stat().st_size if item.is_file() else 0
                        })
                else:
                    if not self.remote_sftp:
                        logger.error("Remote connection not established")
                        raise ConnectionError("Remote connection not established")
                    
                    try:
                        items = []
                        for item in self.remote_sftp.listdir(path):
                            item_path = f"{path}/{item}" if path else item
                            stat = self.remote_sftp.stat(item_path)
                            items.append({
                                'name': item,
                                'is_dir': stat.st_mode & 0o40000 != 0,
                                'size': stat.st_size
                            })
                    except IOError as e:
                        logger.error(f"Remote directory error: {str(e)}")
                        raise FileNotFoundError(f"Remote directory error: {str(e)}")
                
                # 规范化路径显示
                if is_local:
                    normalized_path = os.path.normpath(path)
                else:
                    # 对于远程路径，先转换为绝对路径再规范化
                    if not path:
                        path = '.'
                    try:
                        normalized_path = os.path.normpath(self.remote_sftp.normalize(path))
                    except:
                        normalized_path = os.path.normpath(path)
                
                await self.send(text_data=json.dumps({
                    'type': 'dir_list',
                    'items': items,
                    'current_path': normalized_path
                }))
                
            elif data['type'] == 'change_dir':
                is_local = data.get('is_local', True)
                path = data.get('path', '')
                
                if is_local:
                    base = self.local_base
                    target = base / path
                    
                    if not target.exists():
                        logger.error(f"Directory not found: {target}")
                        raise FileNotFoundError(f"Directory not found: {target}")
                    
                    if not target.is_dir():
                        logger.error(f"Not a directory: {target}")
                        raise NotADirectoryError(f"Not a directory: {target}")
                else:
                    if not self.remote_sftp:
                        logger.error("Remote connection not established")
                        raise ConnectionError("Remote connection not established")
                    
                    try:
                        stat = self.remote_sftp.stat(path)
                        if not stat.st_mode & 0o40000:
                            logger.error(f"Not a directory: {path}")
                            raise NotADirectoryError(f"Not a directory: {path}")
                    except IOError as e:
                        logger.error(f"Remote directory error: {str(e)}")
                        raise FileNotFoundError(f"Remote directory error: {str(e)}")
                
                # 规范化路径显示
                if is_local:
                    normalized_path = os.path.normpath(path)
                else:
                    # 对于远程路径，先转换为绝对路径再规范化
                    if not path:
                        path = '.'
                    try:
                        normalized_path = os.path.normpath(self.remote_sftp.normalize(path))
                    except:
                        normalized_path = os.path.normpath(path)
                
                await self.send(text_data=json.dumps({
                    'type': 'dir_changed',
                    'current_path': normalized_path
                }))
            #收到下载消息进行下载 songhz
            elif data['type'] == 'download':
                local_path = os.path.join(settings.BASE_DIR, 'downloads/')
                remote_path = data.get('remote_path')
                local_path = data.get('local_path')
                filename = data.get('filename')
                remote_file = remote_path+'/'+filename
                local_file = local_path+'/'+filename
                logger.info(f"收到前台的下载请求{remote_path},{local_path},{filename}")

                #下载文件到本地
                if os.path.exists(local_file):
                    await self.send(text_data=json.dumps({
                        'type': 'output',
                        'message': '本地文件%s已存在'%filename
                    }))
                else:
                    if self.remote_sftp:
                        logger.info('sftp连接正常,开始下载') 
                        self.remote_sftp.get(remote_file, local_file)
                        logger.info('下载完成') 
                        await self.send(text_data=json.dumps({
                            'type': 'output',
                            'message': '文件%s已下载到本地目录%s'%(filename ,local_path)
                        }))
                    else:
                        logger.error(f'self.remote_ssh={self.remote_ssh}')
                        logger.error(f'self.remote_sftp={self.remote_sftp}')
                        await self.send(text_data=json.dumps({
                            'type': 'output',
                            'message': 'sftp连接异常，下载失败'
                        }))
                
        except Exception as e:
            logger.error(f'下载文件异常：{str(e)}')
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))