import html 
import logging 
from datetime import datetime 
from pathlib import Path 
from jinja2 import Environment, FileSystemLoader, select_autoescape 
from devices.models import Device
from devices.serializers import DeviceSerializer
from django.conf import settings
import os
import sys
#from .tools_songhz import list_write_csv
from devices.tools.tools_songhz import list_write_csv
import csv

class ThemeManager:
    """多主题样式加载器"""
    THEMES = {
        'default': 'css/report.css', 
        'dark': 'css/dark_mode.css', 
        'print': 'css/print.css' 
    }
 
    def get_theme_path(self, theme_name: str) -> str:
        return self.THEMES.get(theme_name,  self.THEMES['default'])


class ReportGenerator:
    """专业报告生成器（完整实现版）"""
    
    def __init__(self):
        # 初始化配置 
        self.template_paths  = [
            '/opt/app/templates',
            os.path.join(settings.BASE_DIR, 'devices/conf/template')
        ]
        # 静态资源路径
        self.static_paths  = [
            os.path.join(settings.BASE_DIR,  'static')
        ]
        self.report_dir = ''
        self.textfsm_csv_dir = os.path.join(settings.DIR_INFO['REPORT_DIR'],'textfsm')
        self.logger  = self._init_logger()

    def _get_static_url(self, filename: str) -> str:
        """智能定位静态资源"""
        for path in self.static_paths: 
            full_path = Path(path) / filename 
            if full_path.exists(): 
                return f"file://{full_path.absolute()}" 
        return ""

    def _format_timestamp(self, value, format_str: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
        """
        时间戳格式化（支持多种输入类型）
        :param value: 输入时间（支持datetime、字符串、Unix时间戳）
        :param format_str: 输出格式（默认：2025-02-20 16:43:00 UTC+8）
        :return: 格式化后的时间字符串 
        """
        if not value:
            return "N/A"
            
        try:
            # 统一转换为datetime对象 
            if isinstance(value, datetime):
                dt = value 
            elif isinstance(value, (int, float)):
                dt = datetime.fromtimestamp(value) 
            elif isinstance(value, str):
                if value.isdigit(): 
                    dt = datetime.fromtimestamp(int(value)) 
                else:
                    dt = datetime.fromisoformat(value) 
            else:
                raise ValueError("不支持的时间格式")
            
            # 自动添加时区信息（如未包含）
            if not dt.tzinfo: 
                dt = dt.astimezone()   # 使用系统时区 
                
            return dt.strftime(format_str) 
            
        except Exception as e:
            self.logger.warning(f" 时间格式化失败: {str(e)}")
            return f"Invalid Time: {str(value)}"

    def generate_report_file(self, report_id, data, execute_type,output_format='html'):
        """
        主入口方法 
        :param report_id: 报告唯一标识 
        :param data: 输入数据字典 
        :param output_format: 输出格式（html/pdf）
        :return: 生成文件路径 
        """
        try:
            self.report_dir = os.path.join(settings.DIR_INFO['REPORT_DIR'],execute_type)
            if not os.path.exists(self.report_dir):
                os.makedirs(self.report_dir)
            # 上下文构建 
            context = self._build_report_context(report_id, data)
            # 模板渲染 
            template = self._get_report_template()
            # 渲染模板
            html_content = template.render(context)
            # 文件输出到html
            output_path = self._write_output_file(report_id, html_content)

            #生成textfsm解析文件
            if execute_type == 'inspect':
                self.config_textfsm(report_id,data)
            #self.config_textfsm(report_id,data)
            # 格式转换 
            if output_format == 'pdf':
                self.export_as_pdf(output_path) 

                
            return output_path 
        except Exception as e:
            self.logger.error(f" 报告生成失败: {str(e)}")
            raise 
    
    # --------------------------
    # 模板处理模块 
    # --------------------------


    def _get_report_template(self):
        """增强版模板加载方法"""
        env = Environment(
            loader=FileSystemLoader(self.template_paths), 
            extensions=['jinja2.ext.do'],   # 启用扩展功能 
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True 
        )
            
        env.filters.update({
            'format_time': self._format_timestamp 
        })
        # 添加静态路径处理函数 
        env.globals.update({ 
            'static': self._get_static_url,
            'now': datetime.now().strftime("%Y-%m-%d") 
        })
        
        return env.get_template('report2.html') 
 
    # --------------------------
    # 数据处理模块 
    # --------------------------
    def _build_report_context(self, report_id, data):
        """构建模板上下文"""
        return {
            'static_url': self._get_static_url,
            'selected_theme': ThemeManager().get_theme_path(data.get('theme')), 
            'meta': self._build_metadata(report_id),
            'timing': self._process_timing(data),
            'content': self._process_content(data),
            'statistics': self._generate_statistics(data),
            'results': self._process_results(data)
        }
    def _process_results(self, data):
        """结果数据处理"""
        return data.get('results',  [])

    def _generate_statistics(self, data):
        """生成统计数据"""
        response = {}
        devices = data.get('devices',  [])
        commands = data.get('commands',  [])
        items = data.get('items',  {})
        commands_length = 0
        for item in items:
            os_type_command_length = len(items[item]['commands'])
            os_type_devices_length = len(items[item]['devices'])
            commands_length += os_type_command_length*os_type_devices_length
        return {
            "device_count": len(devices),
            "success_count": sum(1 for d in data['results'] if d.get('status') == 'success'),
            "command_types": commands_length,
            #"success_rate": int(sum(1 for d in data['results'] if d.get('status') == 'success')/(len(devices)*len(commands))*100),
            #'os_types': len(items.keys())
        }
    def _build_metadata(self, report_id):
        """增强型元数据构建"""
        return {
            "report_id": report_id,
            "system_metadata": {
                "platform": self._get_platform_info(),
                "generator_hash": self.__class__.__hash__(self)
            },
            "generated_time": datetime.now().isoformat(),
            "timestamps": {
                "start": datetime.now().isoformat(), 
                "timezone": "UTC+8"
            }
        }
    def _get_platform_info(self):
        """获取运行平台信息"""
        return {
            "os": os.name, 
            "python_version": sys.version
        }
    def _process_timing(self, data):
        """时间数据处理"""
        try:
            start = datetime.fromisoformat(data['start_time']) 
            end = datetime.fromisoformat(data['end_time']) 
            return {
                'start': start.strftime("%Y-%m-%d  %H:%M:%S"),
                'end': end.strftime("%Y-%m-%d  %H:%M:%S"),
                'duration': self._calculate_duration(start, end),
                'timezone': start.astimezone().tzinfo.tzname(None) 
            }
        except Exception as e:
            self.logger.warning(f" 时间处理异常: {str(e)}")
            return {'error': '时间数据无效'}
 
    def _process_content(self, data):
        """内容安全处理"""
        os_commands = []
        os_devices = []
        items = data.get('items',  {})
        for item in items:
            os_commands.append({
                'os_type': item,
                'commands':items[item]['commands']
            })  
            os_devices.append({
                'os_type': item,
                'devices':items[item]['devices']
            })
        return {
            'devices': [self._sanitize_device(d) for d in data.get('devices',  [])],
            'commands': data.get('commands',  []),
            'os_commands': os_commands,
            'os_devices': os_devices
        }
 
    # --------------------------
    # 工具方法模块 
    # --------------------------
    def _init_logger(self):
        """初始化日志配置"""
        logger = logging.getLogger(__name__) 
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter) 
        logger.addHandler(handler) 
        return logger 
 
    def _calculate_duration(self, start, end):
        """计算持续时间"""
        delta = end - start 
        response = ''
        minutes = (delta.seconds//60)%60
        if minutes > 0:
            response += f"{minutes}m"
        seconds = delta.seconds%60
        if seconds > 0:
            response += f"{seconds}s"
        return response 
 
    def _sanitize_device(self, device):
        """设备信息清洗"""
        device = Device.objects.get(id=device)
        serializer = DeviceSerializer(device)

        return {
            'name': html.escape(serializer.data.get('name')),
            'type': html.escape(serializer.data.get('device_type')),
            'status': serializer.data.get('status')
        }
 
    # --------------------------
    # 输出处理模块 
    # --------------------------
    def _write_output_file(self, report_id, content):
        """写入输出文件"""
        # 定义输出路径
        output_path = Path(f"{self.report_dir}/{report_id}/index.html")
        output_path.parent.mkdir(exist_ok=True) 
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content) 
        return output_path 
 
    def export_as_pdf(self, html_path):
        """PDF转换方法"""
        # 需要安装pdfkit 
        import pdfkit 
        pdfkit.from_file(str(html_path),  str(html_path.with_suffix('.pdf'))) 

    def config_textfsm(self, report_id, data):
        """配置textfsm解析文件"""
        print("textfsm解析开始",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        # 定义textfsm解析文件的输出路径
        output_path = self.textfsm_csv_dir
        #output_path = f'{output_path}/{report_id}'
        # 需要安装textfsm
        import textfsm
        # 获取结果列表
        results = data.get('results', [])
        # 遍历结果列表
        for command_result in results:
            # 获取设备信息
            device_name = command_result.get('device', '')
            # 获取设备ip
            device_ip = command_result.get('device_ip', '')
            # 获取命令信息 
            command = command_result.get('command', '')
            # 获取结果信息
            command_output = command_result.get('result', '')
            # 获取os_type信息
            os_type = command_result.get('os_type', '')
            # 获取更新时间
            update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # csv文件附加字段
            extra_datas = {
                'device_name': device_name,
                'device_ip': device_ip,
                'update_time': update_time
            }
            if 'huawei' in os_type:
                os_type = 'huawei_vrp'
            # 判断是否存在textfsm解析文件
            textfsm_path = os.path.join(settings.DIR_INFO['CONF_DIR'],'textfsm', f"{os_type}_{command.replace(' ', '_')}.textfsm")
            if os.path.exists(textfsm_path):
                textfsm_result = []
                # 定义textfsm解析文件的输出文件名
                output_file_name = f"{os_type}_{command.replace(' ', '_')}.csv"
                # 读取textfsm解析文件
                with open(textfsm_path, 'r', encoding='utf-8') as template_file:
                    fsm = textfsm.TextFSM(template_file)
                    textfsm_result = fsm.ParseText(command_output)
                # 将解析结果写入csv文件
                if len(textfsm_result) > 0:
                    list_write_csv(os.path.join(output_path,output_file_name),textfsm_result,fsm.header,extra_datas)
                    # 更新解析数据库文件总表
                    self.update_textfsm_database(os_type,command,textfsm_result,fsm.header,extra_datas)
            else:
                continue
        print("textfsm解析结束")

    def update_textfsm_database(self, os_type, command, textfsm_result, headers, extra_datas):
        """更新textfsm解析数据库文件"""    
        # 获取textfsm解析数据库文件
        textfsm_database = os.path.join(self.textfsm_csv_dir, f"{os_type}_{command.replace(' ', '_')}.csv")
        # 读取textfsm解析数据库文件
        list_write_csv(textfsm_database,textfsm_result,headers,extra_datas)



