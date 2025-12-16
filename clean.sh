#!/bin/bash
#一键停止并移除所有相关的容器、网络，但不会删除持久化的数据卷，如./mysql_data
docker-compose down -v
