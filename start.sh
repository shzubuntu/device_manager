#!/bin/bash

# 添加调试日志
echo "=== 开始执行start.sh初始化脚本 ==="
date
# 打印环境变量（敏感信息已脱敏）
echo "环境变量检查：MYSQL_HOST=${MYSQL_HOST}, PYTHONPATH=${PYTHONPATH}"
# 检查关键文件是否存在
echo "文件检查："
ls -la /app/authentication/apps.py
ls -la /app/device_manager/settings.py
# 创建必要的目录
mkdir -p staticfiles

# 设置环境变量
#export DJANGO_SETTINGS_MODULE=device_manager.settings_docker
export PYTHONPATH=$PYTHONPATH:$(pwd)

# 收集静态文件（添加错误处理）
echo "收集静态文件..."
if ! python manage.py collectstatic --noinput; then
    echo "ERROR: 静态文件收集失败"
    exit 1
fi

# 检查数据库迁移
echo "检查数据库迁移..."
python manage.py makemigrations

# 等待数据库就绪
echo "等待数据库连接... 当前参数：host=${MYSQL_HOST} user=${MYSQL_USER}"
counter=0
while ! mysqladmin ping -h"${MYSQL_HOST}" -u"${MYSQL_USER}" -p"${MYSQL_PASSWORD}" --silent; do
    sleep 2
    counter=$((counter + 1))
    if [ $counter -ge 30 ]; then
        echo "错误：等待数据库超时（60秒）"
        exit 1
    fi
done
echo "数据库连接成功！"
echo "数据库已就绪，开始应用迁移..."
python manage.py migrate --verbosity 3
echo "数据库迁移完成，准备启动应用..."

# 创建超级用户
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "检查超级用户是否存在..."
    # 使用Python代码检查用户是否存在
    if ! python -c "import django; django.setup(); from django.contrib.auth.models import User; exit(0) if User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists() else exit(1)"; then
        echo "创建超级用户..."
        python manage.py createsuperuser --noinput
    else
        echo "超级用户 '$DJANGO_SUPERUSER_USERNAME' 已存在，跳过创建..."
    fi
else
    echo "未配置超级用户环境变量，跳过创建..."
fi

# 启动应用
echo "启动应用..."
echo "正在启动Gunicorn服务..."
daphne -b 0.0.0.0 -p 8000 device_manager.asgi:application

echo "应用服务已启动，监听端口：8000"