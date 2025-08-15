#!/bin/bash
docker-compose down -v && docker-compose up -d
#docker-compose down -v && docker-compose up --build -d && docker-compose exec web python manage.py migrate
#docker-compose down  && docker-compose up --build -d && docker-compose exec web python manage.py migrate
#docker-compose build --no-cache web
#一键停止并移除所有相关的容器、网络，但不会删除持久化的数据卷，如./mysql_data
#docker-compose down

#在上一条命令基础上删除数据卷，如./mysql_data
#docker-compose down -v

# 停止容器释放CPU、内存资源，不删除容器
#docker-compose stop

#docker-compose start

# 停止容器,释放CPU、不释放内存资源，不删除容器
#docker-compose pause
#docker-compose unpause
