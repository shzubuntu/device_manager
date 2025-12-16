# ...existing code...
#!/bin/bash
set -e

echo "=== 开始执行start.sh初始化脚本 ==="
date
echo "环境变量检查：MYSQL_HOST=${MYSQL_HOST}, PYTHONPATH=${PYTHONPATH}"
echo "文件检查："
ls -la /app/authentication/apps.py || true
ls -la /app/device_manager/settings.py || true

# 确保日志和静态目录存在
mkdir -p /app/logs
mkdir -p /app/staticfiles

# 如果以 root 运行，修正权限为 app:app（uid 1000）
if [ "$(id -u)" = "0" ]; then
  echo "以 root 身份运行，修正 /app 下权限..."
  chown -R 1000:1000 /app || true
else
  echo "当前 UID=$(id -u)，跳过 chown（非 root）"
fi

# 确保当前用户可以写 logs 和 staticfiles；否则给出提示并退出
if [ ! -w /app/logs ]; then
  echo "ERROR: /app/logs 不可写，可能会导致 Django 无法启动。"
  echo "解决方法：在宿主机上运行: sudo chown -R 1000:1000 ./logs"
  # 也可以继续但 collectstatic 等操作可能失败 -> 退出以避免不一致状态
  exit 1
fi

echo "收集静态文件..."
if ! python manage.py collectstatic --noinput; then
    echo "ERROR: 静态文件收集失败"
    exit 1
fi

echo "检查数据库迁移..."
# 仅生成迁移文件，不强制提交
python manage.py makemigrations || true

echo "等待数据库连接... host=${MYSQL_HOST} user=${MYSQL_USER}"
counter=0
while ! mysqladmin ping -h"${MYSQL_HOST}" -u"${MYSQL_USER}" -p"${MYSQL_PASSWORD}" --silent; do
    sleep 2
    counter=$((counter + 1))
    if [ $counter -ge 30 ]; then
        echo "错误：等待数据库超时（约60秒）"
        exit 1
    fi
done
echo "数据库连接成功！"

echo "应用迁移..."
python manage.py migrate --verbosity 3

# 创建超级用户（若配置）
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "检查/创建超级用户..."
    if ! python - <<PY
import os,sys
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','device_manager.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
sys.exit(0 if User.objects.filter(username=os.environ.get('DJANGO_SUPERUSER_USERNAME')).exists() else 1)
PY
    then
        echo "创建超级用户..."
        python manage.py createsuperuser --noinput || true
    else
        echo "超级用户已存在，跳过创建..."
    fi
else
    echo "未配置超级用户环境变量，跳过创建..."
fi

echo "启动应用：后台 gunicorn -> 前台 daphne"
# 启动 gunicorn 后台（HTTP）
gunicorn device_manager.wsgi:application -b 0.0.0.0:8000 --workers 3 &

# 前台运行 daphne（ASGI，处理 websocket）
exec daphne -b 0.0.0.0 -p 8001 device_manager.asgi:application

# ...existing code...