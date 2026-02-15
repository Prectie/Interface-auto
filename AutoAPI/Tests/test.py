import requests
import yaml
from jsonpath_ng import parse

from Runtime.executor import Executor
from Utils.print_pretty import print_rich


def dtestd():
    res = requests.post(
        url="http://shop-xo.hctestedu.com/index.php?s=api/region/index",
    )
    expr = parse("$.errmsg")
    ma = expr.find(res.json())
    value = [m.value for m in ma]
    print(value)

    print_rich(res.json())


def test_single_api(executor_fx: Executor, api_id: str):  # 参数化：一个 api_id 一个用例  #
    """
    目的/作用：
        基于 pytest_generate_tests 自动生成的 api_id 参数，逐条执行 single.yaml 的接口用例。  #
    参数说明：
        1) executor_fx：function 级 executor fixture；  #
        2) api_id：收集阶段生成的接口 id。  #
    返回值说明：
        1) 无（断言失败或执行异常会直接让 pytest 用例失败）。  #
    在系统中的作用：
        将 single.yaml.apis 映射为 pytest 用例集合，实现“接口库回归”。  #
    调用关系：
        1) pytest 收集阶段参数化生成多个 test_single_api[api_id]；  #
        2) 运行阶段调用 executor.run_single 完成完整闭环。  #
    """  # 方法说明结束  #
    result = executor_fx.run_single(api_id=api_id, fail_fast=True)  # 执行单接口（断言失败立即抛错更直观）  #
    print("\n" + "=" * 120)  # 打印分隔线  #
    print(f"[dev] api_id = {api_id}")  # 打印接口 id  #

    if result.request:  # 若存在 prepared_request  #
        print("[dev] prepared_request:")  # 打印标题  #
        print_rich(result.request)  # 美化打印请求结构  #

    print(f"[dev] status_code = {result.status_code}")  # 打印状态码  #
    print("[dev] response_text (maybe truncated):")  # 提示响应可能被截断  #
    print_rich(result.response_text or "")  # 打印响应文本摘要  #

    if result.extract_out:  # 若有提取结果  #
        print("[dev] extract_out:")  # 打印标题  #
        print_rich(result.extract_out)  # 美化打印提取结果  #

    if result.assertions:  # 若有断言结果  #
        print("[dev] assertions:")  # 打印标题  #
        print_rich([a.to_dict() for a in result.assertions])  # 美化打印断言结果  #

    print("=" * 120 + "\n")  # 打印分隔线  #


if __name__ == "__main__":
    # yaml.safe_load_all()
    dtestd()

