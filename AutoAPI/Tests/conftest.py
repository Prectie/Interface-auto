# -*- coding: utf-8 -*-
from typing import Optional

import pytest

from pathlib import Path

from Utils.allure_reporter import AllureReporter
from Utils.path_utils import PathTool
from Core.repository import YamlRepository
from Engine.executor import Executor

# 全局缓存 repository，避免收集阶段重复 load
_repo_cache: Optional[YamlRepository] = None


def _get_data_dir() -> Path:
    """
      从当前 conftest.py 的位置向上查找项目根目录，并定位到 Data 目录

    :return: Path：Data 目录的绝对路径
    """
    # 查找包含 Data/pyproject/run.py 的目录作为根目录
    project_root = PathTool.project_root(__file__, markers=("Data", "pyproject.toml", "run.py"))
    return project_root / "Data"


def _get_repo() -> YamlRepository:
    """
      在 pytest 收集阶段与运行阶段复用同一个 repository 实例，避免重复读取 YAML

    :return: YamlRepository：已 load 完成的仓库对象
    """
    # 声明使用全局变量
    global _repo_cache

    # 若缓存为空
    if _repo_cache is None:
        # 获取 Data 目录
        data_dir = _get_data_dir()
        # 初始化仓库
        _repo_cache = YamlRepository(root_dir=data_dir)
        # 读取读取 YAML + 校验 + 缓存结构化对象
        _repo_cache.load()
    return _repo_cache


def _collect_api_ids(repo: YamlRepository) -> list[str]:
    """
      根据 repository 的统一生成最终要执行的 api_id 列表
    :param repo: YamlRepository (已 load)
    :return: 最终执行的 api_id 列表
    """
    return repo.list_runnable_api_id()


def _build_single_case_params(repo: YamlRepository):
    """
      根据 single.yaml 中每个 api 的参数条数, 收集 pytest 测试条数
      优先级排列:
        1.body
        2.params
        3.files

    :param repo: 已 load 的 yaml 仓库对象
    :return: list[pytest.param]: pytest 参数列表, 每项包含 api_id 和 data_index
    """
    # 初始化参数列表
    cases = []

    # 遍历最终可执行 api
    for api_id in _collect_api_ids(repo):
        # 获取接口定义对象
        api = repo.apis[api_id]
        # 读取 request 配置
        requests_node = api.request or {}

        # 收集 case 规则
        body_node = requests_node.get("body", None)
        params_node = requests_node.get("params", None)
        files_node = requests_node.get("files", None)

        # 收集条数默认 1 条, 因为会存在接口不需要上传数据的情况, 比如 get
        case_count = 1
        if isinstance(body_node, list):
            case_count = len(body_node)
        elif isinstance(params_node, list):
            case_count = len(params_node)
        elif isinstance(files_node, list):
            case_count = len(files_node)

        # 遍历 data 中每条数据
        for data_index in range(case_count):
            # 追加 pytest 参数项
            cases.append(
                # 构造一条参数化 case
                pytest.param(
                    api_id,
                    data_index,
                    id=f"{api_id}[data_{data_index}]"
                )
            )

    return cases


def _collect_flow_ids(repo: YamlRepository) -> list[str]:
    """
      根据 repository.flows 生成需要执行的 flow_id 列表 (当前结构只有一个 flow)
    :param repo: repo：YamlRepository (已 load)
    :return: 最终执行的 flow_id 列表
    """
    # 获取 flow 所有数据, 为假值时置 空dict
    flow = repo.flows or {}
    # 初始化输出的 flow_id 列表
    out = []
    for flow_id, flow_bundle in flow.items():
        # 若 flow 为 True, 则执行
        if bool(flow_bundle.is_run):
            out.append(flow_id)
    # 排序确保稳定
    out.sort()
    return out


def _resolve_allure_results_dir(config) -> Optional[Path]:
    """
      解析 pytest 当前运行的 --alluredir 目录, 返回 allure-results 目录 Path
    :param config: pytest Config 对象
    """
    # 初始化结果目录变量
    candidate = None
    try:
        # 读取 --alluredir 的值
        candidate = config.getoption("--alluredir")
    except Exception:
        pass
    # 若未读到, 则继续尝试插件内部 option 名
    if not candidate:
        candidate = getattr(getattr(config, "option", None), "allure_report_dir", None)

    # 若依旧为空, 则返回 None
    if not candidate:
        return None

    return Path(candidate)


def pytest_sessionstart(session):
    """
      在测试会话开始时生成 Allure 环境文件与分类文件
    :param session: pytest Session 对象
    """
    results_dir = _resolve_allure_results_dir(session.config)
    if not results_dir:
        return

    repo = _get_repo()
    project_root = PathTool.project_root(__file__, markers=("Data", "pyproject.toml", "run.py"))
    env_map = {
        "active_env": repo.config.active_env,
        "host": repo.config.env.get("host"),
        "project_root": project_root,
        "data_dir": _get_data_dir(),
    }
    AllureReporter.write_environment_file(results_dir, env_map)
    AllureReporter.write_categories_file(results_dir)


def pytest_generate_tests(metafunc):
    """
      作用:
        - pytest 钩子：动态生成参数
        - 在 pytest 收集阶段，基于 YAML 自动生成参数化用例

    :param metafunc: pytest 提供的元信息对象，用于判断测试函数需要哪些参数并进行参数化
    """
    # 获取并缓存仓库 (收集阶段首先执行, 因此需要读取仓库获取数据)
    repo = _get_repo()

    # 若测试函数需要 api_id 和 data_index 参数, 则收集 可运行 api_id 列表
    if {"api_id", "data_index"} <= set(metafunc.fixturenames):
        cases = _build_single_case_params(repo)
        # 参数化: 一个 api_id 生成一个测试用例
        metafunc.parametrize("api_id,data_index", cases)
        return

    # 若测试函数需要 flow_id 参数, 则收集 可运行 flow_id 列表
    if "flow_id" in metafunc.fixturenames:
        flow_ids = _collect_flow_ids(repo)
        metafunc.parametrize("flow_id", flow_ids, ids=flow_ids)


@pytest.fixture(scope="session")
def repo() -> YamlRepository:
    """
      session 级 fixture：仓库只创建一次;
      向测试运行阶段提供已 load 的 YamlRepository
    :return: YamlRepository: 已加载好的仓库
    """
    # 直接返回缓存仓库
    return _get_repo()


@pytest.fixture(scope="function")
def executor_fx(repo: YamlRepository) -> Executor:
    """
      作用:
      - 提供执行器对象
      - function 级 fixture：每条用例一个 executor (避免状态残留)
    :param repo: repo：YamlRepository , 已加载好的 yaml 内存仓库
    :return: executor：执行器实例
    """
    # 创建并返回 executor
    return Executor(repo)
