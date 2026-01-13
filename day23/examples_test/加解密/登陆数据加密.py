# -*- coding: utf-8 -*-
# @Author  : 柚一
# @File    : 登陆数据加密.py
# https://pypi.tuna.tsinghua.edu.cn/simple/
# 项目地址可能发生变化，测试数据如果太多可能随时还原。 碰到地址打不开，报错等等情况，联系班主任老师及时反馈
import base64

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# aes加密
# 1.密钥  开发约定
key=b'1234567812345678'
# 加密数据
data='123456'
# aes需要字节数据
data=data.encode('utf-8')
# 加密 ECB
cipher=AES.new(key,AES.MODE_ECB)
# 填充
ct_bytes=cipher.encrypt(pad(data,AES.block_size))
ct=base64.b64encode(ct_bytes).decode('utf-8')
print("加密数据",ct)

# 加密： 密码--字符串--时间戳--数字   123tony2025119902
# 解密：数字--时间戳--字符串--密码

# 解密
ci_bytest=base64.b64decode(ct)#base64解码
cipher=AES.new(key,AES.MODE_ECB)#aes解密
pt=unpad(cipher.decrypt(ci_bytest),AES.block_size)#去除填充
c=pt.decode('utf-8')
print("解密数据",c)

# 调api接口做接口测试