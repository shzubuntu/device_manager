from django.contrib import admin
from .models import Device

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'ip_address', 'port', 'device_type', 'created_at')
    list_filter = ('device_type', 'created_at')
    search_fields = ('name', 'ip_address')
    readonly_fields = ('created_at', 'updated_at')
