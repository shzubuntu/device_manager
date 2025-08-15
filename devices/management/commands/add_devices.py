#!/usr/bin/python
#Author: songhz
#Time: 2025-02-22 16:26:18
#Name: add_devices.py
#Version: V1.0
from django.core.management.base import BaseCommand
from devices.models import Device, OSType
class Command(BaseCommand):
    help = 'Add 31 switch devices to the database'
    def handle(self, *args, **kwargs):
# 确保操作系统类型存在
        os_type, created = OSType.objects.get_or_create(name='huawei_yunshan')
# 批量添加设备
        devices = []
        for i in range(1, 32):  # 生成 31 个设备
            ip_address = f'172.18.110.{i}'
            device = Device(
                name=f'TY_{i}',
                ip_address=ip_address,
                port=22,
                username='monitor',
                password='Wlyw@3*7=21!',
                device_type='switch',
                os_type=os_type,
                status='online',
                protocol='ssh'
            )
            devices.append(device)
        # 批量保存设备
        Device.objects.bulk_create(devices)
        self.stdout.write(self.style.SUCCESS("设备已成功添加到数据库。"))
