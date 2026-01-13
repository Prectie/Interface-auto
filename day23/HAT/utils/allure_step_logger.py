# -*- coding: utf-8 -*-
# @Author  : 柚一
# @File    : allure_step_logger.py
# https://pypi.tuna.tsinghua.edu.cn/simple/
# 项目地址可能发生变化，测试数据如果太多可能随时还原。 碰到地址打不开，报错等等情况，联系班主任老师及时反馈
import io
from contextlib import contextmanager

import allure
from loguru import logger


class StepLogCollector:

    def __init__(self):
        self.log_buffer=io.StringIO()#创建一个笔记本
        self.sink_id=None #笔记本的id  身份证号

    def __enter__(self):
        self.sink_id=logger.add(self.log_buffer,level="DEBUG")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logger.remove(self.sink_id)#移除id
        log_context=self.log_buffer.getvalue()#获取日志信息
        if log_context.strip():
            allure.attach(
                log_context,
                name="步骤日志",
                attachment_type=allure.attachment_type.TEXT
            )
        self.log_buffer.close()

@contextmanager#包装器  支持with语法 普通函数支持with写法
def allure_step_with_log(step_name):#用例步骤
    with allure.step(step_name):#发送登陆接口 提取数据
        with StepLogCollector() as collector:#创建一个笔记本  记录步骤日志
            yield collector#暂停执行