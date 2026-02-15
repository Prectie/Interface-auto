# -*- coding: utf-8 -*-  # 声明编码，避免中文注释乱码  #
from typing import Optional

import pytest  # 导入 pytest，用于 fixture 与钩子函数  #
from pathlib import Path  # 导入 Path，用于跨平台路径拼接  #

from Utils.path_utils import PathTool  # 导入路径工具，用于定位项目根目录  #
from Base.repository import YamlRepository  # 导入仓库，用于加载与缓存 YAML  #
from Runtime.executor import Executor  # 导入执行器，用于执行 single/multiple  #


_repo_cache: Optional[YamlRepository] = None  # 全局缓存 repository，避免收集阶段重复 load  #


def _get_data_dir() -> Path:  # 获取 Data 目录  #
    """
    目的/作用：
        从当前 conftest.py 的位置向上查找项目根目录，并定位到 Data 目录。  #
    参数说明：
        1) 无。  #
    返回值说明：
        1) Path：Data 目录的绝对路径。  #
    在系统中的作用：
        统一管理 YAML 数据路径，避免测试用例里硬编码路径。  #
    调用关系：
        1) 被 _get_repo 调用，用于构造 YamlRepository(root_dir)。  #
    """  # 方法说明结束  #
    project_root = PathTool.project_root(__file__, markers=("Data", "pyproject.toml", "run.py"))  # 查找包含 Data/pyproject/run.py 的目录作为根目录  #
    return project_root / "Data"  # 返回 Data 目录路径  #


def _get_repo() -> YamlRepository:  # 获取（并缓存）YamlRepository  #
    """
    目的/作用：
        在 pytest 收集阶段与运行阶段复用同一个 repository 实例，避免重复读取 YAML。  #
    参数说明：
        1) 无。  #
    返回值说明：
        1) YamlRepository：已 load 完成的仓库对象。  #
    在系统中的作用：
        让“参数化生成用例”与“运行时 fixture 提供仓库”使用同一份数据来源。  #
    调用关系：
        1) 被 pytest_generate_tests 调用，用于生成参数；  #
        2) 被 repo fixture 调用，用于返回仓库对象。  #
    """  # 方法说明结束  #
    global _repo_cache  # 声明使用全局变量  #
    if _repo_cache is None:  # 若缓存为空  #
        data_dir = _get_data_dir()  # 获取 Data 目录  #
        _repo_cache = YamlRepository(root_dir=data_dir)  # 初始化仓库（注意：root_dir 必须是 Path，不能是 str）  #
        _repo_cache.load()  # 读取 YAML + 严格校验 + 缓存结构化对象  #
    return _repo_cache  # 返回缓存仓库  #


def _collect_api_ids(repo: YamlRepository) -> list[str]:  # 收集 single 接口用例参数  #
    """
    目的/作用：
        根据 repository.apis 与 config.run_control 生成最终要执行的 api_id 列表。  #
    参数说明：
        1) repo：YamlRepository（已 load）。  #
    返回值说明：
        1) list[str]：最终参数化的 api_id 列表。  #
    在系统中的作用：
        把“运行控制（only/skip/is_run）”前置到收集阶段，减少无效用例生成。  #
    调用关系：
        1) 被 pytest_generate_tests 调用，用于参数化 api_id。  #
    """  # 方法说明结束  #
    cfg = repo.config  # 读取 config bundle  #
    rc = cfg.run_control or {}  # 读取 run_control（若为空则用空 dict）  #
    global_is_run = rc.get("is_run", True)  # 读取全局开关（默认 True）  #
    if not global_is_run:  # 若全局不运行  #
        return []  # 直接返回空列表（不生成任何 single 用例）  #

    only_apis = rc.get("only_apis", []) or []  # 读取白名单（为空表示不限制）  #
    skip_apis = set(rc.get("skip_apis", []) or [])  # 读取黑名单并转 set 便于过滤  #

    api_ids = list(repo.apis.keys())  # 获取全部 api_id  #
    api_ids.sort()  # 排序，保证用例顺序稳定  #

    if only_apis:  # 若配置了白名单  #
        api_ids = [x for x in api_ids if x in set(only_apis)]  # 仅保留白名单  #

    api_ids = [x for x in api_ids if x not in skip_apis]  # 剔除黑名单  #

    api_ids = [x for x in api_ids if repo.apis[x].is_run is not False]  # 剔除 api 级显式 is_run=false 的接口  #

    return api_ids  # 返回最终 api_id 列表  #


