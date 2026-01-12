# -*- coding: utf-8 -*-
# @Author  : 柚一
# @File    : YamlCaseParser.py
# https://pypi.tuna.tsinghua.edu.cn/simple/
# 项目地址可能发生变化，测试数据如果太多可能随时还原。 碰到地址打不开，报错等等情况，联系班主任老师及时反馈
import os.path

import yaml

from day12.HAT.core.globalContext import g_context


def readYaml(file_path):
    case_info=[]
    with open(file_path,'r',encoding='utf-8') as f:
        # yaml.load读取   Loader=yaml.FullLoader 安全读取
        data=yaml.load(f,Loader=yaml.FullLoader)
    case_info.append(data)
    return case_info


# 专门读取context.yaml文件数据
def load_context_from_yaml(file_path):
    """
    :param file_path: 目录文件夹
    :return:
    """
    yaml_file_path=os.path.join(file_path, 'context.yaml')
    with open(yaml_file_path, 'r', encoding='utf-8') as file:
        data = yaml.load(file, Loader=yaml.FullLoader)
        if data:g_context().set_by_dict(data)
        print("全局变量", g_context().show_dict())

if __name__ == '__main__':
    # ./当前目录  ../上一级目录  ../../上上级目录  /n /t  r防止转义
    # data=readYaml(r'../../examples/api-cases-yaml/login.yaml')
    # print('返回结果',data)

    load_context_from_yaml(r'../../examples/api-cases-yaml/')

