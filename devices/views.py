import os
import paramiko
from django.shortcuts import render, get_object_or_404, redirect
from django.db import transaction
from django.conf import settings
from django.http import FileResponse, JsonResponse,HttpResponse, HttpResponseNotFound, Http404
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Device, OSType, Command
from .serializers import DeviceSerializer, OSTypeSerializer, CommandSerializer
from pathlib import Path
import csv
import json
import serial.tools.list_ports
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
from django.views import View
import subprocess
import time
import textfsm
import io
from concurrent.futures import ThreadPoolExecutor
from django.contrib.auth.decorators import login_required
from rest_framework.permissions import IsAuthenticated
from authentication.decorators import CustomLoginRequired
from authentication.permissions import IsAuthenticatedForWriteOnly
from django.core.cache import cache
import redis
import logging  # 添加logging导入

# 定义日志器，名称与Django日志配置中的logger名称对应
logger = logging.getLogger('devices')  # 'devices'对应settings.py中的日志器名称

@login_required
def OSTypesList(request):
    """
    渲染OS类型管理主页。
    """
    return render(request, 'devices/os_types_home.html')
#OS类型管理API
class OSTypesViewSet(viewsets.ModelViewSet):
    """
    OS类型视图集，用于处理OS类型的增删改查操作。
    """
    #permission_classes = [IsAuthenticated]  # 添加权限类
    permission_classes = [IsAuthenticatedForWriteOnly]
    serializer_class = OSTypeSerializer
    # 设置缓存
    cache_key = 'os_types'
    cache_timeout = 60*60*24

    def get_queryset(self):
        """
        获取OS类型列表
        """
        os_types = cache.get(self.cache_key)
        if not os_types:
            os_types = OSType.objects.all()
            cache.set(self.cache_key, os_types, self.cache_timeout)
            logger.debug("从数据库中获取OS类型列表")  # 使用日志系统
        else:
            logger.debug("从缓存中获取OS类型列表")  # 使用日志系统
        return os_types

    def create(self, request):
        """
        创建新的OS类型实例。
        ---
        request:
            title: OS类型名称
        response:
            201: 创建成功
            400: 请求数据无效
        """
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            # 清除缓存
            cache.delete(self.cache_key)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, pk=None):
        """
        获取特定OS类型的详细信息。
        ---
        response:
            200: 返回OS类型详细信息
            404: 未找到OS类型
        """
        os_type = self.get_object()
        serializer = self.get_serializer(os_type)
        return Response(serializer.data)

    def update(self, request, pk=None):
        """
        更新现有OS类型实例。
        ---
        request:
            title: OS类型名称
        response:
            200: 更新成功
            400: 请求数据无效
            404: 未找到OS类型
        """
        os_type = self.get_object()
        serializer = self.get_serializer(os_type, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            # 清除缓存
            cache.delete(self.cache_key)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        """
        删除特定OS类型实例。
        ---
        response:
            204: 删除成功
            404: 未找到OS类型
            403: 没有权限
        """
        if request.data.get('ids'):
            # 批量删除
            ids = request.data['ids']
            OSType.objects.filter(id__in=ids).delete()
            # 清除缓存
            cache.delete(self.cache_key)
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            # 删除单个OS类型
            os_type = self.get_object()
            os_type.delete()
            # 清除缓存
            cache.delete(self.cache_key)
            return Response(status=status.HTTP_204_NO_CONTENT)

@CustomLoginRequired
@csrf_exempt
def import_os_types(request):
    """
    导入OS类型
    """
    if request.method == 'POST':
        file = request.FILES.get('file')  # 修改这里，从'importFile'改为'file'
        if not file:
            return JsonResponse({'error': '没有上传文件'}, status=400)

        # 读取 CSV 文件
        try:
            decoded_file = file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.reader(io_string, delimiter=',')
            next(reader)  # 跳过表头

            for row in reader:
                name, comment = row
                # 创建OS类型对象
                OSType.objects.create(
                    name=name,
                    comment=comment
                )
            # 清除缓存
            cache.delete('os_types')
            return JsonResponse({'message': 'OS类型导入成功！'}, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
def export_os_types(request):
    """
    导出OS类型
    """
    if request.method == 'POST':
        ids = request.POST.get('ids')
        if not ids:
            return JsonResponse({'error': '没有选择OS类型'}, status=400)

        ids = json.loads(ids)  # 将 JSON 字符串转换为列表
        # 过滤掉 'on'
        if 'on' in ids:
            ids.remove('on')
        os_types = OSType.objects.filter(id__in=ids)  # 获取选中的OS类型

        # 创建 CSV 文件
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="os_types.csv"'
        
        # 使用 UTF-8 编码
        response.write(u'\ufeff'.encode('utf-8'))  # 添加 BOM 以支持 Excel 打开时的 UTF-8 编码
        writer = csv.writer(response)

        # 写入表头
        writer.writerow(['name', 'comment'])
        
        # 写入书籍数据
        for os_type in os_types:
            writer.writerow([os_type.name, os_type.comment])

        return response  # 直接返回 CSV 文件 

@CustomLoginRequired
def CommandsList(request):
    """
    渲染命令管理主页。
    """
    return render(request, 'devices/commands_home.html')

class CommandsViewSet(viewsets.ModelViewSet):
    """
    命令视图集，用于处理命令的增删改查操作。
    """
    #permission_classes = [IsAuthenticated]  # 添加权限类
    permission_classes = [IsAuthenticatedForWriteOnly]
    serializer_class = CommandSerializer
    # 设置缓存
    cache_key = 'commands'
    cache_timeout = 60*60*24

    def get_queryset(self):
        """
        获取命令列表，包含模板状态信息
        """
        commands = cache.get(self.cache_key)
        if not commands:
            commands = Command.objects.all()
            # 为每个命令添加模板状态信息
            for command in commands:
                os_type = command.os_type.name
                command_text = command.command_text.replace(' ', '_')
                if 'huawei' in os_type.lower():
                    os_type = 'huawei_vrp'
                
                try:
                    template_path = os.path.join(settings.DIR_INFO['CONF_DIR'],'textfsm' f'{os_type}_{command_text}.textfsm')
                    csv_path = os.path.join(settings.DIR_INFO['REPORT_DIR'],'textfsm', f'{os_type}_{command_text}.csv')
                    template_status = 'exists' if os.path.exists(template_path) else 'not_exists'
                    csv_status = 'exists' if os.path.exists(csv_path) else 'not_exists'
                    command.status= {
                        'template_status': template_status, 
                        'csv_status': csv_status
                    }
                except Exception as e:
                    command.status= {
                        'template_status': 'error',
                        'csv_status': 'error'
                    }
            
            cache.set(self.cache_key, commands, self.cache_timeout)
            logger.info(f"从数据库中获取命令列表")
        else:
            logger.info(f"从缓存中获取命令列表")
        return commands

    def create(self, request):
        """
        创建新的命令实例。
        ---
        request:
            command_text: 命令文本
            os_type: 操作系统类型
            comment: 命令描述
        response:
            201: 创建成功
            400: 请求数据无效
        """
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            # 清除缓存
            cache.delete(self.cache_key)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, pk=None):
        """
        获取特定命令的详细信息。
        ---
        response:
            200: 返回命令详细信息
            404: 未找到命令
        """
        command = self.get_object()
        serializer = self.get_serializer(command)
        return Response(serializer.data)

    def update(self, request, pk=None):
        """
        更新现有命令实例。
        ---
        request:
            command_text: 命令文本
            os_type: 操作系统类型
            comment: 命令描述
        response:
            200: 更新成功
            400: 请求数据无效
            404: 未找到命令
        """
        command = self.get_object()
        serializer = self.get_serializer(command, data=request.data, partial=True)
        logger.debug(f"前端接受的命令数据: {serializer}")
        if serializer.is_valid():
            serializer.save()
            # 清除缓存
            cache.delete(self.cache_key)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        """
        删除特定命令实例。
        ---
        response:
            204: 删除成功
            404: 未找到命令
            403: 没有权限
        """
        if request.data.get('ids'):
            # 批量删除
            ids = request.data['ids']
            Command.objects.filter(id__in=ids).delete()
            # 清除缓存
            cache.delete(self.cache_key)
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            # 删除单个命令
            command = self.get_object()
            command.delete()
            # 清除缓存
            cache.delete(self.cache_key)
            return Response(status=status.HTTP_204_NO_CONTENT)

@CustomLoginRequired
@csrf_exempt
def import_commands(request):
    """
    导入命令
    """
    if request.method == 'POST':
        file = request.FILES.get('file')  # 修改这里，从'importFile'改为'file'
        if not file:
            return JsonResponse({'error': '没有上传文件'}, status=400)

        # 读取 CSV 文件
        try:
            decoded_file = file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.reader(io_string, delimiter=',')
            next(reader)  # 跳过表头

            for row in reader:  
                command_text, os_type, comment = row
                os_type_obj = OSType.objects.get(name=os_type)
                # 创建命令对象
                Command.objects.create(
                    command_text=command_text,
                    os_type=os_type_obj,
                    comment=comment 
                )
            # 清除缓存
            cache.delete('commands')
            return JsonResponse({'message': '命令导入成功！'}, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
@csrf_exempt
def export_commands(request):   
    """
    导出命令
    """
    if request.method == 'POST':
        ids = request.POST.get('ids')
        if not ids: 
            return JsonResponse({'error': '没有选择命令'}, status=400)

        ids = json.loads(ids)  # 将 JSON 字符串转换为列表
        # 过滤掉 'on'
        if 'on' in ids:
            ids.remove('on')
        commands = Command.objects.filter(id__in=ids)  # 获取选中的命令 
        
        # 创建 CSV 文件
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="commands.csv"'
        
        # 使用 UTF-8 编码
        response.write(u'\ufeff'.encode('utf-8'))  # 添加 BOM 以支持 Excel 打开时的 UTF-8 编码  
        writer = csv.writer(response)

        # 写入表头
        writer.writerow(['command_text', 'os_type', 'comment'])
        
        # 写入命令数据  
        for command in commands:
            writer.writerow([command.command_text, command.os_type, command.comment])

        return response  # 直接返回 CSV 文件  

# textfsm模板管理API
class TextFSMView(APIView):
    """
    处理TextFSM模板的增删改查操作。
    """
    permission_classes = [IsAuthenticatedForWriteOnly]
    textfsm_dir = os.path.join(settings.DIR_INFO['CONF_DIR'], 'textfsm')

    def get(self, request, os_type, command_text):
        """
        获取特定textfsm模板的详细信息。
        ---
        response:
            200: 返回textfsm模板详细信息
            404: 未找到textfsm模板
        """
        command_text = command_text.replace(' ', '_')  # 替换空格以匹配文件名
        if 'huawei' in os_type.lower():
            os_type = 'huawei_vrp'
        file_path = os.path.join(self.textfsm_dir, f"{os_type}_{command_text}.textfsm")

        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                template_text = f.read()
            return Response({'template_text': template_text})
        else:
            return Response({'template_text': None}, status=status.HTTP_200_OK)

    def post(self, request, os_type, command_text):
        """
        创建新的textfsm模板。
        ---
        request:
            template_text: 模板文本
        response:
            201: 创建成功
            400: 请求数据无效
        """
        command_text = command_text.replace(' ', '_')  # 替换空格以匹配文件名
        template_text = request.data.get('template_text')

        if not template_text:
            return Response({'error': '模板内容不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        # 将模板文本写入文件
        if 'huawei' in os_type.lower():
            os_type = 'huawei_vrp'
        file_path = os.path.join(self.textfsm_dir, f"{os_type}_{command_text}.textfsm")
        with open(file_path, 'w') as f:
            f.write(template_text)
        cache.delete("commands")
        return Response({'message': '模板创建成功'}, status=status.HTTP_201_CREATED)

    def put(self, request, os_type, command_text):
        """
        更新现有textfsm模板。
        ---
        request:
            template_text: 模板文本
        response:
            200: 更新成功
            404: 未找到textfsm模板
        """
        command_text = command_text.replace(' ', '_')  # 替换空格以匹配文件名
        if 'huawei' in os_type.lower():
            os_type = 'huawei_vrp'
        file_path = os.path.join(self.textfsm_dir, f"{os_type}_{command_text}.textfsm")

        if not os.path.exists(file_path):
            return Response({'error': '模板文件不存在'}, status=status.HTTP_404_NOT_FOUND)

        template_text = request.data.get('template_text')
        with open(file_path, 'w') as f:
            f.write(template_text)

        return Response({'message': '模板更新成功'}, status=status.HTTP_200_OK)

    def delete(self, request, os_type, command_text):
        """
        删除特定textfsm模板。
        ---
        response:
            204: 删除成功
            404: 未找到textfsm模板
        """
        if 'huawei' in os_type.lower():
            os_type = 'huawei_vrp'
        file_path = os.path.join(self.textfsm_dir, f"{os_type}_{command_text}.textfsm")

        if os.path.exists(file_path):
            os.remove(file_path)
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({'error': '模板文件不存在'}, status=status.HTTP_404_NOT_FOUND)

# 查看和删除textfsm解析结果
class TextFSMCsvView(APIView):
    """
    处理TextFSM解析结果的查询和删除操作。
    """
    permission_classes = [IsAuthenticatedForWriteOnly]
    textfsmcsv_dir = os.path.join(settings.DIR_INFO['REPORT_DIR'], 'textfsm')

    def get(self, request, os_type, command_text):
        """
        获取特定textfsm解析结果的详细信息。
        ---
        response:
            200: 返回textfsm解析结果详细信息
            404: 未找到textfsm解析结果
        """
        if 'huawei' in os_type.lower():
            os_type = 'huawei_vrp'
        file_name = f"{os_type}_{command_text}.csv"
        file_path = os.path.join(self.textfsmcsv_dir, f"{os_type}_{command_text}.csv")
        logger.debug(f"请求的文件路径: {file_path}")  # 添加调试输出

        if os.path.exists(file_path):
            return Response({'csv_file_name': file_name})
        else:
            logger.debug(f"未找到文件: {file_path}")  # 添加调试输出
            return Response({'csv_file_name': None}, status=status.HTTP_200_OK)
    def delete(self, request, os_type, command_text):
        """
        删除特定textfsm解析结果。
        ---
        response:
            204: 删除成功
            404: 未找到textfsm解析结果
        """
        if 'huawei' in os_type.lower():
            os_type = 'huawei_vrp'
        file_path = os.path.join(self.textfsmcsv_dir, f"{os_type}_{command_text}.csv")
        logger.debug(f"删除file_path: {file_path}")
        if os.path.exists(file_path):
            os.remove(file_path)
            cache.delete('commands')
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({'error': '解析结果文件不存在'}, status=status.HTTP_404_NOT_FOUND)

# 查看textfsm解析结果
def view_textfsm_result(request, command_id):
    """
    查看textfsm解析结果
    """
    logger.debug(f"查看textfsm解析结果: {command_id}")  # 添加调试输出
    command = get_object_or_404(Command, id=command_id)
    os_type = command.os_type.name
    if 'huawei' in os_type.lower():
        os_type = 'huawei_vrp'
    command_text = command.command_text.replace(' ', '_')  # 替换空格以匹配文件名
    csv_file_name = f"{os_type}_{command_text}.csv"

    # 构建 CSV 文件路径
    csv_file_path = os.path.join(settings.DIR_INFO['REPORT_DIR'],'textfsm', csv_file_name)

    if os.path.exists(csv_file_path):
        with open(csv_file_path, mode='r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            csv_data = [row for row in reader]  # 读取 CSV 文件内容
        return render(request, 'devices/view_csv.html', {
            'csv_data': csv_data,
            'file_name': os.path.basename(csv_file_path),
            'csv_file_path': csv_file_path,  # 传递文件路径
            'return_url': 'commands_list'  # 传递 URL 名称
        })
    else:
        raise Http404("解析结果文件不存在")

# 设备管理主页
@CustomLoginRequired
def DevicesList(request):
    """
    渲染设备管理主页。
    """
    return render(request, 'devices/devices_home.html')
# 设备管理API
class DevicesViewSet(viewsets.ModelViewSet):
    """
    设备视图集，用于处理设备的增删改查操作。
    """
    #permission_classes = [IsAuthenticated]  # 添加权限类
    permission_classes = [IsAuthenticatedForWriteOnly]
    serializer_class = DeviceSerializer
    # 设置缓存
    cache_key = 'devices_list'
    # 缓存超时时间
    cache_timeout = 60*60*24

    def get_queryset(self):
        """
        获取设备列表
        """
        #设置缓存
        devices = cache.get(self.cache_key)
        if not devices:
            devices = Device.objects.all()
            cache.set(self.cache_key, devices, self.cache_timeout)
            logger.debug(f"从数据库中获取设备列表")
        else:
            logger.debug(f"从缓存中获取设备列表")
        return devices
    
    def create(self, request):
        """
        创建新的设备实例。
        ---
        request:
            title: 设备名称
        response:
            201: 创建成功
            400: 请求数据无效
        """
        logger.debug(f"创建新的设备实例: {request.data}")  # 添加调试输出
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            # 清除缓存
            cache.delete(self.cache_key)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, pk=None):
        """
        获取特定设备的详细信息。
        ---
        response:
            200: 返回设备详细信息
            404: 未找到设备
        """
        logger.debug(f"获取特定设备的详细信息: {pk}")  # 添加调试输出
        device = self.get_object()
        serializer = self.get_serializer(device)
        return Response(serializer.data)

    def update(self, request, pk=None):
        """
        更新现有设备实例。
        ---
        request:
            title: 设备名称
        response:
            200: 更新成功
            400: 请求数据无效
            404: 未找到设备
        """
        logger.debug(f"更新现有设备实例: {pk}")  # 添加调试输出
        device = self.get_object()
        serializer = self.get_serializer(device, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            # 清除缓存
            cache.delete(self.cache_key)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        """
        删除特定设备实例。
        ---
        response:
            204: 删除成功
            404: 未找到设备
            403: 没有权限
        """
        if request.data.get('ids'):
            # 批量删除
            ids = request.data['ids']
            Device.objects.filter(id__in=ids).delete()
            # 清除缓存
            cache.delete(self.cache_key)
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            # 删除单个设备
            device = self.get_object()
            device.delete()
            # 清除缓存
            cache.delete(self.cache_key)
            return Response(status=status.HTTP_204_NO_CONTENT)

# 设备状态更新
@CustomLoginRequired
@csrf_exempt
def devices_update_status(request):
    """
    更新所有设备状态
    """
    if request.method == 'POST':
        body = json.loads(request.body)  # 解析 JSON 请求体
        device_ids = body.get('device_ids', [])  # 获取设备 ID 列表
        updated_devices = []
        # 清除缓存
        cache_key = 'devices_list'
        cache.delete(cache_key)
        # 批量检测更新设备状态
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(device_update_status, request,device_id): device_id for device_id in device_ids}
            for future in futures:
                try:
                    result = future.result()  # 获取线程执行结果
                    updated_devices.append(result)
                except Exception as e:
                    logging.error(f"Error updating device {futures[future]}: {e}")

        return JsonResponse({'updated_devices': updated_devices})

# 更新设备状态
@CustomLoginRequired
def device_update_status(request,device_id):
    """
    更新设备状态
    """
    device = Device.objects.get(id=device_id)
    if ping_device(device.ip_address):  # 检测设备状态
        device.status = 'online'  # 如果在线，更新状态
    else:
        device.status = 'offline'  # 如果离线，更新状态
    device.save()
    return device_id
# 检测设备状态
def ping_device(ip_address):
    """
    检测设备状态
    """
    try:
        # 使用 ping 命令检测设备状态
        output = subprocess.check_output(['ping', '-c', '1', ip_address], stderr=subprocess.STDOUT, universal_newlines=True)
        return True  # 如果 ping 成功，返回 True
    except subprocess.CalledProcessError:
        return False  # 如果 ping 失败，返回 False

# 设备信息导入
@CustomLoginRequired
@csrf_exempt
def import_devices(request):
    """
    导入设备
    """
    # 清除缓存
    cache_key = 'devices_list'
    cache.delete(cache_key)
    if request.method == 'POST':
        file = request.FILES.get('file') 
        logger.debug(f"导入设备请求文件:{file}")
        if not file:
            return JsonResponse({'error': '没有上传文件'}, status=400)

        # 读取 CSV 文件
        try:
            decoded_file = file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.reader(io_string, delimiter=',')
            next(reader)  # 跳过表头

            for row in reader:
                name, ip_address, port, username, password, device_type, os_type = row
                # 创建设备对象
                Device.objects.create(
                    name=name,
                    ip_address=ip_address,
                    port=port,
                    username=username,
                    password=password,
                    device_type=device_type,
                    os_type=os_type
                )
            return JsonResponse({'message': '设备导入成功！'}, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


# 设备信息导出
@csrf_exempt
def export_devices(request):
    """
    导出设备
    """
    if request.method == 'POST':
        ids = request.POST.get('ids')
        if not ids:
            return JsonResponse({'error': '没有选择设备'}, status=400)

        ids = json.loads(ids)  # 将 JSON 字符串转换为列表
        # 过滤掉 'on'
        if 'on' in ids:
            ids.remove('on')
        devices = Device.objects.filter(id__in=ids)  # 获取选中的设备

        # 创建 CSV 文件
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="devices.csv"'
        
        # 使用 UTF-8 编码
        response.write(u'\ufeff'.encode('utf-8'))  # 添加 BOM 以支持 Excel 打开时的 UTF-8 编码
        writer = csv.writer(response)

        # 写入表头
        writer.writerow(['name', 'ip_address', 'port', 'username', 'device_type', 'os_type'])
        
        # 写入设备数据
        for device in devices:
            writer.writerow([device.name, device.ip_address, device.port, device.username, device.device_type, device.os_type])

        return response  # 直接返回 CSV 文件 

#CSV文件管理页面
@CustomLoginRequired
def list_csv_files(request):
    """
    列出CSV文件
    """
    results_dir = settings.DIR_INFO['REPORT_DIR']
    csv_files = []

    # 遍历 results 目录下的所有文件和子目录
    for root, dirs, files in os.walk(results_dir):
        for file in files:
            if file.endswith('.csv'):
                # 获取相对路径
                relative_path = os.path.relpath(os.path.join(root, file), results_dir)
                # 获取文件的创建时间
                file_path = os.path.join(root, file)
                creation_time = time.ctime(os.path.getctime(file_path))
                csv_files.append({'path': relative_path, 'creation_time': creation_time})

    # 按照创建时间排序
    csv_files.sort(key=lambda x: x['creation_time'], reverse=True)

    return render(request, 'devices/csv_list.html', {'csv_files': csv_files})

# 读取CSV文件内容
#@login_required
def read_csv_file(file_path):
    """
    读取CSV文件
    """
    full_path = os.path.join(settings.DIR_INFO['REPORT_DIR'], file_path)
    if os.path.exists(full_path):
        with open(full_path, mode='r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            csv_data = [row for row in reader]  # 读取 CSV 文件内容
        return csv_data
    raise Http404("文件不存在")

#@login_required
# 查看CSV文件内容
def view_csv_file(request, file_path):
    """
    查看CSV文件
    """
    csv_data = read_csv_file(file_path)
    return render(request, 'devices/view_csv.html', {
        'csv_data': csv_data,
        'file_name': os.path.basename(file_path),
        'return_url': 'list_csv_files'  # 传递 URL 名称
    })
# 下载CSV文件
#@login_required
def download_csv_file(request, file_path):
    """
    下载CSV文件
    """
    full_path = os.path.join(settings.DIR_INFO['REPORT_DIR'],'inspect',  file_path)
    if os.path.exists(full_path):
        return FileResponse(open(full_path, 'rb'), as_attachment=True, filename=os.path.basename(full_path))
    raise Http404("文件不存在")
# 获取巡检报告
def devices_inspect_report(request, report_id):
    """
    获取巡检报告
    """
    filepath = os.path.join(settings.DIR_INFO['REPORT_DIR'],'inspect', f"{report_id}/index.html")
    logger.debug(f"查看报告:{filepath}")
    if os.path.exists(filepath): 
        return FileResponse(open(filepath, 'rb'), filename=f"report_{report_id}.html")
    else:
        filepath = os.path.join(settings.DIR_INFO['REPORT_DIR'],'config' f"{report_id}/index.html")
        if os.path.exists(filepath): 
         return FileResponse(open(filepath, 'rb'), filename=f"report_{report_id}.html")
    return HttpResponseNotFound("报告不存在")

# 在线测试TextFSM
class TextFSMTestView(View):
    """
    测试TextFSM
    """
    def get(self, request):
        return render(request, 'devices/textfsm_test.html')

    def post(self, request):
        raw_text = request.POST.get('raw_text')
        template_text = request.POST.get('template_text')

        try:
            template_file = io.StringIO(template_text)
            fsm = textfsm.TextFSM(template_file)
            parsed_result = fsm.ParseText(raw_text)
            # 将解析结果转换为 JSON 格式
            json_result = json.dumps(parsed_result,indent=4)
            return JsonResponse({'result': json_result})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

# 设备巡检下发页面
@CustomLoginRequired
def devices_inspect(request):
    """
    设备巡检下发页面
    """
    return render(request, 'devices/inspect.html')

# 设备巡检列表
@CustomLoginRequired
def devices_inspections(request):
    """
    设备巡检列表页面
    """
    return render(request, 'devices/inspections.html')

# 设备巡检API
class DevicesInspectionsView(APIView):
    """
    查询和删除设备巡检结果API
    """
    permission_classes = [IsAuthenticatedForWriteOnly]
    # 设置缓存
    cache_key = 'devices_inspections'
    cache_timeout = 60*60*24
    history_dir = os.path.join(settings.DIR_INFO['REPORT_DIR'],'inspect')

    def get(self, request):
        """获取设备巡检历史记录"""
        logger.debug(f"调用api获取设备巡检历史记录")
        # 从缓存中获取
        histories = cache.get(self.cache_key)
        if not histories:
            histories =[]
            # 遍历目录中的所有文件夹
            for foldername in os.listdir(self.history_dir):
                folder_path = os.path.join(self.history_dir, foldername)
                if os.path.isdir(folder_path):
                    index_file_path = os.path.join(folder_path, 'index.json')
                    if os.path.exists(index_file_path):
                        with open(index_file_path, 'r', encoding='utf-8') as file:
                            try:
                                # 读取并解析 JSON 文件
                                data = json.load(file)
                                # 假设 JSON 文件中有 'id', 'device', 'command', 'result', 'timestamp' 字段
                                histories.append({
                                    'id': foldername,  # 使用文件夹名作为 ID
                                    'device_ids': data.get('device_ids', '未知设备'),
                                    'command_ids': data.get('command_ids', '无命令'),
                                    'server_commands':  data.get('server_commands', '无命令'),
                                    'network_commands':  data.get('network_commands', '无命令'),
                                    'status': data.get('status', '无结果'),
                                    'start_time': data.get('start_time', '未知时间'),
                                    'end_time': data.get('end_time', '未知时间'),
                                })
                            except json.JSONDecodeError:
                                continue  # 如果 JSON 解析失败，跳过该文件
                    else:
                        # 如果index.json文件不存在，则删除整个文件夹
                        import shutil
                        shutil.rmtree(folder_path)

            histories.sort(key=lambda x: x['end_time'], reverse=True)
            # 缓存结果
            cache.set(self.cache_key, histories, self.cache_timeout)
            logger.debug(f"从数据库中获取设备巡检历史记录")
        else:
            logger.debug(f"从缓存中获取设备巡检历史记录")
        return JsonResponse({'histories': histories})
    #@login_required
    def delete(self, request, history_id):
        """删除指定的历史记录"""
        logger.debug(f"调用api删除指定的历史记录: {history_id}")
        # 清除缓存
        cache.delete(self.cache_key)
        try:
            folder_path = os.path.join(self.history_dir, history_id)
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                # 删除整个文件夹及其内容
                import shutil
                shutil.rmtree(folder_path)
                return Response({'status': 'success', 'message': '历史记录已删除'}, status=status.HTTP_204_NO_CONTENT)
            else:
                return Response({'error': '指定的历史记录不存在'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        # 批量删除巡检记录
        history_ids = request.data.get('ids')
        logger.debug(f"批量删除巡检记录: {history_ids}")
        for history_id in history_ids:
            self.delete(request, history_id)
        cache.delete(self.cache_key)
        return Response({'status': 'success', 'message': '文件删除成功'}, status=status.HTTP_204_NO_CONTENT)

# 独立终端连接交互页面
class TerminalSingleView(APIView):
    def get(self, request, device_id=None):
        context = {}
        return render(request, 'devices/terminal_single.html', context)

# sftp文件传输
class SFTPView(APIView):
    def get(self, request, device_id):
        try:
            # 验证设备ID是否存在
            device = Device.objects.get(id=device_id)
            
            #设置本地和远程默认的目录 songhz
            local_home = Path.home()
            remote_home = '/root ' if device.username == 'root' else '/home/%s'%device.username
            if device.device_type == 'switch':
                remote_home = 'flash:'
            return render(request, 'devices/sftp.html', {
                'device_id': device_id,
                'local_home': local_home,
                'remote_home': remote_home,
            })
        except Device.DoesNotExist:
            return Response({'error': 'Device not found'}, status=status.HTTP_404_NOT_FOUND)

# 远程文件管理
class SftpFileManager(APIView):
    """
    远程文件管理2
    """
    permission_classes = [IsAuthenticated]  # 添加权限类

    def get(self, request, device_id):
        path = request.GET.get('path', '/')
        try:
            device = Device.objects.get(id=device_id)
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            #处理交换机类设备的SSH连接请求
            if device.device_type == 'switch':
                ssh.connect(
                    hostname=device.ip_address,
                    username=device.username,
                    password=device.password,
                    look_for_keys=False,
                    allow_agent=False
                )
            else:
                ssh.connect(
                    hostname=device.ip_address,
                    port=device.port,
                    username=device.username,
                    password=device.password
                )
            
            stdin, stdout, stderr = ssh.exec_command(f'ls -lp {path}') if device.device_type == 'server' else ssh.exec_command('dir flash:')
            files = []
            if device.device_type == 'switch':
                for line in stdout:
                    if line.strip():
                        parts = line.split()
                        if len(parts) < 8:
                            continue
                            
                        is_dir = parts[1].startswith('d')
                        name = parts[-1].rstrip('/')
                        size = 0 if is_dir else int(parts[2])
                        
                        files.append({
                            'name': name,
                            'is_dir': is_dir,
                            'size': size
                        })
            else:
                if path != '/':
                    files.append({
                        'name': '..',
                        'is_dir': True,
                        'parent': True
                    })
                
                for line in stdout:
                    if line.strip():
                        parts = line.split()
                        if len(parts) < 9:
                            continue
                            
                        is_dir = parts[0].startswith('d')
                        name = parts[-1].rstrip('/')
                        size = 0 if is_dir else int(parts[4])
                        
                        files.append({
                            'name': name,
                            'is_dir': is_dir,
                            'size': size
                        })
            
            ssh.close()
            #将文件列表按照目录类型进行排序 songhz
            files.sort(key=lambda x: x['is_dir'],reverse=True) 
            return Response({
                'current_path': path,
                'files': files
            })
        except Exception as e:
            logging.error(f"上传文件失败: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# 上传文件
class SftpFileUpload(APIView):
    """
    sftp文件上传
    """
    #permission_classes = [IsAuthenticated]  # 添加权限类

    def post(self, request, device_id):
        logger.debug("SftpFileUpload接收文件上传请求")
        try:
            device = Device.objects.get(id=device_id)
            ssh = None
            sftp = None
            
            # 从FormData获取参数
            remote_path = request.data.get('remote_path')
            local_path = request.data.get('local_path')
            file = request.FILES.get('file')

                
            # 处理交换机类设备的SSH连接请求
            if device.device_type == 'switch':
                ssh = paramiko.Transport((device.ip_address,device.port))
                ssh.connect(username=device.username,password=device.password)
                sftp = paramiko.SFTPClient.from_transport(ssh)
                remote_path = ''
                logger.debug(f"交换机设备的远程路径: {remote_path}")  # 添加调试输出
            else:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(
                    hostname=device.ip_address,
                    port=device.port,
                    username=device.username,
                    password=device.password
                ) 
                sftp = ssh.open_sftp()
                logger.debug(f"服务器设备的远程路径: {remote_path}")  # 添加调试输出
            
            # 上传文件
            remote_file_path = os.path.join(remote_path, file.name)
            logger.debug(f"开始上传文件{file.name}到远程路径: {remote_file_path}")  # 添加调试输出
            sftp.putfo(file.file,remote_file_path)
            # 清理资源
            sftp.close()
            ssh.close()
            
            return Response({'status': 'success'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# 下载文件
class SftpFileDownload(APIView):
    """
    文件下载2
    """
    #permission_classes = [IsAuthenticated]  # 添加权限类

    def get(self, request, device_id):
        logger.debug("SftpFileDownload接收文件下载请求")
        logger.debug(f"request:{request},device_id:{device_id}")
        
        try:
            device = Device.objects.get(id=device_id)
            ssh = None
            sftp = None
            remote_path = request.GET.get('remote_path')
            local_path = request.GET.get('local_path')
            filename = request.GET.get('filename')
            remote_url = None
            #处理交换机类设备的SSH连接请求
            if device.device_type == 'switch':
                ssh = paramiko.Transport((device.ip_address,device.port))
                ssh.connect(username=device.username,password=device.password)
                sftp = paramiko.SFTPClient.from_transport(ssh)
                #h3c交换机上SFTP传输文件不用家目录
                remote_url = filename
            else:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(
                    hostname=device.ip_address,
                    port=device.port,
                    username=device.username,
                    password=device.password
                ) 
                sftp = ssh.open_sftp()
                remote_url = remote_path+'/'+filename
            
            #当添加目录时默认会在该目录同时存放一份
            sftp.get(remote_url, filename)
            sftp.close()
            ssh.close()
            
            response = FileResponse(open(filename, 'rb'))
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            logging.error(f"下载文件失败: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# 点击终端按钮进入终端交互页面
def TerminalSimpleView(request, device_id):
    try:
        logger.debug(f"TerminalSimpleView,request:{request},device_id:{device_id}")
        device = Device.objects.get(id=device_id)
        return render(request, 'devices/terminal_simple.html', {
            'device': device
        })
    except Device.DoesNotExist:
        logging.error("Device not found")
        return HttpResponseNotFound('设备未找到')

# 串口终端连接交互页面
def SerialTerminalView(request):
    """
    串口终端连接交互页面
    """
    return render(request, 'devices/serial_terminal.html')

# 获取串口列表
def get_serial_ports(request):
    """
    获取串口列表
    """
    ports = [port.device for port in serial.tools.list_ports.comports()]
    return JsonResponse(ports, safe=False)



# 设备日志管理页面
def devices_logs(request):
    """日志中心页面"""
    return render(request, 'devices/devices_logs.html')

# 设备日志API
class DevicesLogsView(APIView):
    """
    查询和删除设备日志API
    """
    permission_classes = [IsAuthenticatedForWriteOnly]
    terminal_logs_dir = settings.DIR_INFO['LOG_DIR'] # 设备控制台交互日志目录
    inspection_logs_dir = os.path.join(settings.DIR_INFO['REPORT_DIR'], 'inspect') # 巡检日志目录
    config_logs_dir = os.path.join(settings.DIR_INFO['REPORT_DIR'], 'config') # 配置下发日志目录

    def get(self, request):
        """获取设备日志列表"""
        logger.debug("调用api获取设备日志列表")
        #设备控制台交互日志目录
        #terminal_logs_dir = os.path.join(settings.BASE_DIR, 'logs')
        # 巡检日志目录
        #inspection_logs_dir = os.path.join(settings.BASE_DIR, 'results')
        # 配置下发日志目录
        #config_logs_dir = os.path.join(settings.BASE_DIR, 'config_results')
        # 所有日志
        logs_all = []

        # 遍历巡检日志目录中的所有日志
        for foldername in os.listdir(self.inspection_logs_dir):
            # 巡检日志目录
            folder_path = os.path.join(self.inspection_logs_dir, foldername)
            # 搜索巡检日志目录下的.log日志文件
            for log_file in os.listdir(folder_path):
                if log_file.endswith('.log'):
                    log_file_path = os.path.join(folder_path, log_file)
                    hostname = log_file.split('__')[0]
                    ip = log_file.split('__')[1].rstrip('.log')
                    # 获取日志文件的最后修改时间
                    last_modified = os.path.getmtime(log_file_path)
                    # 将时间戳转换为datetime对象
                    timestr = datetime.fromtimestamp(last_modified).strftime('%Y-%m-%d %H:%M:%S')
                    # 获取日志文件的大小
                    log_file_size = os.path.getsize(log_file_path)
                    # 将日志文件大小转换为KB
                    log_file_size_kb = round(log_file_size / 1024, 2)
                    # 将日志文件大小转换为MB,保留两位小数
                    log_file_size_mb = round(log_file_size / (1024 * 1024), 2)
                    # 显示信息
                    log_file_size_info = f"{log_file_size_kb}KB" if log_file_size_kb < 1024 else f"{log_file_size_mb}MB"
                    # 将日志文件信息添加到列表中
                    logs_all.append({
                        'log_type': 'inspection',
                        'hostname': hostname,
                        'ip': ip,
                        'last_modified': timestr,
                        'display_name': log_file,
                        'file_name': log_file,
                        'log_file_size': log_file_size_info,
                        'index_dir': foldername
                    })
        # 遍历配置下发日志目录中的所有日志
        for foldername in os.listdir(self.config_logs_dir):
            # 巡检日志目录
            folder_path = os.path.join(self.config_logs_dir, foldername)
            # 搜索巡检日志目录下的.log日志文件
            for log_file in os.listdir(folder_path):
                if log_file.endswith('.log'):
                    log_file_path = os.path.join(folder_path, log_file)
                    hostname = log_file.split('__')[0]
                    ip = log_file.split('__')[1].rstrip('.log')
                    # 获取日志文件的最后修改时间
                    last_modified = os.path.getmtime(log_file_path)
                    # 将时间戳转换为datetime对象
                    timestr = datetime.fromtimestamp(last_modified).strftime('%Y-%m-%d %H:%M:%S')
                    # 获取日志文件的大小
                    log_file_size = os.path.getsize(log_file_path)
                    # 将日志文件大小转换为KB
                    log_file_size_kb = round(log_file_size / 1024, 2)
                    # 将日志文件大小转换为MB,保留两位小数
                    log_file_size_mb = round(log_file_size / (1024 * 1024), 2)
                    # 显示信息
                    log_file_size_info = f"{log_file_size_kb}KB" if log_file_size_kb < 1024 else f"{log_file_size_mb}MB"
                    # 将日志文件信息添加到列表中
                    logs_all.append({
                        'log_type': 'config',
                        'hostname': hostname,
                        'ip': ip,
                        'last_modified': timestr,
                        'display_name': log_file,
                        'file_name': log_file,
                        'log_file_size': log_file_size_info,
                        'index_dir': foldername
                    })
        # 遍历控制台交互日志目录中的所有日志
        for filename in os.listdir(self.terminal_logs_dir):
            if filename.endswith('.log'):
                log_file_path = os.path.join(self.terminal_logs_dir, filename)
                filename_parts = filename.split('__')[0].replace('ssh_','')
                ip = filename_parts.split('_')[-1]
                hostname = filename_parts.replace(f'_{ip}','')
                time_str = filename.split('__')[1].strip('.log')
                #将形如20250224_154458的时间字符串转换为时间戳
                time_stamp = int(time.mktime(time.strptime(time_str, '%Y%m%d_%H%M%S')))
                # 将时间戳转换为时间字符串
                timestr = datetime.fromtimestamp(time_stamp).strftime('%Y-%m-%d %H:%M:%S')
                # 获取日志文件的大小(单位:字节)
                log_file_size = os.path.getsize(log_file_path)
                # 将日志文件大小转换为KB,保留两位小数
                log_file_size_kb = round(log_file_size / 1024, 2)
                # 将日志文件大小转换为MB,保留两位小数
                log_file_size_mb = round(log_file_size / (1024 * 1024), 2)
                # 显示信息
                log_file_size_info = f"{log_file_size_kb}KB" if log_file_size_kb < 1024 else f"{log_file_size_mb}MB"
                #将日志文件信息添加到列表中
                logs_all.append({
                    'log_type': 'terminal_ssh',
                    'hostname': hostname,
                    'ip': ip,
                    'last_modified': timestr,
                    'display_name': f'{filename_parts}.log',
                    'file_name': filename,
                    'log_file_size': log_file_size_info,
                    'index_dir': 'logs'
                })
        # 将列表按照时间戳进行排序
        logs_all.sort(key=lambda x: x['last_modified'], reverse=True)
        return JsonResponse(logs_all, safe=False)
    #@login_required
    def delete(self, request, logfile):
        """删除指定的日志记录"""
        logger.debug(f"调用api删除指定的日志记录: {logfile}")
        index_dir,file_name = logfile.split('--')
        try:
            if index_dir == 'logs':
                logfilepath = os.path.join(self.terminal_logs_dir, file_name)
                if os.path.exists(logfilepath) and os.path.isfile(logfilepath):
                    # 删除整个文件夹及其内容
                    os.remove(logfilepath)
            else:
                logfilepath_inspect = os.path.join(self.inspection_logs_dir,index_dir, file_name)
                logfilepath_config = os.path.join(self.config_logs_dir, index_dir, file_name)
                if os.path.exists(logfilepath_inspect):
                    os.remove(logfilepath_inspect)
                elif os.path.exists(logfilepath_config):
                    os.remove(logfilepath_config)
            return Response({'status': 'success', 'message': '日志记录已删除'}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({'error': '指定的日志记录不存在'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        # 批量删除日志
        logs = request.data.get('logs')
        logger.debug(f"批量删除日志: {logs}")
        for log in logs:
            self.delete(request, log)
        return Response({'status': 'success', 'message': '日志文件删除成功'}, status=status.HTTP_204_NO_CONTENT)


#查看日志内容
class LogContentView(APIView):
    """
    获取日志内容
    """
    def get(self, request, logfile):
        try:
            
            logger.debug(f"调用api获取日志内容1: {logfile}")

            index_dir,file_name = logfile.split('--')
            # 使用 unquote 解码 URL 编码的路径
            if index_dir == 'logs':
                logfile_path = os.path.join(settings.DIR_INFO['LOG_DIR'], file_name)
                logger.debug(f"调用api获取日志内容2: {logfile_path}")
            else:
                logfile_path_inspect = os.path.join(settings.DIR_INFO['REPORT_DIR'], 'inspect',index_dir, file_name)
                logfile_path_config = os.path.join(settings.DIR_INFO['REPORT_DIR'], 'config',index_dir, file_name)
                if os.path.exists(logfile_path_inspect):
                    logfile_path = logfile_path_inspect
                elif os.path.exists(logfile_path_config):
                    logfile_path = logfile_path_config
            logger.debug(f"调用api获取日志内容3: {logfile_path}")
            if not os.path.exists(logfile_path):
                return Response({'error': 'Log file not found'}, status=status.HTTP_404_NOT_FOUND)
                
            with open(logfile_path, 'r', encoding='utf-8') as f:
                # 逐行读取并去掉每行的 \r 符号
                content = ''.join(line.replace('\r', '') for line in f)


            return Response({
                'content': content
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
# 下载日志文件
class LogDownloadView(APIView):
    """
    下载日志
    """
    def get(self, request, logfile):
        try:
            logger.debug(f"调用api下载日志: {logfile}")
            index_dir,file_name = logfile.split('--')
            if index_dir == 'logs':
                log_file_path = os.path.join(settings.DIR_INFO['LOG_DIR'], file_name)
                with open(log_file_path, 'rb') as file:
                        response = HttpResponse(file.read(), content_type='text/plain')
                        response['Content-Disposition'] = f'attachment; filename={logfile}'
                        return response
            else:
                logfile_path_inspect = os.path.join(settings.DIR_INFO['REPORT_DIR'], 'inspect',index_dir, file_name)
                logfile_path_config = os.path.join(settings.DIR_INFO['REPORT_DIR'], 'config',index_dir, file_name)
                if os.path.exists(logfile_path_inspect):
                    with open(logfile_path_inspect, 'rb') as file:
                            response = HttpResponse(file.read(), content_type='text/plain')
                            response['Content-Disposition'] = f'attachment; filename={logfile}'
                            return response
                elif os.path.exists(logfile_path_config):
                    with open(logfile_path_config, 'rb') as file:
                            response = HttpResponse(file.read(), content_type='text/plain')
                            response['Content-Disposition'] = f'attachment; filename={logfile}'
                            return response
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@login_required
def cache_manager(request):
    """缓存管理页面"""
    return render(request, 'devices/cache_manager.html')

class CachesView(APIView):
    """
    缓存管理API
    """
    def get(self, request):
        """获取所有缓存键"""
        try:
            # 直接使用Redis客户端
            redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, password=settings.REDIS_PASSWORD)
            
            # 测试Redis连接
            try:
                redis_client.ping()
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Redis连接失败: {str(e)}'
                }, status=500)
            
            # 获取所有键
            keys = redis_client.keys('*')
            
            # 获取每个键的信息
            cache_info = []
            current_time = int(time.time())
            
            for key in keys:
                try:
                    key = key.decode('utf-8')
                    
                    # 获取键的类型
                    key_type = redis_client.type(key).decode('utf-8')
                    
                    # 获取值
                    value = redis_client.get(key)
                    
                    # 获取TTL
                    ttl = redis_client.ttl(key)
                    
                    # 计算过期时间
                    expire_at = current_time + ttl if ttl > 0 else None
                    
                    # 格式化过期时间
                    expire_time = datetime.fromtimestamp(expire_at).strftime('%Y-%m-%d %H:%M:%S') if expire_at else '永久'
                    
                    # 将TTL转换为时分秒格式
                    if ttl > 0:
                        hours = ttl // 3600
                        minutes = (ttl % 3600) // 60
                        seconds = ttl % 60
                        ttl_str = f"{hours}小时{minutes}分{seconds}秒"
                    else:
                        ttl_str = '永久'
                    
                    # 计算大小
                    size = len(value) if value else 0
                    
                    cache_info.append({
                        'key': key,
                        'type': key_type,
                        'expire_at': expire_time,
                        'ttl': ttl_str,
                        'size': size
                    })
                    
                except Exception as e:
                    continue
            
            return JsonResponse({
                'status': 'success',
                'data': cache_info
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'获取缓存信息时发生错误: {str(e)}'
            }, status=500)
    def delete(self, request):
        """删除指定的缓存键"""
        try:
            key = request.POST.get('key')
            if not key:
                return JsonResponse({
                    'status': 'error',
                    'message': '未提供缓存键'
                }, status=400)
            
            # 删除缓存
            logger.debug(f"删除缓存: {key}")
            # 同时从Django缓存和Redis中删除
            cache.delete(key)
            redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, password=settings.REDIS_PASSWORD)
            redis_client.delete(key)
            logger.debug(f"缓存键 {key} 已成功删除")  # 添加成功日志
            return JsonResponse({
                'status': 'success',
                'message': f'缓存键 {key} 已成功删除'
            })
        except Exception as e:
            logging.error(f"删除缓存时发生错误: {str(e)}")  # 添加错误日志
            return JsonResponse({
                'status': 'error',
                'message': f'删除缓存时发生错误: {str(e)}'
            }, status=500)

    def put(self, request):
        """获取缓存键的值"""
        try:
            key = request.data.get('key')
            if not key:
                return JsonResponse({
                    'status': 'error',
                    'message': '未提供缓存键'
                }, status=400)
            
            # 获取缓存值
            redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, password=settings.REDIS_PASSWORD)
            value = redis_client.get(key)
            
            if value is None:
                return JsonResponse({
                    'status': 'error',
                    'message': '缓存键不存在'
                }, status=404)
            
            # 尝试解析值
            try:
                # 首先尝试pickle反序列化
                import pickle
                try:
                    unpickled_value = pickle.loads(value)
                    value = str(unpickled_value)
                except (pickle.UnpicklingError, TypeError):
                    # 如果pickle反序列化失败，尝试其他方式
                    try:
                        # 尝试解码为字符串
                        decoded_value = value.decode('utf-8')
                        try:
                            # 尝试解析为JSON
                            json_value = json.loads(decoded_value)
                            value = json.dumps(json_value, ensure_ascii=False, indent=2)
                        except json.JSONDecodeError:
                            # 如果不是JSON，直接使用解码后的字符串
                            value = decoded_value
                    except UnicodeDecodeError:
                        # 如果解码失败，可能是二进制数据，转换为十六进制并添加\x前缀
                        hex_value = value.hex()
                        value = '\\x' + '\\x'.join(hex_value[i:i+2] for i in range(0, len(hex_value), 2))
            except Exception as e:
                logging.error(f"解析缓存值时发生错误: {str(e)}")
                # 如果所有解析方式都失败，显示原始十六进制
                hex_value = value.hex()
                value = '\\x' + '\\x'.join(hex_value[i:i+2] for i in range(0, len(hex_value), 2))
            
            return JsonResponse({
                'status': 'success',
                'data': {
                    'key': key,
                    'value': value
                }
            })
        except Exception as e:
            logging.error(f"获取缓存值时发生错误: {str(e)}")  # 添加错误日志
            return JsonResponse({
                'status': 'error',
                'message': f'获取缓存值时发生错误: {str(e)}'
            }, status=500)
@login_required
def configs_list(request):
    """配置下发"""
    return render(request, 'devices/configs.html')

# 下发命令列表管理API
class ConfigsView(APIView):
    """
    处理下发命令列表的增删改查操作。
    """
    permission_classes = [IsAuthenticatedForWriteOnly]
    configs_path = os.path.join(settings.DIR_INFO['CONF_DIR'], 'netconf')

    def get(self,request,configs_id=None):
        """
        获取特定下发命令列表模板的详细信息。
        ---
        response:
            200: 返回下发命令列表模板详细信息
            404: 未找到下发命令列表模板
        """
        configs_list = []
        #configs_path = os.path.join(settings.DIR_INFO['CONF_DIR'], 'netconf')
        for file in os.listdir(self.configs_path):
            if file.endswith('.conf'):
                #print(file)
                configs_id_local = file.rstrip('.conf')
                commands_name = configs_id_local.split('__')[1]
                os_type = configs_id_local.split('__')[0]
                with open(os.path.join(self.configs_path, file), 'r') as f:
                    configs_text = f.read()
                if configs_id == configs_id_local:
                    return Response({'id':configs_id_local,'os_type': os_type, 'commands_name': commands_name, 'commands_text': configs_text})
                configs_list.append({
                        'id':configs_id_local,
                        'os_type': os_type,
                        'commands_name': commands_name,
                        'commands_text': configs_text
                    })
        logger.debug(f"configs_list: {configs_list}")
        return Response(configs_list)


    def post(self, request):
        """
        创建新的textfsm模板。
        ---
        request:
            template_text: 模板文本
        response:
            201: 创建成功
            400: 请求数据无效
        """
        commands_text = request.data.get('commands_text')
        commands_name = request.data.get('commands_name')
        os_type = request.data.get('os_type')

        if not commands_text:
            return Response({'error': '模板内容不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        # 将模板文本写入文件
        file_path = os.path.join(self.configs_path, f"{os_type}__{commands_name}.conf")
        with open(file_path, 'w') as f:
            f.write(commands_text)

        return Response({'message': '模板创建成功'}, status=status.HTTP_201_CREATED)

    def put(self, request):
        """
        更新现有textfsm模板。
        ---
        request:
            template_text: 模板文本
        response:
            200: 更新成功
            404: 未找到textfsm模板
        """
        logger.debug(f"put {request.data}")
        commands_text = request.data.get('commands_text')
        commands_name = request.data.get('commands_name')
        os_type = request.data.get('os_type')

        file_path = os.path.join(self.configs_path, f"{os_type}__{commands_name}.conf")

        if not os.path.exists(file_path):
            return Response({'error': '模板文件不存在'}, status=status.HTTP_404_NOT_FOUND)

        configs_text = request.data.get('template_text')
        with open(file_path, 'w') as f:
            f.write(commands_text)

        return Response({'message': '模板更新成功'}, status=status.HTTP_200_OK)

    def delete(self, request, configs_id):
        """
        删除特定textfsm模板。
        ---
        response:
            204: 删除成功
            404: 未找到textfsm模板
        """
        file_path = os.path.join(self.configs_path, f"{configs_id}.conf")

        if os.path.exists(file_path):
            os.remove(file_path)
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({'error': '模板文件不存在'}, status=status.HTTP_404_NOT_FOUND)

@login_required
def devices_config(request):
    """配置下发"""
    return render(request, 'devices/devices_config.html')

# 设备巡检列表
@CustomLoginRequired
def devices_configs(request):
    """
    设备巡检列表页面
    """
    return render(request, 'devices/devices_configs.html')

# 设备配置下发API
class DevicesConfigsView(APIView):
    """
    查询和删除设备巡检结果API
    """
    permission_classes = [IsAuthenticatedForWriteOnly]
    # 设置缓存
    cache_key = 'devices_configs'
    cache_timeout = 60*60*24
    history_dir = os.path.join(settings.DIR_INFO['REPORT_DIR'], 'config')

    def get(self, request):
        """获取设备巡检历史记录"""
        logger.debug(f"调用api获取设备巡检历史记录")
        # 从缓存中获取
        histories = cache.get(self.cache_key)
        if not histories:
            histories =[]
            #history_dir = os.path.join(settings.BASE_DIR, 'config_results')

            # 遍历目录中的所有文件夹
            for foldername in os.listdir(self.history_dir):
                folder_path = os.path.join(self.history_dir, foldername)
                if os.path.isdir(folder_path):
                    index_file_path = os.path.join(folder_path, 'index.json')
                    if os.path.exists(index_file_path):
                        with open(index_file_path, 'r', encoding='utf-8') as file:
                            try:
                                # 读取并解析 JSON 文件
                                data = json.load(file)
                                # 假设 JSON 文件中有 'id', 'device', 'command', 'result', 'timestamp' 字段
                                histories.append({
                                    'id': foldername,  # 使用文件夹名作为 ID
                                    'device_ids': data.get('device_ids', '未知设备'),
                                    'command_ids': data.get('command_ids', '无命令'),
                                    'server_commands':  data.get('server_commands', '无命令'),
                                    'network_commands':  data.get('network_commands', '无命令'),
                                    'status': data.get('status', '无结果'),
                                    'start_time': data.get('start_time', '未知时间'),
                                    'end_time': data.get('end_time', '未知时间'),
                                })
                            except json.JSONDecodeError:
                                continue  # 如果 JSON 解析失败，跳过该文件
                    else:
                        # 如果index.json文件不存在，则删除整个文件夹
                        import shutil
                        shutil.rmtree(folder_path)

            histories.sort(key=lambda x: x['end_time'], reverse=True)
            # 缓存结果
            cache.set(self.cache_key, histories, self.cache_timeout)
            logger.debug(f"从数据库中获取设备巡检历史记录")
        else:
            logger.debug(f"从缓存中获取设备巡检历史记录")
        return JsonResponse({'histories': histories})
    #@login_required
    def delete(self, request, history_id):
        """删除指定的历史记录"""
        logger.debug(f"调用api删除指定的历史记录: {history_id}")
        # 清除缓存
        cache.delete(self.cache_key)
        try:
            folder_path = os.path.join(self.history_dir, history_id)
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                # 删除整个文件夹及其内容
                import shutil
                shutil.rmtree(folder_path)
                return Response({'status': 'success', 'message': '历史记录已删除'}, status=status.HTTP_204_NO_CONTENT)
            else:
                return Response({'error': '指定的历史记录不存在'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        # 批量删除巡检记录
        history_ids = request.data.get('ids')
        logger.debug(f"批量删除x: {history_ids}")
        for history_id in history_ids:
            self.delete(request, history_id)
        cache.delete(self.cache_key)
        return Response({'status': 'success', 'message': '文件删除成功'}, status=status.HTTP_204_NO_CONTENT)

# 获取巡检报告
def devices_config_report(request, report_id):
    """
    获取巡检报告
    """
    logger.debug(f"调用api获取巡检报告: {report_id}")
    filepath = os.path.join(settings.DIR_INFO['REPORT_DIR'],'config', f"{report_id}/index.html")
    logger.debug(f"查看报告: {filepath}")
    if os.path.exists(filepath): 
        return FileResponse(open(filepath, 'rb'), filename=f"report_{report_id}.html")
    else:
        filepath = os.path.join(settings.DIR_INFO['REPORT_DIR'],'config',  f"{report_id}/index.html")
        if os.path.exists(filepath): 
         return FileResponse(open(filepath, 'rb'), filename=f"report_{report_id}.html")
    return HttpResponseNotFound("报告不存在")
