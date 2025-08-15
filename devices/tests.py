from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from .models import Device, OSType, Command
import json

class DeviceAPITest(APITestCase):
    def setUp(self):
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        # 创建 token
        self.token = Token.objects.create(user=self.user)
        # 设置认证头
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # 创建测试 OS 类型
        self.os_type = OSType.objects.create(
            name='Test OS',
            comment='Test OS Comment'
        )
        
        # 创建测试设备
        self.device = Device.objects.create(
            name='Test Device',
            os_type='Test OS',
            ip_address='127.0.0.1',
            port=22,
            username='testuser',
            password='testpass',
            device_type='server',
            protocol='ssh'
        )
        
        # 设置 API URL
        self.device_list_url = reverse('devices_list_api')
        self.device_detail_url = reverse('devices_detail_api', kwargs={'pk': self.device.pk})
        self.device_logs_url = reverse('devices_logs_api')
        self.device_connect_url = reverse('terminal_simple', kwargs={'device_id': self.device.pk})
        self.device_disconnect_url = reverse('terminal_single')

    def test_create_device(self):
        """测试创建设备"""
        data = {
            'name': 'New Device',
            'os_type': 'New OS Type',
            'ip_address': '192.168.1.1',
            'port': 22,
            'username': 'admin',
            'password': 'admin123',
            'device_type': 'server',
            'protocol': 'ssh'
        }
        response = self.client.post(self.device_list_url, data, format='json')
        print("创建设备结果：", json.dumps(response.data, indent=4))
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Device.objects.count(), 2)
        self.assertEqual(Device.objects.get(name='New Device').ip_address, '192.168.1.1')
        self.assertEqual(Device.objects.get(name='New Device').os_type, 'New OS Type')

    def test_list_devices(self):
        """测试获取设备列表"""
        response = self.client.get(self.device_list_url)
        print("设备列表：", json.dumps(response.data, indent=4))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Test Device')

    def test_get_device_detail(self):
        """测试获取设备详情"""
        response = self.client.get(self.device_detail_url)
        print("设备详情：", json.dumps(response.data, indent=4))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Device')
        self.assertEqual(response.data['ip_address'], '127.0.0.1')

    def test_update_device(self):
        """测试更新设备"""
        data = {
            'name': 'Updated Device',
            'ip_address': '192.168.1.2'
        }
        response = self.client.put(self.device_detail_url, data, format='json')
        print("更新设备结果：", json.dumps(response.data, indent=4))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.device.refresh_from_db()
        self.assertEqual(self.device.name, 'Updated Device')
        self.assertEqual(self.device.ip_address, '192.168.1.2')

    def test_delete_device(self):
        """测试删除设备"""
        response = self.client.delete(self.device_detail_url)
        print("删除设备结果：", response.status_code)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Device.objects.count(), 0)

    def test_connect_device(self):
        """测试连接设备"""
        response = self.client.get(self.device_connect_url)
        print("连接设备结果：", response.status_code)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_disconnect_device(self):
        """测试断开设备连接"""
        response = self.client.get(self.device_disconnect_url)
        print("断开设备连接结果：", response.status_code)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_device_logs(self):
        """测试获取设备日志"""
        response = self.client.get(self.device_logs_url)
        print("设备日志：", response.status_code)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