def _collect_flow_ids(repo: YamlRepository) -> list[str]:  # 收集 multiple 业务流参数  #
    """
    目的/作用：
        根据 repository.flows 生成 flow_id 列表（当前结构只有一个 flow）。  #
    参数说明：
        1) repo：YamlRepository（已 load）。  #
    返回值说明：
        1) list[str]：最终参数化的 flow_id 列表。  #
    在系统中的作用：
        把 flow 的 is_run 也放到收集阶段决定，避免生成无效 flow 用例。  #
    调用关系：
        1) 被 pytest_generate_tests 调用，用于参数化 flow_id。  #
    """  # 方法说明结束  #
    flow = repo.get_flow()  # 获取 flow bundle  #
    if not bool(flow.is_run):  # 若 flow 不运行  #
        return []  # 不生成 flow 用例  #
    fid = str(flow.flow_id).strip()  # 取 flow_id 并去空格  #
    return [fid]  # 当前结构仅一个 flow，所以返回单元素列表  #


def pytest_generate_tests(metafunc):  # pytest 钩子：动态生成参数  #
    """
    目的/作用：
        在 pytest 收集阶段，基于 YAML 自动生成参数化用例。  #
    参数说明：
        1) metafunc：pytest 提供的元信息对象，用于判断测试函数需要哪些参数并进行参数化。  #
    返回值说明：
        1) 无（通过 metafunc.parametrize 影响收集结果）。  #
    在系统中的作用：
        将“用例数据驱动”前置到收集阶段，做到 YAML -> 用例 的自动映射。  #
    调用关系：
        1) pytest 在收集测试用例时自动调用该钩子。  #
    """  # 方法说明结束  #
    repo = _get_repo()  # 获取并缓存仓库（收集阶段会读一次 YAML）  #

    if "api_id" in metafunc.fixturenames:  # 若测试函数需要 api_id 参数  #
        api_ids = _collect_api_ids(repo)  # 收集可运行 api_id 列表  #
        metafunc.parametrize("api_id", api_ids, ids=api_ids)  # 参数化：一个 api_id 生成一个测试用例  #

    if "flow_id" in metafunc.fixturenames:  # 若测试函数需要 flow_id 参数  #
        flow_ids = _collect_flow_ids(repo)  # 收集可运行 flow_id 列表  #
        metafunc.parametrize("flow_id", flow_ids, ids=flow_ids)  # 参数化：一个 flow_id 生成一个测试用例  #


@pytest.fixture(scope="session")  # session 级 fixture：仓库只创建一次  #
def repo() -> YamlRepository:  # 提供 repository 给运行阶段使用  #
    """
    目的/作用：
        向测试运行阶段提供已 load 的 YamlRepository。  #
    参数说明：
        1) 无。  #
    返回值说明：
        1) YamlRepository：已加载仓库。  #
    在系统中的作用：
        让 executor 在运行阶段拿到同一份 YAML 结构化数据。  #
    调用关系：
        1) 被 executor_fx 调用；  #
        2) 也可被你后续扩展的 fixture（如 allure 附件、日志）调用。  #
    """  # 方法说明结束  #
    return _get_repo()  # 直接返回缓存仓库  #


@pytest.fixture(scope="function")  # function 级 fixture：每条用例一个 executor（避免状态残留）  #
def executor_fx(repo: YamlRepository) -> Executor:  # 提供执行器对象  #
    """
    目的/作用：
        为每个测试用例提供一个新的 executor 实例，避免运行态数据互相污染。  #
    参数说明：
        1) repo：YamlRepository（session 级）。  #
    返回值说明：
        1) executor：执行器实例。  #
    在系统中的作用：
        作为 pytest 与框架执行层之间的桥接入口。  #
    调用关系：
        1) 被 test_single_api/test_flow 调用，用于执行接口或业务流。  #
    """  # 方法说明结束  #
    return Executor(repo)  # 创建并返回 executor  #
