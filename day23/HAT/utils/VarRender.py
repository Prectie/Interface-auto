# -*- coding: utf-8 -*-
# @Author  : 柚一
# @File    : VarRender.py
# https://pypi.tuna.tsinghua.edu.cn/simple/
# 项目地址可能发生变化，测试数据如果太多可能随时还原。 碰到地址打不开，报错等等情况，联系班主任老师及时反馈
from jinja2 import Template


def refresh(target,context):
    """
    原理：字符串模板和字典来进行字符串的替换操作
    :param target: 目标字符串  需要有个字符串模板{{变量名}}  {"name":"{{name}}","age":18}
    :param context:  源字典  {"name":"张三","age":18,"sex":"女","class":["哈哈哈"，‘嘻嘻’]}
    :return:
    """
    if target is None: return None
    return Template(str(target)).render(context)

if __name__ == '__main__':
    target= {"name":"{{name}}","age":18}
    context={"name":"张三","age":18,"sex":"女","class":["哈哈哈",'嘻嘻']}
    r=refresh(target,context)
    print("新数据",r)