# -*- coding: utf-8 -*-
# @Author  : 柚一
# @File    : TestRunner.py
# https://pypi.tuna.tsinghua.edu.cn/simple/
# 项目地址可能发生变化，测试数据如果太多可能随时还原。 碰到地址打不开，报错等等情况，联系班主任老师及时反馈
import copy
import sys

import allure
import pytest
import requests
from tqdm import tqdm

from day23.HAT.context.ApiCaseContext import ApiCaseContext
from day23.HAT.core.globalContext import g_context
from day23.HAT.extend.script import run_script
from day23.HAT.keywords.api_keywords import Keywords
from day23.HAT.parse.ExcelCaseParser import load_excel_files, excel_case_parser
from day23.HAT.parse.YamlCaseParser import readYaml, load_context_from_yaml, load_yaml_files, yaml_case_parser
from day23.HAT.utils.VarRender import refresh
from day23.HAT.utils.allure_step_logger import allure_step_with_log


class TestRunner:
    # 用例数据
    # load_context_from_yaml(r'./examples/api-cases-yaml/') #把地址放在全局变量中去了
    # data=readYaml(r'./examples/api-cases-yaml/addcard.yaml')
    # print("yaml用例数据",data)

    # data=load_yaml_files(r'./examples/api-cases-yaml/')  #[{登陆},{购物车}]

    # all_data=yaml_case_parser(r'./examples/api-cases-商城/')
    # data=all_data['case_infos']

    # all_data=excel_case_parser(r'./examples/api-cases-excel/')
    # data=all_data['case_infos']
    # @pytest.mark.parametrize("caseinfo",data)  #一定是一个列表数据
    def test_case_execute(self,caseinfo):
        # print("用例数据",caseinfo)
        # keywords=Keywords(requests.session())  #每次发送请求创建一个session对象
        base_info=caseinfo.get('基础配置',{})#测试报告后续用的

        # 只需要调用ApiCaseContext().方法()
        if base_info.get("用例类型")=='ApiCase':#用例是api用例
            keywords=ApiCaseContext().init_keywords()

        allure.dynamic.parameter("caseinfo", "")
        allure.dynamic.feature(base_info.get("一级模块", "默认模块"))
        allure.dynamic.story(base_info.get("二级模块", "默认模块"))
        allure.dynamic.title(base_info.get("用例标题",'默认用例标题'))

        # 还要考虑到一种情况,你准备的测试数据，也可能是从其他地方传过来的，目前没用到
        local_context=caseinfo.get("local_context",{})
        context=copy.deepcopy(g_context().show_dict())
        context.update(local_context)

        # 读取前置脚本的数据
        pre_script=refresh(caseinfo.get("前置脚本", None),context)
        if pre_script:#前置脚本不为空  "context.update({'uname':'youer'})"
            for script in eval(pre_script): #循环前置脚本的数据
                # 放在全局变量(script--g_context().show_dict())
                run_script.exec_script(script,g_context().show_dict()) #只是把前置脚本的数据放在全局变量中

        steps=caseinfo.get('用例步骤',None)

        with tqdm(total=len(steps),desc="开始执行") as pbar:
            for step in steps:#[{'发送登录接口'：{'操作类型': '发送请求POST', '请求地}}]
                step_name=list(step.keys())[0] #'发送登录接口'
                step_value=list(step.values())[0]#{'操作类型': '发送请求POST', '请求地址': 'httpxx
                pbar.set_description(f'{base_info.get("用例标题")}-当前步骤:{step_name}')
                pbar.update(1)
                with allure_step_with_log(step_name):
                # with allure.step(step_name):
                    print("没有渲染前的字典值数据", step_value)  #accounts: "{{uname}}"
                    context = copy.deepcopy(g_context().show_dict())#拷贝全局变量 全局变量中有uname的值
                    context.update(local_context)#ddt数据放在全局变量，给用例中的accounts: "{{uname}}" 进行渲染
                    print("全局变量", context)
                    step_value=eval(refresh(step_value, context))#从全局变量渲染字典值数据到用例中去  accounts: "youer"
                    print("渲染后的字典值数据", step_value)
                    key=step_value['操作类型']#发送请求POST  发送请求GET
                    # print("操作类型",key)
                    try:
                        key_func=keywords.__getattribute__(key)#去Keywords关键字类中找对应的方法  反射
                        key_func(**step_value)  # 发送请求POST(接口信息)
                    except AttributeError as e:#没有找到属性
                        # # print("在keywords类中没有找到对应的方法")
                        if g_context().get_dict("key_dir") is not None:
                            keywords.ex_invoke(key=key,step_value=step_value)
                        # 只有在"找不到方法"且配置了外部关键字目录时，才尝试外部调用
                    except Exception as e:
                        raise

                    #     sys.path.append('./HAT/key_dir')#找目录文件
                    #     module=__import__(key)#导入模块 import 发送请求 POST
                    #     class_=getattr(module,key)#获取模块中的方法
                    #     key_func=class_(requests).__getattribute__(key)
                    # key_func(**step_value)  # 发送请求POST(接口信息)

        # 还要考虑到一种情况,你准备的测试数据，也可能是从其他地方传过来的，目前没用到
        local_context = caseinfo.get("local_context", {})
        context = copy.deepcopy(g_context().show_dict())
        context.update(local_context)

        # 读取前置脚本的数据
        pre_script = refresh(caseinfo.get("后置脚本", None), context)
        if pre_script:  # 前置脚本不为空  "context.update({'uname':'youer'})"
            for script in eval(pre_script):  # 循环前置脚本的数据
                # 放在全局变量(script--g_context().show_dict())
                run_script.exec_script(script, g_context().show_dict())  # 只是把前置脚本的数据放在全局变量中






# if __name__ == '__main__':
#     pytest.main(['-sv',__file__])