class OSTypeAPITest(APITestCase):
    def setUp(self):
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        # 创建 token
        self.token = Token.objects.create(user=self.user)
        # 设置认证头
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # 创建测试 OS 类型
        self.os_type = OSType.objects.create(
            name='Test OS',
            comment='Test OS Comment'
        )
        
        # 设置 API URL
        self.os_type_list_url = reverse('os_types_list')
        self.os_type_detail_url = reverse('os_types_detail', kwargs={'pk': self.os_type.pk})

    def test_create_os_type(self):
        """测试创建 OS 类型"""
        data = {
            'name': 'New OS Type',
            'comment': 'New OS Type Comment'
        }
        response = self.client.post(self.os_type_list_url, data, format='json')
        print("创建 OS 类型结果：", json.dumps(response.data, indent=4))
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OSType.objects.count(), 2)
        self.assertEqual(OSType.objects.get(name='New OS Type').name, 'New OS Type')
        self.assertEqual(OSType.objects.get(name='New OS Type').comment, 'New OS Type Comment')

    def test_list_os_types(self):
        """测试获取 OS 类型列表"""
        response = self.client.get(self.os_type_list_url)
        print("OS 类型列表：", json.dumps(response.data, indent=4))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Test OS')
        self.assertEqual(response.data[0]['comment'], 'Test OS Comment')

    def test_get_os_type_detail(self):
        """测试获取 OS 类型详情"""
        response = self.client.get(self.os_type_detail_url)
        print("OS 类型详情：", json.dumps(response.data, indent=4))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test OS')
        self.assertEqual(response.data['comment'], 'Test OS Comment')

    def test_update_os_type(self):
        """测试更新 OS 类型"""
        data = {
            'name': 'Updated OS Type',
            'comment': 'Updated Comment'
        }
        response = self.client.put(self.os_type_detail_url, data, format='json')
        print("更新 OS 类型结果：", json.dumps(response.data, indent=4))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.os_type.refresh_from_db()
        self.assertEqual(self.os_type.name, 'Updated OS Type')
        self.assertEqual(self.os_type.comment, 'Updated Comment')

    def test_delete_os_type(self):
        """测试删除 OS 类型"""
        response = self.client.delete(self.os_type_detail_url)
        print("删除 OS 类型结果：", response.status_code)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(OSType.objects.count(), 0)

class CommandAPITest(APITestCase):
    def setUp(self):
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        # 创建 token
        self.token = Token.objects.create(user=self.user)
        # 设置认证头
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # 创建测试 OS 类型
        self.os_type = OSType.objects.create(
            name='Test OS',
            comment='Test OS Comment'
        )
        
        # 创建测试命令
        self.command = Command.objects.create(
            command_text='echo "Hello, World!"',
            os_type=self.os_type
        )
        
        # 设置 API URL
        self.command_list_url = reverse('commands_list_api')
        self.command_detail_url = reverse('commands_detail_api', kwargs={'pk': self.command.pk})

    def test_create_command(self):
        """测试创建命令"""
        data = {
            'command_text': 'echo "Hello, World!"',
            'os_type': self.os_type.id
        }
        response = self.client.post(self.command_list_url, data, format='json')
        print("创建命令结果：", json.dumps(response.data, indent=4))
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Command.objects.count(), 2)
        
        # 获取最新创建的命令
        new_command = Command.objects.latest('id')
        self.assertEqual(new_command.command_text, 'echo "Hello, World!"')
        self.assertEqual(new_command.os_type, self.os_type)

    def test_list_commands(self):
        """测试获取命令列表"""
        response = self.client.get(self.command_list_url)
        print("命令列表：", json.dumps(response.data, indent=4))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['command_text'], 'echo "Hello, World!"')
        self.assertEqual(response.data[0]['os_type'], self.os_type.id)

    def test_get_command_detail(self):
        """测试获取命令详情"""
        response = self.client.get(self.command_detail_url)
        print("命令详情：", json.dumps(response.data, indent=4))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['command_text'], 'echo "Hello, World!"')
        self.assertEqual(response.data['os_type'], self.os_type.id)

    def test_update_command(self):
        """测试更新命令"""
        data = {
            'command_text': 'Updated Command',
            'os_type': self.os_type.id
        }
        response = self.client.put(self.command_detail_url, data, format='json')
        print("更新命令结果：", json.dumps(response.data, indent=4))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.command.refresh_from_db()
        self.assertEqual(self.command.command_text, 'Updated Command')
        self.assertEqual(self.command.os_type, self.os_type)

    def test_delete_command(self):
        """测试删除命令"""
        response = self.client.delete(self.command_detail_url)
        print("删除命令结果：", response.status_code)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Command.objects.count(), 0)
