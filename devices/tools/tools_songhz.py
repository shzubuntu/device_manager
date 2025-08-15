#!/usr/bin/python
#Author: songhz
#Time: 2024-04-24 10:01:55
#Name: linux_cmd_print_color.py
#Version: V1.0

import os
import re
import csv
import chardet
import platform
import time
from datetime import datetime
from functools import wraps
"""
【功能索引】
    测试日志装饰器 20241106
    返回文件的创建时间 20240816 songhz
    检测并返回文件的编码
    读取文件内容【动态检测文件编码】
    获取文件夹下最新的文件夹url
    根据路径和文件扩展名获取文件列表
    打印颜色字体
    移除文本中的字母
    将字典写入文件，可以额外增加列 20240816 songhz
    将列表写入文件，可以额外增加列 20240816 songhz
    检查字符串是否符合正则表达式 20241104 songhz
"""


#定义一个日志装饰器
def log(func):
    @wraps(func)
    def loginfo(*args, **kwargs):
        print("执行函数",func.__name__)
        return func(*args, **kwargs)
    return loginfo

#返回文件的创建时间
def get_file_time(filepath):
    time_str = ''
    if platform.system() == 'Windows':
        # 在Windows上，使用st_ctime作为文件的创建时间
        creation_time = os.path.getctime(filepath)
        time_str = time.ctime(creation_time)
    else:
        # 在Unix/Linux上，通常没有直接的创建时间，可以返回修改时间作为替代
        modification_time = os.path.getmtime(filepath)
        time_str = time.ctime(modification_time)
    time_obj = datetime.strptime(time_str, '%a %b %d %H:%M:%S %Y')
    date_str = time_obj.strftime('%Y-%m-%d %H:%M:%S')
    return date_str

#检测并返回文件的编码
def detect_encoding(file_path):
    with open(file_path, 'rb') as file:
        raw_data = file.read()
    result = chardet.detect(raw_data)
    return result['encoding']

#读取文件内容，动态检测文件编码
def read_file(file_path):
    encoding = detect_encoding(file_path)
    with open(file_path, 'r', encoding=encoding) as file:
        content = file.read()
    return content

#获取文件夹下最新的文件夹url
def get_latest_dir(path):
    dirs = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
    latest_dir = max(dirs, key=lambda x: os.path.getmtime(os.path.join(path, x)))
    return os.path.join(path, latest_dir)

#根据路径和文件扩展名获取文件列表
def get_file_from_dir(root_path, file_extname):
    fileurls = []
    #获取该目录下所有的文件名称和目录名称
    files = os.listdir(root_path)
    for file in files:
        #获取目录或者文件的路径
        fileurl = os.path.join(root_path,file)
        #判断该路径为文件还是路径
        if os.path.isdir(fileurl):
            #递归获取所有文件和目录的路径
            fileurls = fileurls + get_file_from_dir(fileurl, file_extname)
        else:
            if file_extname is None:
                fileurls.append(fileurl)
                continue
            extname = fileurl.split('.')[-1]
            if extname in file_extname:
                fileurls.append(fileurl)
            else:
                continue
    return fileurls

#打印颜色字体
def print_color(text, color):
    color = color.upper()
    RESET = '\033[0m'
    color_dict = {
        'RED':'\033[91m',
        'GREEN':'\033[92m',
        'YELLOW':'\033[93m',
        'BLUE':'\033[94m',
        'MAGENTA':'\033[95m',
        'CYAN':'\033[96m',
    }

    results = color_dict[color] + text + RESET
    return results

#移除文本中的字母
def remove_letters(text):
    return re.sub('[a-zA-Z]','',text)

#将字典写入文件，可以额外增加列
def dict_write_csv(fileurl,datas,extra_datas=False):
    """
    fileurl: csv文件名
    datas: 字典列表，要写入csv文件的内容
    extra_datas: 需要额外增加的列及内容
    """
    if len(datas) == 0:
        return
    #extra_data是额外增加的数据,固定的值
    #检测文件是否存在
    exists = os.path.exists(fileurl)
    #如果有附加数据，那么将附加数据添加进已有数据中
    new_datas = [] #保存新的数据
    if extra_datas is not False:
        for data in datas:
            new_data = {**extra_datas, **data}
            new_datas.append(new_data)
    else:
        new_datas = datas
    #如果存在，则以增量的方式添加数据
    keys = list(new_datas[0].keys())
    with open(fileurl,'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=keys)
        #如果文件不存在，则写入表头
        if not exists:
            writer.writeheader()
        for d in new_datas:
            writer.writerow(d)

#将列表写入文件，可以额外增加列
def list_write_csv(fileurl,lists,headers,extra_datas=False):
    """
    fileurl: csv文件名
    lists: 嵌套列表，要写入csv文件的内容
    headers: 表头字段列表
    extra_datas: 需要额外增加的列及内容
    """
    if len(lists) == 0:
        return
    #构建字典
    datas = []
    for l in lists:
        new_data = {}
        for i in range(len(l)):
            #处理List数据和含有逗号的数据
            data_str = ';'.join(l[i]) if isinstance(l[i],list) else str(l[i]).replace(',',';')
            new_data[headers[i]] = data_str
        datas.append(new_data.copy())
    dict_write_csv(fileurl,datas,extra_datas)

#检查字符串是否符合正则表达式
def check_string(re_exp, text,alpha=True):
    """
     alpha = True 字母大小写敏感
    """
    if alpha is False:
        re_exp = re_exp.lower()
        text = text.lower()
    res = re.search(re_exp, text)
    if res:
        return True
    else:
        return False
def get_mac(text):
    mac_regex = r"((?:[0-9a-fA-F]{4}[-.]){2}[0-9a-fA-F]{4})"
    macs = re.findall(mac_regex,text)
    return macs
def main():
    """
    print_color("songhz",'red')
    print_color("songhz",'green')
    print_color("songhz",'yellow')
    print_color("songhz",'blue')
    print_color("songhz",'magenta')
    print_color("songhz",'cyan')
    print(get_latest_dir("/root/workplace/tangyin/history"))
    datas = [["zhangsan",17,[88,99]],["lisi",18,[88]]]
    datas = [["wangwu",17,[88,99]]]

    extra_datas = {
        "sex":'2',
        "address":'shanghai',
    }
    fileurl = 'test.csv'
    header = ['username','age','score']
    dict_write_csv(fileurl,datas,extra_datas)
    dict_write_csv(fileurl,datas1,extra_datas)
    """
    #print(check_string('so.*g', 'songhanzheng'))
    #tt = 'switchport port-security mac-address sticky c074.ad1f.d8d0,port-security mac-address security sticky e070-eab2-df4c vlan 246'
    #print(get_mac(tt))
    #text = 'iset interfaces irb unit 121 family inet address 172.24.21.252/24 vrrp-group 21 virtual-address 172.24.21.254'
    #ip_regex = r"((?:\d{1,3}.){3}\d{1,3}/\d{1,2})"
    #print(re.findall(ip_regex,text))
    #re_exp = '172.25.*'
    #re_exp = "172.25\..*"
    #text='ip address 172.26.172.254 255.255.255.0'
    #print(re.search(re_exp, text),check_string(re_exp,text))
    #text='ip address 172.25.172.254 255.255.255.0'
    #print(re.search(re_exp, text),check_string(re_exp,text))

if __name__ == '__main__':
    main()
