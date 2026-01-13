# -*- coding: utf-8 -*-
# @Author  : 柚一
# @File    : md5.py
# https://pypi.tuna.tsinghua.edu.cn/simple/
# 项目地址可能发生变化，测试数据如果太多可能随时还原。 碰到地址打不开，报错等等情况，联系班主任老师及时反馈

# md5 不可逆的，不能进行解密  测试：密码规则和数据库里面的加密密文是不是一致，是也一直就通过
import hashlib

md5=hashlib.md5()
md5.update("123456".encode('utf-8'))
print(md5.hexdigest())