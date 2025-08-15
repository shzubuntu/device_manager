#!/bin/bash

# 设置项目名称和版本
PROJECT_NAME="device_manager"
VERSION="1.0.0"

# 创建临时目录
TEMP_DIR="temp_package"
PACKAGE_DIR="${PROJECT_NAME}_${VERSION}"
mkdir -p "${TEMP_DIR}/${PACKAGE_DIR}"

# 复制项目文件
echo "正在复制项目文件..."
cp -r authentication "${TEMP_DIR}/${PACKAGE_DIR}/"
cp -r books "${TEMP_DIR}/${PACKAGE_DIR}/"
cp -r device_manager "${TEMP_DIR}/${PACKAGE_DIR}/"
cp -r devices "${TEMP_DIR}/${PACKAGE_DIR}/"
cp -r templates "${TEMP_DIR}/${PACKAGE_DIR}/"
cp -r static "${TEMP_DIR}/${PACKAGE_DIR}/"
#cp -r .git "${TEMP_DIR}/${PACKAGE_DIR}/"
cp api_client.py "${TEMP_DIR}/${PACKAGE_DIR}/"
cp db.sqlite3 "${TEMP_DIR}/${PACKAGE_DIR}/"
cp package.sh "${TEMP_DIR}/${PACKAGE_DIR}/"
cp start.sh "${TEMP_DIR}/${PACKAGE_DIR}/"
cp manage.py "${TEMP_DIR}/${PACKAGE_DIR}/"
cp requirements.txt "${TEMP_DIR}/${PACKAGE_DIR}/"
cp README.md "${TEMP_DIR}/${PACKAGE_DIR}/"
#cp .env "${TEMP_DIR}/${PACKAGE_DIR}/"
# 创建部署说明文档
cat > "${TEMP_DIR}/${PACKAGE_DIR}/DEPLOY.md" << 'EOL'
# 设备管理系统部署说明

## 系统要求
- Python 3.8+
- Redis 6.0+
- MySQL 5.7+

## 安装步骤

1. 安装依赖包：
```bash
pip install -r requirements.txt
```

2. 配置数据库：
- 创建MySQL数据库
- 修改 settings.py 中的数据库配置

3. 初始化数据库：
```bash
python manage.py makemigrations
python manage.py migrate
```

4. 创建超级用户：
```bash
python manage.py createsuperuser
```

5. 启动Redis服务

6. 启动应用：
```bash
python manage.py runserver 0.0.0.0:8000
```

## 注意事项
- 请确保Redis服务已启动
- 建议在生产环境中使用 gunicorn 或 uwsgi 部署
- 请及时修改默认密码
- 建议配置 HTTPS
EOL

# 创建打包目录
mkdir -p dist

# 打包文件
echo "正在打包文件..."
cd "${TEMP_DIR}"
#tar -czf "../dist/${PACKAGE_DIR}.tar.gz" "${PACKAGE_DIR}"
tar -czf "../dist/${PROJECT_NAME}.tar.gz" "${PACKAGE_DIR}"
cd ..

# 清理临时文件
echo "清理临时文件..."
rm -rf "${TEMP_DIR}"

echo "打包完成！"
echo "打包文件位置：dist/${PROJECT_NAME}.tar.gz" 
