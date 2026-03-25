import requests
import yaml
from jsonpath_ng import parse

from Engine.executor import Executor
from Utils.print_pretty import print_rich


def test_single_api(executor_fx: Executor, api_id: str, data_index: int):
    """
      基于 pytest_generate_tests 自动生成的 api_id 参数，逐条执行 single.yaml 的接口用例

    :param executor_fx: function 级 executor fixture, 提供执行器
    :param api_id: 收集阶段生成的接口 id
    """
    # 执行单接口
    result = executor_fx.run_single(api_id=api_id, data_index=data_index)
    # 打印分隔线
    print("\n" + "=" * 120)
    # 打印接口 id
    print(f"[dev] api_id = {api_id}")

    # 若存在 prepared_request, 打印 发送的请求数据
    if result.request:
        print("[dev] prepared_request:")
        print_rich(result.request)

    # 打印响应文本摘要
    print("[dev] response (可能存在被截断的情况):")
    print_rich(result.response or "")

    # 若有提取结果
    if result.extract_out:
        print("[dev] extract_out:")
        print_rich(result.extract_out)

    # 若有断言结果
    if result.assertions:
        print("[dev] assertions:")
        print_rich([a.to_dict() for a in result.assertions])

    # 打印分隔线
    print("=" * 120 + "\n")


def test_flows_api(executor_fx: Executor, flow_id: str):
    """
      基于 pytest_generate_tests 自动生成的 api_id 参数，逐条执行 single.yaml 的接口用例

    :param executor_fx: function 级 executor fixture, 提供执行器
    :param flow_id: 收集阶段生成的接口 id
    """
    # 执行单接口
    result = executor_fx.run_flow(flow_id=flow_id)
    # 打印分隔线
    print("\n" + "=" * 120)

    # 若存在 prepared_request, 打印 发送的请求数据
    if result.steps:
        print("[dev] prepared_request:")
        print_rich(result.steps)

    # 打印分隔线
    print("=" * 120 + "\n")


if __name__ == "__main__":
    # yaml.safe_load_all()
    dtestd()

