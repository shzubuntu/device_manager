from rest_framework import serializers
from .models import Device, OSType, Command

class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = '__all__'
        extra_kwargs = {
            #'password': {'write_only': True},
            'ssh_key': {'write_only': True},
        }

class OSTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OSType
        fields = '__all__'

class CommandSerializer(serializers.ModelSerializer):
    os_type_name = serializers.CharField(source='os_type.name', read_only=True)
    template_status = serializers.SerializerMethodField()
    csv_status = serializers.SerializerMethodField()

    class Meta:
        model = Command
        fields = ['id', 'command_text', 'os_type', 'os_type_name', 'comment', 'template_status', 'csv_status']

    def get_template_status(self, obj):
        """
        获取命令的模板状态
        """
        return getattr(obj, 'status', {}).get('template_status', 'not_exists')

    def get_csv_status(self, obj):
        """
        获取命令的csv状态
        """
        return getattr(obj, 'status', {}).get('csv_status', 'not_exists')

class TextFSMSerializer(serializers.Serializer):
    os_type = serializers.CharField(max_length=100)  # 操作系统类型
    command_text = serializers.CharField(max_length=100)  # 命令文本
    template_text = serializers.CharField()  # 模板文本