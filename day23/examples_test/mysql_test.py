# -*- coding: utf-8 -*-
# @Author  : 柚一
# @File    : mysql_test.py
# https://pypi.tuna.tsinghua.edu.cn/simple/
# 项目地址可能发生变化，测试数据如果太多可能随时还原。 碰到地址打不开，报错等等情况，联系班主任老师及时反馈
import pymysql
from pymysql import cursors

# python操作数据库
# 过程：链接数据库--生成游标（鼠标）--写sql--执行sql(游标)---(游标)获得结果--关闭游标--关闭数据库

"""
常用方法：
- cursor(): 创建游标对象
- close(): 关闭游标对象
- fetchone(): 得到结果集的下一行
- fetchmany([size = cursor.arraysize]):得到结果集的下几行
- fetchall():得到结果集中剩下的所有行
- execute(sql[,args]): 执行一个数据库查询或命令
- executemany(sql,args):执行多个数据库查询或命令
"""

# 链接数据库-
connect=pymysql.connect(host='shop-xo.hctestedu.com',
              port=3306,
              user='api_test',
              password='Aa9999!',
              db='shopxo_hctested',
             cursorclass=cursors.DictCursor,#字典方式展示数据
              charset='utf8')
# 生成游标
cursor=connect.cursor()

# 执行sql
sql="select id,username from sxo_user where username='youyi'"
cursor.execute(sql)

# (游标)获得结果
result=cursor.fetchall()
print('数据库结果',result)

# 关闭游标
cursor.close()
# 关闭数据库
connect.close()
