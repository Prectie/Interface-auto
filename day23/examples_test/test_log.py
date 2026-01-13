# -*- coding: utf-8 -*-
# @Author  : 柚一
# @File    : test_log.py
# https://pypi.tuna.tsinghua.edu.cn/simple/
# 项目地址可能发生变化，测试数据如果太多可能随时还原。 碰到地址打不开，报错等等情况，联系班主任老师及时反馈
from loguru import logger

# logger.debug("调试级别")
# logger.info("程序正常运行")
# logger.warning("警告信息")
# logger.error("错误信息")

# 保存在文件中
logger.add(
    "log_{time}.log",#日志文件名称
    rotation="100MB",#指定文件大小
    retention="10 days"#保存时间
)


#写了一个程序  程序有没有问题  不清楚的
try:
    a = int(input("请输入任意字符:"))
    print(1 / a)
    logger.info("程序正常运行")
except Exception as e:
    logger.error("错误信息")


