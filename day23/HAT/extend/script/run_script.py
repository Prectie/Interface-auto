# -*- coding: utf-8 -*-
# @Author  : 柚一
# @File    : run_script.py
# https://pypi.tuna.tsinghua.edu.cn/simple/
# 项目地址可能发生变化，测试数据如果太多可能随时还原。 碰到地址打不开，报错等等情况，联系班主任老师及时反馈

def exec_script(script, context):
    """
    执行脚本
    :param script: 前置脚本
    :param context: 上下文，全局变量
    :return:
    """
    # 如果前置脚本为空 直接return
    if script is None: return
    exec(script, {"context": context})
    # exec 让字符串变成代码并且执行
    # exec 第个参数是 字符串的python代码
    # 第二个参数是全局变量字典  "context"随意变化 a,b