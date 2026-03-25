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
    test_dir = 'Tests/test.py::test_flows_api'
    test_ = 'Tests/test.py'

    # 生成 allure html 文件路径
    allure_report_dir = f'./allure_report/{timestamp}'

    # 创建 report_dir 路径文件
    os.makedirs(json_report_dir, exist_ok=True)
    os.makedirs(allure_report_dir, exist_ok=True)

    pytest_args = [
        test_dir,
        f'--alluredir={json_report_dir}',
    ]

    # 执行测试并生成 Allure 结果
    pytest.main(pytest_args)

    # 生成 Allure 报告并通过 allure serve 打开
    os.system(f"allure generate {json_report_dir} -o {allure_report_dir} --clean")
    os.system(f"allure serve {json_report_dir}")


if __name__ == "__main__":
    raise SystemExit(run_tests())
