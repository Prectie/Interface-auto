# -*- coding: utf-8 -*-
# @Author  : 柚一
# @File    : 下载接口.py
# https://pypi.tuna.tsinghua.edu.cn/simple/
# 项目地址可能发生变化，测试数据如果太多可能随时还原。 碰到地址打不开，报错等等情况，联系班主任老师及时反馈
import os

import requests

url='http://127.0.0.1:5001/download/2.png'
response=requests.get(url)
if response.status_code==200:
    os.makedirs('img',exist_ok=True)
    with open('img/2.png','wb')as f:
        f.write(response.content)
    print('下载成功')
else:
    print('下载失败')