import requests
import yaml
from jsonpath_ng import parse

from Engine.executor import Executor
from Utils.allure_reporter import AllureReporter
from Utils.log_utils import LoggerManager
from Utils.print_pretty import print_rich

logger = LoggerManager.get_logger()


def test_single_api(executor_fx: Executor, api_id: str, data_index: int):
    """
      基于 pytest_generate_tests 自动生成的 api_id 参数，逐条执行 single.yaml 的接口用例

    :param executor_fx: function 级 executor fixture, 提供执行器
    :param api_id: 收集阶段生成的接口 id
    :param data_index: 当前接口数据驱动的下标
    """
    AllureReporter.set_single_metadata(
        api_id=api_id,
        data_index=data_index,
        active_env=executor_fx.repo.config.active_env
    )
    # 执行单接口
    ret = executor_fx.run_single(api_id=api_id, data_index=data_index)

    if ret.request:
        logger.debug(print_rich(ret.request))



def test_flows_api(executor_fx: Executor, flow_id: str):
    """
      基于 pytest_generate_tests 自动生成的 flow_id 参数，逐条执行业务流用例

    :param executor_fx: function 级 executor fixture, 提供执行器
    :param flow_id: 收集阶段生成的接口 id
    """
    flow = executor_fx.repo.get_flow(flow_id)
    AllureReporter.set_flow_metadata(
        flow=flow,
        active_env=executor_fx.repo.config.active_env
    )
    # 执行单接口
    ret = executor_fx.run_flow(flow_id=flow_id)
    if ret.steps:
        logger.debug(print_rich(ret.steps))

if __name__ == "__main__":
    # yaml.safe_load_all()
    pass
