import os.path

import os
import sys
import time
import pytest


def run_tests():
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    # 生成allure中间结果
    json_report_dir = f'./allure_json_report/{timestamp}'

    # 需要测试的文件路径
    test_dir = 'test_demo/test_.py'
    test_demo_dir = 'Tests/test_demo.py'
    test_sys_dir = 'Tests/SystemAdmin/'
    test_aud_dir = 'Tests/Audited/test_info_sharing.py'
    test_k = './Tests/ApplicationPortal/test_core_app.py::TestCoreApp::test_orp_core_0002'

    # 生成 allure html 文件路径
    allure_report_dir = f'./allure_report/{timestamp}'

    # 创建 report_dir 路径文件
    os.makedirs(json_report_dir, exist_ok=True)
    os.makedirs(allure_report_dir, exist_ok=True)

    pytest_args = [
        test_k,
        f'--alluredir={json_report_dir}',
    ]

    # 执行测试并生成 Allure 结果
    pytest.main(pytest_args)

    # 生成 Allure 报告并通过 allure serve 打开
    os.system(f"allure generate {json_report_dir} -o {allure_report_dir} --clean")
    os.system(f"allure serve {json_report_dir}")


if __name__ == "__main__":
    raise SystemExit(run_tests())
