from django.db import models
import os
from django.conf import settings

class Device(models.Model):
    DEVICE_TYPES = (
        ('server', '服务器'),
        ('switch', '交换机'),
        ('router', '路由器'),
        ('firewall', '防火墙'),
    )
    
    PROTOCOL_TYPES = (
        ('ssh', 'SSH'),
        ('telnet', 'Telnet'),
        ('serial', 'Serial'),
    )

    name = models.CharField(max_length=100, verbose_name='设备名称')
    ip_address = models.CharField(max_length=15, verbose_name='IP地址')
    port = models.IntegerField(default=22, verbose_name='端口')
    username = models.CharField(max_length=50, verbose_name='用户名')
    password = models.CharField(max_length=50, verbose_name='密码')
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES, default='server', verbose_name='设备类型')
    os_type = models.CharField(max_length=50, blank=True, null=True, verbose_name='操作系统类型')
    status = models.CharField(max_length=10, default='online', verbose_name='状态')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    flag = models.CharField(max_length=10, default='forever')
    ssh_key = models.TextField(blank=True, null=True, verbose_name='SSH密钥')
    protocol = models.CharField(
        max_length=10, 
        choices=PROTOCOL_TYPES, 
        default='ssh', 
        verbose_name='连接协议'
    )

    def __str__(self):
        return f"{self.name} ({self.ip_address})"

    class Meta:
        verbose_name = '设备'
        verbose_name_plural = '设备'
        ordering = ['-created_at']

    @classmethod
    def get_or_create_device(cls, name, ip_address, username, password, device_type, port, ssh_key=None, protocol='ssh'):
        # 检查是否存在相同的设备（不考虑密码）
        device, created = cls.objects.get_or_create(
            ip_address=ip_address,
            username=username,
            device_type=device_type,
            port=port,
            ssh_key=ssh_key,
            protocol=protocol,
            defaults={'name': name, 'password': password}  # 使用 defaults 参数设置 name 和 password 字段
        )
        print("@@@$$$get_or_create_device",device)
        return device

class OSType(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name='操作系统类型')
    comment = models.TextField(blank=True, null=True, verbose_name='备注')

    def __str__(self):
        return self.name

class Command(models.Model):
    command_text = models.CharField(max_length=255)
    os_type = models.ForeignKey(OSType, on_delete=models.CASCADE)
    comment = models.TextField(blank=True, null=True)

    @property
    def template_exists(self):
        # 构建模板文件的路径
        template_name = f"{self.os_type.name}_{self.command_text.replace(' ', '_')}.textfsm"
        template_path = os.path.join(settings.BASE_DIR, 'devices', 'textfsm', template_name)
        return os.path.exists(template_path)

    def __str__(self):
        return self.command_text