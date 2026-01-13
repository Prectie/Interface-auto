# -*- coding: utf-8 -*-
# @Author  : 柚一
# @File    : main.py.py
# https://pypi.tuna.tsinghua.edu.cn/simple/
# 项目地址可能发生变化，测试数据如果太多可能随时还原。 碰到地址打不开，报错等等情况，联系班主任老师及时反馈
import os
import sys
import time

import pytest
from allure_combine import combine_allure
from loguru import logger

from day23.HAT.core.CasePlugin import CasePlugin

# '-v','-s'详细内容
# --capture=sys系统配置 生成allure报告 stdout附件
# --claen-alluredir清空测试数据 保持测试报告中的数据是最新的测试数据
# alluredir生成测试数据  数据文件夹allure-results

# 如果不存在logs文件就创建一个
if not os.path.exists('./HAT/logs'):
    os.mkdir('./HAT/logs')

# 文件名称
time_str=time.strftime('%Y-%m-%d %H-%M-%S', time.localtime())
log_level=os.getenv("HAT_LOG_LEVEL","DEBUG").upper()#支持环境变量配置日志级别  HAT_LOG_LEVEL项目上有配置的日志名称

logger.configure(
    handlers=[
        {"sink":sys.stdout,"level":"INFO"},#控制台显示
        {"sink": os.path.join("./HAT/logs",f"hat_{time_str}.log"), "level": log_level}#文件中展示
    ]
)



pytest_args=['-v','-s','--capture=sys',
             '--clean-alluredir',
             '--alluredir=allure-results',
             './HAT/core/TestRunner.py',
             '--type=yaml',
             '--cases=./examples/api-cases-商城/',
             '--reruns=2',
             '--reruns-delay=3'
             ]
# 执行用例
pytest.main(pytest_args,plugins=[CasePlugin()])
# 生成测试报告
os.system('allure generate -c -o allure-report')

combine_allure('./allure-report')