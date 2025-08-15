#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
from typing import Dict, Any, Optional

class DeviceManagerAPI:
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        初始化 API 客户端
        :param base_url: API 基础 URL
        """
        self.base_url = base_url.rstrip('/')
        self.token = None
        self.headers = {
            'Content-Type': 'application/json'
        }

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        用户登录并获取 token
        :param username: 用户名
        :param password: 密码
        :return: 包含 token 的响应数据
        """
        url = f"{self.base_url}/auth/api/token/"
        data = {
            'username': username,
            'password': password
        }
        response = requests.post(url, json=data)
        response.raise_for_status()
        self.token = response.json()['token']
        self.headers['Authorization'] = f'Token {self.token}'
        return response.json()

    # 设备管理 API
    def create_device(self, device_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建设备
        :param device_data: 设备数据
        :return: 创建的设备信息
        """
        url = f"{self.base_url}/devices/"
        response = requests.post(url, json=device_data, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_device_list(self) -> list:
        """
        获取设备列表
        :return: 设备列表
        """
        url = f"{self.base_url}/devices/"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_device_detail(self, device_id: int) -> Dict[str, Any]:
        """
        获取设备详情
        :param device_id: 设备 ID
        :return: 设备详情
        """
        url = f"{self.base_url}/devices/{device_id}/"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def update_device(self, device_id: int, device_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新设备
        :param device_id: 设备 ID
        :param device_data: 更新的设备数据
        :return: 更新后的设备信息
        """
        url = f"{self.base_url}/devices/{device_id}/"
        response = requests.put(url, json=device_data, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def delete_device(self, device_id: int) -> None:
        """
        删除设备
        :param device_id: 设备 ID
        """
        url = f"{self.base_url}/devices/{device_id}/"
        response = requests.delete(url, headers=self.headers)
        response.raise_for_status()

    # OS 类型管理 API
    def create_os_type(self, os_type_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建 OS 类型
        :param os_type_data: OS 类型数据
        :return: 创建的 OS 类型信息
        """
        url = f"{self.base_url}/os_types/"
        response = requests.post(url, json=os_type_data, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_os_type_list(self) -> list:
        """
        获取 OS 类型列表
        :return: OS 类型列表
        """
        url = f"{self.base_url}/os_types/"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_os_type_detail(self, os_type_id: int) -> Dict[str, Any]:
        """
        获取 OS 类型详情
        :param os_type_id: OS 类型 ID
        :return: OS 类型详情
        """
        url = f"{self.base_url}/os_types/{os_type_id}/"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def update_os_type(self, os_type_id: int, os_type_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新 OS 类型
        :param os_type_id: OS 类型 ID
        :param os_type_data: 更新的 OS 类型数据
        :return: 更新后的 OS 类型信息
        """
        url = f"{self.base_url}/os_types/{os_type_id}/"
        response = requests.put(url, json=os_type_data, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def delete_os_type(self, os_type_id: int) -> None:
        """
        删除 OS 类型
        :param os_type_id: OS 类型 ID
        """
        url = f"{self.base_url}/os_types/{os_type_id}/"
        response = requests.delete(url, headers=self.headers)
        response.raise_for_status()

    # 命令管理 API
    def create_command(self, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建命令
        :param command_data: 命令数据
        :return: 创建的命令信息
        """
        url = f"{self.base_url}/commands/"
        response = requests.post(url, json=command_data, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_command_list(self) -> list:
        """
        获取命令列表
        :return: 命令列表
        """
        url = f"{self.base_url}/commands/"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_command_detail(self, command_id: int) -> Dict[str, Any]:
        """
        获取命令详情
        :param command_id: 命令 ID
        :return: 命令详情
        """
        url = f"{self.base_url}/commands/{command_id}/"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def update_command(self, command_id: int, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新命令
        :param command_id: 命令 ID
        :param command_data: 更新的命令数据
        :return: 更新后的命令信息
        """
        url = f"{self.base_url}/commands/{command_id}/"
        response = requests.put(url, json=command_data, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def delete_command(self, command_id: int) -> None:
        """
        删除命令
        :param command_id: 命令 ID
        """
        url = f"{self.base_url}/commands/{command_id}/"
        response = requests.delete(url, headers=self.headers)
        response.raise_for_status()

    def get_ostype_id(self, ostypename: str) -> int:
        """
        获取 OS 类型 ID
        :param ostypename: OS 类型名称
        :return: OS 类型 ID
        """
        ostypeinfo = self.get_os_type_list()
        for ostype in ostypeinfo:
            if ostype['name'] == ostypename:
                return ostype['id']
        return None

    # 书籍管理 API
    def create_books(self, num: int = 10) -> Dict[str, Any]:
        """
        批量创建书籍
        :param num: 创建的书籍数量
        :return: 创建的书籍信息
        """
        book_datas = []
        response_datas = []
        for i in range(1, num+1):
            book_datas.append({
                "title": f"book_api_client_{i}",
                "author": f"songhz_{i}",
                "published_date": "2025-03-06",
                "isbn": f"1234567890_{i}"
            })
        url = f"{self.base_url}/api/books/"
        for book_data in book_datas:
            response_datas.append(self.create_book(book_data))
        return response_datas

    def create_book(self, book_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建书籍
        :param book_data: 书籍数据
        :return: 创建的书籍信息
        """
        url = f"{self.base_url}/api/books/"
        response = requests.post(url, json=book_data, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_book_list(self) -> list:
        """
        获取书籍列表
        :return: 书籍列表
        """
        url = f"{self.base_url}/api/books/"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_book_detail(self, book_id: int) -> Dict[str, Any]:
        """
        获取书籍详情
        :param book_id: 书籍 ID
        :return: 书籍详情
        """
        url = f"{self.base_url}/api/books/{book_id}/"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def update_book(self, book_id: int, book_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新书籍
        :param book_id: 书籍 ID
        :param book_data: 更新的书籍数据
        :return: 更新后的书籍信息
        """
        url = f"{self.base_url}/api/books/{book_id}/"
        response = requests.put(url, json=book_data, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def delete_book(self, book_id: int) -> None:
        """
        删除书籍
        :param book_id: 书籍 ID
        """
        url = f"{self.base_url}/api/books/{book_id}/"
        response = requests.delete(url, headers=self.headers)
        response.raise_for_status()

def main():
    # 创建 API 客户端实例
    api = DeviceManagerAPI()
    userinfo = {
        "username": "songhz",
        "password": "123456"
    }
    deviceinfo = {
        "name": "Device_api_client1",
        "os_type": "juniper_junos",
        "ip_address": "192.168.1.1",
        "port": 22,
        "username": "admin",
        "password": "admin123",
        "device_type": "switch",
        "protocol": "ssh"
    }
    ostypeinfo = {
        "name": "juniper_junos",
        "comment": "test api client"
    }
    commandinfo = {
        "command_text": "show version",
        "os_type": 'juniper_junos'
    }
    bookinfo = {
        "title": "book_api_client1",
        "author": "songhz",
        "published_date": "2025-03-06",
        "isbn": "1234567890"
    }
    bookinfo_update = {
        "title": "book_api_client1_update",
        "author": "songhz_update",
        "published_date": "2025-03-06",
        "isbn": "1234567890"
    }
    try:
        # 登录并获取 token
        print("登录...")
        login_response = api.login(userinfo["username"], userinfo["password"])
        print(f"登录成功，获取到 token: {login_response['token']}")
        # 批量创建书籍
        books = api.create_books()
        print(f"批量创建书籍成功: {json.dumps(books, indent=2, ensure_ascii=False)}")
        """
        device = api.create_device(deviceinfo)
        print(f"创建设备成功: {json.dumps(device, indent=2, ensure_ascii=False)}")
        os_type = api.create_os_type(ostypeinfo)
        print(f"创建 OS 类型成功: {json.dumps(os_type, indent=2, ensure_ascii=False)}")
        command_new = {
            "command_text": commandinfo["command_text"],
            "os_type": api.get_ostype_id(commandinfo["os_type"])
        }
        command = api.create_command(command_new)
        print(f"创建命令成功: {json.dumps(command, indent=2, ensure_ascii=False)}")
        """
        # 创建书籍
        #book = api.create_book(bookinfo)
        #print(f"创建书籍成功: {json.dumps(book, indent=2, ensure_ascii=False)}")

        # 获取书籍列表
        #booklist = api.get_book_list()
        #print(f"书籍列表: {json.dumps(booklist, indent=2, ensure_ascii=False)}")

        # 获取书籍详情
        #bookdetail = api.get_book_detail(21)
        #print(f"书籍详情: {json.dumps(bookdetail, indent=2, ensure_ascii=False)}")

        # 更新书籍
        #bookupdate = api.update_book(21, bookinfo_update)
        #print(f"更新书籍成功: {json.dumps(bookupdate, indent=2, ensure_ascii=False)}")

        # 删除书籍
        #api.delete_book(21)
        #print("删除书籍成功")

        # 设备管理示例
        #print("\n=== 设备管理 ===")
        
        # 创建设备
        #print("\n创建设备...")
        #device = api.create_device(deviceinfo)
        #print(f"创建设备成功: {json.dumps(device, indent=2, ensure_ascii=False)}")
        #device_id = device['id']

        # 获取设备列表
        #print("\n获取设备列表...")
        #devices = api.get_device_list()
        #print(f"设备列表: {json.dumps(devices, indent=2, ensure_ascii=False)}")

        # 获取设备详情
        #print("\n获取设备详情...")
        #device_detail = api.get_device_detail(device_id)
        #print(f"设备详情: {json.dumps(device_detail, indent=2, ensure_ascii=False)}")

        # 更新设备
        #print("\n更新设备...")
        #update_data = {
        #    'name': 'Updated Device',
        #    'ip_address': '192.168.1.2'
        #}
        #updated_device = api.update_device(device_id, update_data)
        #print(f"更新设备成功: {json.dumps(updated_device, indent=2, ensure_ascii=False)}")

        # 删除设备
        #print("\n删除设备...")
        #api.delete_device(device_id)
        #print("删除设备成功")

        # OS 类型管理示例
        #print("\n=== OS 类型管理 ===")
        
        # 创建 OS 类型
        #print("\n创建 OS 类型...")
        #os_type = api.create_os_type(ostypeinfo)
        #print(f"创建 OS 类型成功: {json.dumps(os_type, indent=2, ensure_ascii=False)}")
        #os_type_id = os_type['id']

        # 获取 OS 类型列表
        #print("\n获取 OS 类型列表...")
        #os_types = api.get_os_type_list()
        #print(f"OS 类型列表: {json.dumps(os_types, indent=2, ensure_ascii=False)}")

        # 获取 OS 类型详情
        #print("\n获取 OS 类型详情...")
        #os_type_detail = api.get_os_type_detail(os_type_id)
        #print(f"OS 类型详情: {json.dumps(os_type_detail, indent=2, ensure_ascii=False)}")

        # 更新 OS 类型
        #print("\n更新 OS 类型...")
        #update_data = {
        #    'name': 'Updated OS Type',
        #    'comment': 'Updated Comment'
        #}
        #updated_os_type = api.update_os_type(os_type_id, update_data)
        #print(f"更新 OS 类型成功: {json.dumps(updated_os_type, indent=2, ensure_ascii=False)}")


        # 命令管理示例
        #print("\n=== 命令管理 ===")
        
        # 创建命令
        #print("\n创建命令...")
        #command = api.create_command(commandinfo)
        #print(f"创建命令成功: {json.dumps(command, indent=2, ensure_ascii=False)}")
        #command_id = command['id']

        # 获取命令列表
        #print("\n获取命令列表...")
        #commands = api.get_command_list()
        #print(f"命令列表: {json.dumps(commands, indent=2, ensure_ascii=False)}")

        # 获取命令详情
        #print("\n获取命令详情...")
        #command_detail = api.get_command_detail(command_id)
        #print(f"命令详情: {json.dumps(command_detail, indent=2, ensure_ascii=False)}")

        # 更新命令
        #print("\n更新命令...")
        #update_data = {
        #    'command_text': 'Updated Command',
        #    'os_type': os_type_id
        #}
        #updated_command = api.update_command(command_id, update_data)
        #print(f"更新命令成功: {json.dumps(updated_command, indent=2, ensure_ascii=False)}")

        # 删除命令
        #print("\n删除命令...")
        #api.delete_command(command_id)
        #print("删除命令成功")

        # 删除 OS 类型
        #print("\n删除 OS 类型...")
        #api.delete_os_type(os_type_id)
        #print("删除 OS 类型成功")

    except requests.exceptions.RequestException as e:
        print(f"API 请求错误: {e}")
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    main() 