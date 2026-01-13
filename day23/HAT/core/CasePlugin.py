# 扩展新功能
from day23.HAT.core.globalContext import g_context
from day23.HAT.parse.CaseParser import case_parser


class CasePlugin:
    # pytest_addoption固定的方法  添加自定义的命令行选项
    def pytest_addoption(self,parser):
        parser.addoption("--type",action="store",help="测试用例类型")
        parser.addoption("--cases",action="store",help="测试用例目录")
        parser.addoption("--keyDir",action="store",help="扩展关键字目录")


    # pytest_generate_tests固定的用法  用于参数化测试
    def pytest_generate_tests(self,metafunc):
        case_type=metafunc.config.getoption("type")
        case_dir=metafunc.config.getoption("cases")
        key_dir=metafunc.config.getoption("keyDir")
        # 把这个扩展方法放到公共变量中去
        g_context().set_dict("key_dir",key_dir)

        # 读取到用例数据
        data=case_parser(case_type,case_dir)

        if "caseinfo" in metafunc.fixturenames:
            metafunc.parametrize("caseinfo",data['case_infos'],ids=data['case_names'])

    # 解决中文显示乱码问题
    def pytest_collection_modifyitems(self,items):
        for item in items:
            item.name=item.name.encode("utf-8").decode("unicode_escape")
            item._nodeid=item.nodeid.encode("utf-8").decode("unicode_escape")