# 设备管理系统

## 项目概述

设备管理系统是一个基于Django框架开发的网络设备管理平台，用于集中管理各种网络设备，如服务器、交换机、路由器和防火墙。系统支持多种连接协议（SSH、Telnet、Serial），并提供了RESTful API和WebSocket实时通信功能，方便用户进行设备管理和监控。

## 架构说明

### 技术栈

- **后端框架**：Django 5.1.5
- **API框架**：Django REST Framework
- **WebSocket支持**：Daphne + Channels + Redis
- **数据库**：MariaDB 11.3
- **缓存/消息队列**：Redis
- **Web服务器**：Nginx + Gunicorn
- **容器化**：Docker + Docker Compose
- **编排工具**：Kubernetes (可选)

### 系统架构

```
┌───────────────────────────────────────────────────────────┐
│                       客户端浏览器                          │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                       Nginx 反向代理                        │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                Django ASGI 应用服务器                       │
│                   (Daphne + Gunicorn)                       │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────┴─────────────────────────────────────────┐
│                     应用功能模块                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  设备管理   │  │  认证管理   │  │  API服务    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐   ┌────────────┐
│              MariaDB 数据库                 │   │  Redis     │
│  (设备信息、用户信息、命令模板等)           │   │ (缓存、WebSocket消息) │
└─────────────────────────────────────────────┘   └────────────┘
```

### 项目结构

```
device_manager/
├── authentication/          # 认证管理应用
├── device_manager/          # 主项目配置
├── devices/                 # 设备管理应用
│   ├── conf/               # 配置文件目录
│   ├── consumers/          # WebSocket消费者
│   ├── management/         # 自定义管理命令
│   ├── tools/              # 工具函数
│   └── var/                # 变量和日志
├── logs/                   # 日志目录
├── nginx/                  # Nginx配置
├── static/                 # 静态文件
├── templates/              # 模板文件
├── .env                    # 环境变量配置
├── docker-compose.yml      # Docker Compose配置
├── Dockerfile              # Docker镜像构建文件
├── manage.py               # Django管理脚本
└── requirements.txt        # Python依赖
```

## 部署步骤

### 1. 环境准备

- 安装Docker和Docker Compose
- 提前下载所需的docker镜像 
    nginx:latest
    alpine:latest
    redis:alpine
    mariadb:11.3
- 确保80、3306、6379端口未被占用

### 2. 配置环境变量

编辑 `.env` 文件，设置必要的环境变量

### 3. 一键部署容器并启动服务
./build.sh

### 4. 一键清理容器并停止服务
./clean.sh

## 使用说明

### 1. 访问系统

系统部署成功后，可以通过以下方式访问：

- **Web界面**：http://localhost
- **API文档**：http://localhost/api/
- **管理后台**：http://localhost/admin/

### 2. 基本操作

#### 2.1 添加设备

1. 登录系统
2. 点击左侧菜单的"设备管理" -> "添加设备"
3. 填写设备信息：
   - 设备名称
   - IP地址
   - 端口号
   - 用户名
   - 密码
   - 设备类型（服务器、交换机、路由器、防火墙）
   - 连接协议（SSH、Telnet、Serial）
   - SSH密钥（可选，仅SSH协议）
4. 点击"保存"按钮

#### 2.2 管理设备

- **查看设备列表**：点击左侧菜单的"设备管理" -> "设备列表"
- **编辑设备**：在设备列表中点击设备的"编辑"按钮
- **删除设备**：在设备列表中点击设备的"删除"按钮
- **批量操作**：支持批量删除设备

#### 2.3 设备操作

- **连接设备**：在设备列表中点击设备的"连接"按钮，进入设备控制台
- **执行命令**：在设备控制台中输入命令，点击"执行"按钮
- **查看命令历史**：在设备控制台中查看历史命令记录

### 3. API使用

系统提供了RESTful API，方便集成到其他系统中。API基础路径为 `/api/`，主要API包括：

#### 3.1 设备管理API

