from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

urlpatterns = [
    # 缓存管理
    path('devices/caches_list/', views.cache_manager, name='caches_list'),
    path('devices/caches/', views.CachesView.as_view(), name='caches_list_api'),

    # csv文件管理
    path('csv/files/', views.list_csv_files, name='list_csv_files'),
    path('csv/files/download/<path:file_path>/', views.download_csv_file, name='download_csv_file'),
    path('csv/files/view/<path:file_path>/', views.view_csv_file, name='view_csv_file'),

    # OS类型管理测试
    path('os_types_list/', views.OSTypesList, name='os_types_list'),  # 主页
    path('os_types/', views.OSTypesViewSet.as_view({'get': 'list', 'post': 'create', 'delete': 'destroy'}), name='os_types_list'),
    path('os_types/<int:pk>/', views.OSTypesViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='os_types_detail'),
    path('os_types/import/', views.import_os_types, name='import_os_types'),  # 批量导入
    path('os_types/export/', views.export_os_types, name='export_os_types'),  # 批量导出

    # 命令管理测试
    path('commands_list/', views.CommandsList, name='commands_list'),  # 主页
    path('commands/', views.CommandsViewSet.as_view({'get': 'list', 'post': 'create', 'delete': 'destroy'}), name='commands_list_api'),
    path('commands/<int:pk>/', views.CommandsViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='commands_detail_api'),
    path('commands/import/', views.import_commands, name='import_commands'),  # 批量导入 
    path('commands/export/', views.export_commands, name='export_commands'),  # 批量导出
    # textfsm模板管理测试
    path('textfsm/<str:os_type>/<str:command_text>/', views.TextFSMView.as_view(), name='textfsm_detail'),
    path('textfsmcsv/<str:os_type>/<str:command_text>/', views.TextFSMCsvView.as_view(), name='textfsmcsv_detail'),
    path('view_textfsm_result/<int:command_id>/', views.view_textfsm_result, name='view_textfsm_result'),
    # 设备管理主页
    path('', views.DevicesList, name='devices_list'),
    # 设备管理API
    path('devices/', views.DevicesViewSet.as_view({'get': 'list', 'post': 'create', 'delete': 'destroy'}), name='devices_list_api'),
    path('devices/<int:pk>/', views.DevicesViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='devices_detail_api'), 
    # 更新所有设备状态
    path('devices/update_status/', views.devices_update_status, name='devices_update_status'),
    # 设备管理导出
    path('devices/export/', views.export_devices, name='export_devices'),
    # 设备管理导入
    path('devices/import/', views.import_devices, name='import_devices'),
    # 设备巡检下发页面
    path('devices/inspect/', views.devices_inspect, name='devices_inspect'),
    # 设备巡检记录及管理API
    path('devices/inspections_list/', views.devices_inspections, name='devices_inspections'),
    path('devices/inspections/', views.DevicesInspectionsView.as_view(), name='devices_inspections_api'),
    path('devices/inspections/<str:history_id>/', views.DevicesInspectionsView.as_view(), name='devices_inspections_api_detail'),
    # 获取巡检报告
    path('devices/inspections/<uuid:report_id>/download/', views.devices_inspect_report, name='download_report'),
    # 设备列表页面点击连接进入终端交互页面
    path('device/terminal_simple/<int:device_id>/', views.TerminalSimpleView, name='terminal_simple'), # 终端
    # 独立终端连接交互页面
    path('device/terminal_single/', views.TerminalSingleView.as_view(), name='terminal_single'), # 独立终端连接交互页面
    # 连接串口
    path('device/serial/', views.SerialTerminalView, name='terminal_serial'), # 串口终端
    # 获取串口列表
    path('api/get_serial_ports/', views.get_serial_ports, name='get_serial_ports'), # 获取串口列表

    #sftp文件传输
    path('sftp/<int:device_id>/', views.SFTPView.as_view(), name='sftp'), # sftp文件传输页面
    path('sftp/files/<int:device_id>/', views.SftpFileManager.as_view(), name='sftp-files'), # 远程文件管理
    path('sftp/upload/<int:device_id>/', views.SftpFileUpload.as_view(), name='sftp-upload'), # 上传文件
    path('sftp/download/<int:device_id>/', views.SftpFileDownload.as_view(), name='sftp-download'), # 下载文件

    # 日志管理中心
    #path('log_center/', views.LogCenterView.as_view(), name='log_center'), # 日志中心
    path('devices/log_center/', views.devices_logs, name='devices_logs'),
    path('devices/logs/', views.DevicesLogsView.as_view(), name='devices_logs_api'),
    path('devices/logs/<str:logfile>/', views.DevicesLogsView.as_view(), name='devices_logs_api_detail'),
    # 查看日志内容
    path('devices/log_content/<str:logfile>/', views.LogContentView.as_view(), name='log_content_api_detail'),
    path('devices/log_download/<str:logfile>/', views.LogDownloadView.as_view(), name='log_download_api_detail'),
    # textfsm模板测试页面
    path('textfsm/test/', views.TextFSMTestView.as_view(), name='textfsm_test'),

    # 下发命令列表管理
    path('configs_list/', views.configs_list, name='configs_list'),
    path('configs/', views.ConfigsView.as_view(), name='configs_api'),
    path('configs/<str:configs_id>/', views.ConfigsView.as_view(), name='textfsmcsv_detail'),
    path('devices/config/', views.devices_config, name='devices_config'),
    #path('view_textfsm_result/<int:command_id>/', views.view_textfsm_result, name='view_textfsm_result'),
        # 设备巡检记录及管理API
    path('devices/configs_list/', views.devices_configs, name='devices_configs'),
    path('devices/configs/', views.DevicesConfigsView.as_view(), name='devices_configs_api'),
    path('devices/configs/<str:history_id>/', views.DevicesConfigsView.as_view(), name='devices_configs_api_detail'),
    # 获取配置下发报告
    path('devices/configs/<uuid:report_id>/download/', views.devices_config_report, name='download_report'),

]

urlpatterns += router.urls
