# -*- coding: utf-8 -*-
from typing import Optional

import pytest
from pathlib import Path

from Utils.path_utils import PathTool
from Base.repository import YamlRepository
from Runtime.executor import Executor

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
      根据 repository.apis 与 config.run_control 生成最终要执行的 api_id 列表
    :param repo: YamlRepository (已 load)
    :return: 最终执行的 api_id 列表
    """
    # 读取 config bundle
    cfg = repo.config
    # 读取 run_control (若为空则用空 dict)
    rc = cfg.run_control or {}
    # 读取全局开关 (默认 True)
    global_is_run = rc.get("is_run", True)
    # 若全局不运行, 则直接返回空列表 (不生成任何 single 用例)
    if not global_is_run:
        return []

    # 读取白名单 (为空表示不限制)
    only_apis = rc.get("only_apis", []) or []
    # 读取黑名单并转 set 便于过滤
    skip_apis = set(rc.get("skip_apis", []) or [])

    # 获取全部 api_id (也是最后执行 api 名单)
    api_ids = list(repo.apis.keys())
    # 执行 接口库时, 谁先谁后不重要, 因为是单个执行
    # 因此排序，保证每次执行的用例顺序稳定
    api_ids.sort()

    # 若配置了白名单, 则仅保留白名单
    if only_apis:
        api_ids = [x for x in api_ids if x in set(only_apis)]

    # 去掉黑名单
    api_ids = [x for x in api_ids if x not in skip_apis]

    # 剔除 api 级显式 is_run=false 的接口
    api_ids = [x for x in api_ids if repo.apis[x].is_run is not False]

    # 返回最终要执行的 api_id 列表
    return api_ids


def _collect_flow_ids(repo: YamlRepository) -> list[str]:
    """
      根据 repository.flows 生成需要执行的 flow_id 列表 (当前结构只有一个 flow)
    :param repo: repo：YamlRepository (已 load)
    :return: 最终执行的 flow_id 列表
    """
    # 获取 flow 所有数据
    flow = repo.get_flow()
    # 若 flow 禁止运行, 则不生成 flow 用例
    if not bool(flow.is_run):
        return []
    # 取 flow_id
    fid = str(flow.flow_id)

    # 当前结构仅一个 flow，所以先返回单元素列表
    return [fid]


def pytest_generate_tests(metafunc):
    """
      作用:
        - pytest 钩子：动态生成参数
        - 在 pytest 收集阶段，基于 YAML 自动生成参数化用例

    :param metafunc: pytest 提供的元信息对象，用于判断测试函数需要哪些参数并进行参数化
    """
    # 获取并缓存仓库 (收集阶段首先执行, 因此需要读取仓库获取数据)
    repo = _get_repo()

    # 若测试函数需要 api_id 参数, 则收集 可运行 api_id 列表
    if "api_id" in metafunc.fixturenames:
        api_ids = _collect_api_ids(repo)
        # 参数化: 一个 api_id 生成一个测试用例
        metafunc.parametrize("api_id", api_ids, ids=api_ids)

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
