# -*- coding: utf-8 -*-
# @Author  : 柚一
# @File    : 封装加解密.py
# https://pypi.tuna.tsinghua.edu.cn/simple/
# 项目地址可能发生变化，测试数据如果太多可能随时还原。 碰到地址打不开，报错等等情况，联系班主任老师及时反馈
import base64

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


class EnCryptData:
    def __init__(self,key):
        self.key=key

    def encrypyt(self,data):
        # aes需要字节数据
        data = data.encode('utf-8')
        # 加密 ECB
        cipher = AES.new(self.key, AES.MODE_ECB)
        # 填充
        ct_bytes = cipher.encrypt(pad(data, AES.block_size))
        ct = base64.b64encode(ct_bytes).decode('utf-8')
        return ct

    def dencrypt(self,data):
        ci_bytest = base64.b64decode(data)  # base64解码
        cipher = AES.new(self.key, AES.MODE_ECB)  # aes解密
        pt = unpad(cipher.decrypt(ci_bytest), AES.block_size)  # 去除填充
        c = pt.decode('utf-8')
        return c

if __name__ == '__main__':
    key=b'1234567812345678'

    ed=EnCryptData(key)
    jiami=ed.encrypyt('tony')
    print("加密数据",jiami)

    pwd = ed.encrypyt('123456')
    print("加密数据", pwd)
    #
    # jiemi=ed.dencrypt(jiami)
    # print("解密数据",jiemi)

    url='http://127.0.0.1:8080/login_safe'
    data={
        "username":jiami,
        "password":pwd
    }

    res=requests.post(url,data=data)
    print(res.text)

