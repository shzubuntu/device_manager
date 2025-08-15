import json
import asyncio
import serial
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
import logging
logger = logging.getLogger('devices.serial_consumer')
# 串口页面websocket交互
class SerialTerminalConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.serial_connection = None
        self.read_task = None
        await self.accept()

    async def disconnect(self,close_code):
        if hasattr(self, 'read_task') and self.read_task:
            self.read_task.cancel()
            try:
                await self.read_task
            except asyncio.CancelledError:
                pass

        if hasattr(self, 'serial_connection') and self.serial_connection:
            self.serial_connection.close()

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)

            if data['type'] == 'auth':
                # Get connection parameters from frontend
                port = data.get('port')
                baudrate = int(data.get('baudrate', 9600))

                # Establish serial connection
                try:
                    logger.info(f'尝试连接串口{port}，波特率{baudrate}')
                    self.serial_connection = serial.Serial(
                        port=port,
                        baudrate=baudrate,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE,
                        bytesize=serial.EIGHTBITS,
                        timeout=1
                    )
                    # 检查是否需要输入密码
                    if self.serial_connection.in_waiting > 0:
                        response = self.serial_connection.readline().decode('utf-8')
                        if 'password' in response.lower():
                            logger.info(f'串口{port}需要密码')
                            # 需要输入密码，发送消息给前端
                            await self.send(text_data=json.dumps({
                                'type': 'prompt_password',
                                'message': '请输入串口连接密码'
                            }))
                        else:
                            # 不需要输入密码，正常处理
                            self.read_task = asyncio.create_task(self.read_serial_output())
                            logger.info(f'串口{port}不需要密码,连接成功')
                            await self.send(text_data=json.dumps({
                                'type': 'status',
                                #'message': 'Serial连接成功\n\r',
                                'message': '连接成功',
                            }))
                    else:
                        # 不需要输入密码，正常处理
                        self.read_task = asyncio.create_task(self.read_serial_output())
                        logger.info(f'串口{port}不需要密码,连接成功')
                        await self.send(text_data=json.dumps({
                            'type': 'status',
                            #'message': 'Serial连接成功\n\r',
                            'message': '连接成功',
                        }))
                        if self.serial_connection:
                            self.serial_connection.write('\n'.encode())

                except Exception as e:
                    raise ConnectionError(f'Serial连接失败: {str(e)}')

            elif data['type'] == 'serial_password':
                logger.info(f'收到串口密码****')
                # 处理前端发送的串口密码
                password = data.get('password')
                if password:
                    self.serial_connection.write(password.encode('utf-8') + b'\n')
                    # 继续处理后续操作
                    self.read_task = asyncio.create_task(self.read_serial_output())
                    logger.info(f'串口{port}密码输入成功,已连接')
                    await self.send(text_data=json.dumps({
                        'type': 'status',
                        'message': 'Serial连接成功\n\r',
                    }))
            elif data['type'] == 'input':
                if self.serial_connection:
                    self.serial_connection.write(data['data'].encode())
            #关闭串口连接
            elif data['type'] == 'Serial_disconnect':
                logger.info(f'收到关闭串口请求')
                if self.serial_connection:
                    self.serial_connection.close()
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                   'message': '无效的消息类型'
                }))
        except Exception as e:
            logger.error(f'串口页面websocket交互异常：{str(e)}')
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    async def read_serial_output(self):
        while True:
            await asyncio.sleep(0.1)
            if self.serial_connection and self.serial_connection.in_waiting:
                try:
                    raw_data = self.serial_connection.read(self.serial_connection.in_waiting)
                    try:
                        data = raw_data.decode('utf-8')
                    except UnicodeDecodeError:
                        data = raw_data.decode('utf-8', errors='replace')

                    await self.send(text_data=json.dumps({
                        'type': 'output',
                        'data': data
                    }))
                except Exception as e:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': f'读取输出失败: {str(e)}'
                    }))
