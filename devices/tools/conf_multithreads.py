# coding: utf-8
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import json
import pandas as pd
from netmiko import ConnectHandler
import datetime
import os
import shutil


def config(device_name,device,command_list):

    try:
        net_connect = ConnectHandler(**device)
        current_view = net_connect.find_prompt()
        print(current_view," is connected")
        for command in command_list:
            output = net_connect.send_config_set(command_list)
            print(output)
        print(current_view," config saved")
        net_connect.disconnect()
        print(current_view," connecttion closed")
    except Exception as e:
        print("%s's infomation get failed. "%device_name,e)


def change_network_conf():
    #device_list = "/cffex/devops/device/special/y_bg_device_list_for_now.csv"
    device_list = "/cffex/data/switch_config/conf/y_bg_device_list.csv"
    data = pd.read_csv(device_list,sep=',')
    devices = {}
    for num in range(len(data)):
        device_name = data["device_name"][num]
        if device_name.startswith("#"):
            continue
        device = {} # 设备信息
        device["device_type"] = data["device_type"][num]
        device["ip"] = data["device_ip"][num]  
        device["username"] = "cffex"
        device["password"] = "Wlyw@5*8=40!" 
        devices[device_name] = device
    #print(json.dumps(devices,indent=4))
    with ThreadPoolExecutor(max_workers=120) as t:
        obj_list = []
        begin = time.time()
        for dev in devices:
            if "h3c" in devices[dev]["device_type"]:
                command_list_0=[
                    "display device manuinfo",
                    "display lldp neighbor-information list"
                ]
                command_list=[
                    "info-center loghost 172.17.1.202"
                ]
            elif "huawei" in devices[dev]["device_type"]:
                command_list=[
                    "info-center loghost 172.17.1.202"
                ]
            elif "cisco" in devices[dev]["device_type"]:
                command_list=[
                    "logging 172.17.1.202",
                ]
            args=[dev,devices[dev],command_list]
            obj = t.submit(lambda p:config(*p),args)
            obj_list.append(obj)
    print("All ",len(devices)," devices finished!")

if __name__ == "__main__":
    start_time=datetime.datetime.now()
    change_network_conf()
    end_time=datetime.datetime.now()
    print("Runtime is: ",end_time-start_time)
