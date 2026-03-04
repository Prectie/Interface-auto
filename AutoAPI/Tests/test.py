import requests
import yaml
from jsonpath_ng import parse

from Engine.executor import Executor
from Utils.print_pretty import print_rich


def dtestd():
    res = requests.post(
        url="http://192.168.1.141:8088/je/dd/dd/getDicItemByCodes",
        cookies={
            "je-theme": "je-theme-blue",
            "je-local-lang": "zh_CN",
            "phone": "auto",
            "authorization": "bIdGHB2UHESv5jiCIC7",
        },
        data={
            "tableCode": "JE_CORE_DICTIONARY",
            "ddListCodes": "BUSINESS_QUESTION_TYPE,YWDN_BUSINESS_TYPE,YWDN_IS_SINGLETON,YWDN_PAGE_TYPE,JE_AUDFLAG,APP_STATUS"
        }
    )
    expr = parse("$.errmsg")
    ma = expr.find(res.json())
    value = [m.value for m in ma]
    print(value)

    print_rich(res.json())


def test_single_api(executor_fx: Executor, api_id: str):
    """
      基于 pytest_generate_tests 自动生成的 api_id 参数，逐条执行 single.yaml 的接口用例

    :param executor_fx: function 级 executor fixture, 提供执行器
    :param api_id: 收集阶段生成的接口 id
    """
    # 执行单接口
    result = executor_fx.run_single(api_id=api_id)
    # 打印分隔线
    print("\n" + "=" * 120)
    # 打印接口 id
    print(f"[dev] api_id = {api_id}")

    # 若存在 prepared_request, 打印 发送的请求数据
    if result.request:
        print("[dev] prepared_request:")
        print_rich(result.request)

    # 打印本次响应的状态码
    print(f"[dev] status_code = {result.status_code}")

    # 打印响应文本摘要
    print("[dev] response_text (可能存在被截断的情况):")
    print_rich(result.response_text or "")

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
    # 打印接口 id
    print(f"[dev] api_id = {flow_id}")

    # 若存在 prepared_request, 打印 发送的请求数据
    if result.steps:
        print("[dev] prepared_request:")
        print_rich(result.steps)

    # 打印分隔线
    print("=" * 120 + "\n")


if __name__ == "__main__":
    # yaml.safe_load_all()
    dtestd()

