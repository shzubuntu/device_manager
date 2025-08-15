# coding: utf-8
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import json
import datetime
import os
import csv
import shutil
import pandas as pd
from netmiko import ConnectHandler

def config_int(hostname,device,int_vlan_descs):
    try:
        #连接到设备上
        net_connect = ConnectHandler(**device)
        #current_view = net_connect.find_prompt()
        print("[INFO] <%s>连接成功"%hostname)

        #进入配置模式
        net_connect.config_mode()

        for int_vlan_desc in int_vlan_descs:
            arr = int_vlan_desc.split('__')
            interface = 'GigabitEthernet 1/0/'+arr[0]
            vlan = arr[1]
            description = 'Unused' if len(arr[2])==0 else arr[2]
            print("[INFO] <%s_%s>清空接口配置"%(hostname,interface))
            output = net_connect.send_command("interface "+interface,expect_string=r'\]')
            output += net_connect.send_command("default", expect_string=r'\[Y/N\]:')
            output += net_connect.send_command('Y', expect_string=r'\]')
            print(output+'\n')
            print("[INFO] <%s_%s>配置清空完成"%(hostname,interface))
            cl = []
            #vlan是0的时候表示该接口关闭
            if vlan=='0':
                cl.append('interface '+interface)
                cl.append('description '+description)
                cl.append('shutdown')
            else:
                cl.append('interface '+interface)
                cl.append('description '+description)
                cl.append('port link-type hybrid')
                cl.append('undo port hybrid vlan 1')
                cl.append('port hybrid vlan %s untagged'%vlan)
                cl.append('port hybrid pvid vlan %s'%vlan)
                cl.append('voice-vlan 191 enable')
                #cl.append('broadcast-suppression 1')
                cl.append('stp edged-port')
                cl.append('poe enable')
                cl.append('port-security intrusion-mode blockmac')
                cl.append('port-security max-mac-count 1')
                cl.append('port-security port-mode autolearn')
            print("[INFO] <%s_%s>下发配置"%(hostname,interface),json.dumps(cl,indent=2))
            output = net_connect.send_config_set(cl,exit_config_mode=False)
            print("[INFO] <%s_%s>配置完成"%(hostname,interface))
        #保存配置
        net_connect.save_config()
        print("[INFO] <%s>配置已保存"%hostname)
        #断开连接
        net_connect.disconnect()
        print("[INFO] <%s>断开连接"%hostname)
    except Exception as e:
        print("[ERROR] <%s>配置下发失败!"%hostname,e)


def change_network_conf():
    device_list = "/cffex/common/device_list.csv"
    data = pd.read_csv(device_list,sep=',')
    devices = {}
    for num in range(len(data)):
        device_name = data["device_name"][num]
        if device_name.startswith("#"):
            continue
        device = {} # 设备信息
        device["device_type"] = data["device_type"][num]
        device["ip"] = data["device_ip"][num]  
        device["username"] = "oa"
        device["password"] = "WWW.baidu.com1" 
        device["session_log"] = "%s_output.log"%device_name
        devices[device_name] = device

    #保存当前网络的接口及描述信息,用于修改描述
    int_desc_pool = {}
    """
    {
        "Y_BG_JR_HL_S01_48" : "ZD_1"
    }
    """
    with open('/cffex/crontab-scripts/mac_sticky.db') as f:
        for line in f:
            ll = line.strip().split(' ')
            hostname = ll[0]
            interface = ll[1]
            vlan = ll[3]
            description = '' if len(ll)<5 else ll[4]
            key= hostname+'_'+interface.split('/')[-1]
            int_desc_pool[key] = description

    #读取需要下发的接口配置信息，并生成配置
    int_vlan_pool = {}
    with open('sw_int_vlan.csv',newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            hostname = row['hostname']
            interface = row['interface']
            vlan = row['vlan']
            key= hostname+'_'+interface.split('/')[-1]
            description = row['description']
            if len(description)==0:
                if key in int_desc_pool:
                    description = int_desc_pool[key]
            value = row['interface'].split('/')[-1]+'__'+row['vlan']+'__'+description
            if row['hostname'] in int_vlan_pool:
                int_vlan_pool[row['hostname']].append(value)
            else:
                int_vlan_pool[row['hostname']] = [value]
    print("配置信息列表:",json.dumps(int_vlan_pool,indent=4))

    prompt = "Please confirm to continue[y/n]:"
    order = input(prompt)
    if order.lower() =='n':
        exit(0)

    #下发配置
    port_count=0
    with ThreadPoolExecutor(max_workers=120) as t:
        for dev in int_vlan_pool:
            port_count +=len(int_vlan_pool[dev])
            args=[dev,devices[dev],int_vlan_pool[dev]]
            obj = t.submit(lambda p:config_int(*p),args)
    print("[Report] 共计%s台设备(%s个接口)配置完成!"%(len(int_vlan_pool),port_count))

if __name__ == "__main__":
    start_time=datetime.datetime.now()
    change_network_conf()
    end_time=datetime.datetime.now()
    print("执行用时:",end_time-start_time)
