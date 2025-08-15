from django.urls import re_path
#from devices.consumers.ssh_consumer import TerminalSimpleConsumer,TerminalSingleConsumer
from devices.consumers.terminal import TerminalSimpleConsumer,TerminalSingleConsumer
from devices.consumers.serial_consumer import SerialTerminalConsumer
from devices.consumers.execute import InspectionConsumer, ConfigConsumer
from devices.consumers.sftp_consumer import SftpConsumer
#from devices.consumers.config import ConfigConsumer

websocket_urlpatterns = [
    # terminal_simple页面websocket交互
    re_path(r'ws/terminal_simple/(?P<device_id>\d+)/$', TerminalSimpleConsumer.as_asgi()),
    # 串口终端连接交互页面
    re_path(r'ws/serial_terminal/$', SerialTerminalConsumer.as_asgi()),
    # 巡检页面websocket交互
    re_path(r'ws/inspection/$', InspectionConsumer.as_asgi()),
    # 独立控制台页面websocket交互
    re_path(r'ws/terminal_single/$', TerminalSingleConsumer.as_asgi()),
    # 远程文件管理页面websocket交互
    re_path(r'ws/sftp/$', SftpConsumer.as_asgi()),
    # 配置下发页面websocket交互
    re_path(r'ws/config/$', ConfigConsumer.as_asgi()),
]
