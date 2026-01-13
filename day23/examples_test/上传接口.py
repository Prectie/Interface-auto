# -*- coding: utf-8 -*-
# @Author  : 柚一
# @File    : 上传接口.py.py
# https://pypi.tuna.tsinghua.edu.cn/simple/
# 项目地址可能发生变化，测试数据如果太多可能随时还原。 碰到地址打不开，报错等等情况，联系班主任老师及时反馈
import requests

url='http://127.0.0.1:5000/upload'
data={'image': open('login1.csv', 'rb')}
res=requests.post(url, files=data)
print('返回结果',res.text)