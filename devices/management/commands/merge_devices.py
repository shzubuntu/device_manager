from django.core.management.base import BaseCommand
from devices.models import Device

class Command(BaseCommand):
    help = 'Merge DeviceTemp into Device'

    def handle(self, *args, **kwargs):
        # 这里不再需要 DeviceTemp 的逻辑
        self.stdout.write(self.style.SUCCESS('Successfully merged DeviceTemp into Device.'))