- **GET /api/devices/**：获取设备列表
- **POST /api/devices/**：添加设备
- **GET /api/devices/{id}/**：获取设备详情
- **PUT /api/devices/{id}/**：更新设备信息
- **DELETE /api/devices/{id}/**：删除设备

#### 3.2 认证API

- **POST /auth/login/**：用户登录
- **POST /auth/logout/**：用户登出
- **GET /auth/user/**：获取当前用户信息

#### 3.3 WebSocket API

- **ws://localhost/ws/device/{id}/**：设备实时通信WebSocket连接

### 4. 日志管理

系统日志存放在 `logs/` 目录下，主要包括：

- **nginx/**：Nginx访问日志和错误日志
- **django/**：Django应用日志
- **mysql/**：MySQL数据库日志

## 开发指南

### 1. 开发环境搭建

```bash
# 安装依赖
pip install -r requirements.txt

# 配置数据库连接
# 修改 device_manager/settings.py 中的 DATABASES 配置

# 执行数据库迁移
python manage.py migrate

# 创建超级用户
python manage.py createsuperuser

# 启动开发服务器
python manage.py runserver
```

### 2. 代码结构

#### 2.1 设备模型

设备模型定义在 `devices/models.py` 中，主要包括：

- **Device**：设备基本信息，如名称、IP地址、用户名、密码、设备类型等
- **OSType**：操作系统类型
- **Command**：命令模板

#### 2.2 视图函数

视图函数定义在 `devices/views.py` 中，主要包括：

- 设备管理视图
- 设备操作视图
- API视图

#### 2.3 WebSocket消费者

WebSocket消费者定义在 `devices/consumers.py` 中，用于处理设备实时通信。

### 3. 测试

```bash
# 运行单元测试
python manage.py test

# 运行特定应用的测试
python manage.py test devices

# 运行特定测试用例
python manage.py test devices.tests.DeviceTestCase
```

## 系统监控与维护

### 1. 监控指标

- **CPU使用率**：通过 `docker stats` 命令查看容器CPU使用率
- **内存使用率**：通过 `docker stats` 命令查看容器内存使用率
- **磁盘空间**：通过 `df -h` 命令查看磁盘空间使用情况
- **日志监控**：通过 `tail -f logs/*/*.log` 命令实时查看日志

### 2. 常见问题排查

#### 2.1 服务无法启动

- 检查端口是否被占用：`netstat -tlnp`
- 检查日志文件：`tail -f logs/*/*.log`
- 检查容器状态：`docker-compose logs -f`

#### 2.2 数据库连接失败

- 检查MySQL容器是否运行：`docker-compose ps db`
- 检查MySQL日志：`tail -f logs/mysql/error.log`
- 检查数据库连接配置：`cat .env`

#### 2.3 Redis连接失败

- 检查Redis容器是否运行：`docker-compose ps redis`
- 检查Redis日志：`docker-compose logs redis`
- 检查Redis连接配置：`cat .env`

## 安全建议

1. **修改默认密码**：首次登录后，立即修改超级用户密码
2. **限制访问IP**：在生产环境中，限制允许访问系统的IP地址
3. **启用HTTPS**：配置Nginx启用HTTPS，加密数据传输
4. **定期备份数据**：定期备份数据库和配置文件
5. **更新依赖**：定期更新Python依赖，修复安全漏洞
6. **配置防火墙**：配置服务器防火墙，只开放必要的端口

## 版本历史

- **v1.0.0**：初始版本，实现基本的设备管理功能
- **v1.1.0**：添加WebSocket实时通信功能
- **v1.2.0**：支持多种连接协议（SSH、Telnet、Serial）

## 贡献指南

欢迎提交Issue和Pull Request，贡献代码。

### 提交代码前，请确保：

1. 代码符合PEP 8规范
2. 所有测试用例通过
3. 添加必要的文档
4. 遵循Git提交规范

## 许可证

MIT License

## 联系方式

如有问题或建议，请通过以下方式联系：

- 邮箱：shzubuntu@gmail.com
- GitHub：https://github.com/shzubuntu/device_manager
