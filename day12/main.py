# -*- coding: utf-8 -*-
# @Author  : 柚一
# @File    : main.py.py
# https://pypi.tuna.tsinghua.edu.cn/simple/
# 项目地址可能发生变化，测试数据如果太多可能随时还原。 碰到地址打不开，报错等等情况，联系班主任老师及时反馈
import os

import pytest
from allure_combine import combine_allure

# '-v','-s'详细内容
# --capture=sys系统配置 生成allure报告 stdout附件
# --claen-alluredir清空测试数据 保持测试报告中的数据是最新的测试数据
# alluredir生成测试数据  数据文件夹allure-results

pytest_args=['-v','-s','--capture=sys',
             '--clean-alluredir',
             '--alluredir=allure-results',
             './HAT/core/TestRunner.py'
             ]
# 执行用例
pytest.main(pytest_args)
# 生成测试报告
os.system('allure generate -c -o allure-report')

combine_allure('./allure-report')