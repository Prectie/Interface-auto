# -*- coding: utf-8 -*-
# @Author  : 柚一
# @File    : ApiCaseContext.py
# https://pypi.tuna.tsinghua.edu.cn/simple/
# 项目地址可能发生变化，测试数据如果太多可能随时还原。 碰到地址打不开，报错等等情况，联系班主任老师及时反馈
import requests

from day23.HAT.core.globalContext import g_context
from day23.HAT.keywords.api_keywords import Keywords

_global_request_obj=None
class ApiCaseContext:
    def __init__(self):
        self.request=None
        self.keywords=None

    # 复用session
    def init_keywords(self):
        #到哪是session复用还是不复用
        session_reuse=g_context().get_dict("session_reuse")#获取全局变量session_reuse的值
        # 如果session_reuse是复用 True 就创建一个 session 保存在全局变量中 后续用例中复用
        if session_reuse is not None and session_reuse==True:
            global  _global_request_obj
            if _global_request_obj is None:#如果全局变量没有值，新建session对象
                _global_request_obj=requests.session()#第一次是没有session的，第二次有session的
            self.request=_global_request_obj#使用全局实例
        else:#如果session_reuse是false  每次都创建session对象
            self.request=requests.session()
        self.keywords=Keywords(self.request)
        return self.keywords




    def release(self):
        pass