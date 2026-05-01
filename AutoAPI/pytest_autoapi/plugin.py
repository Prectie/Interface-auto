# -*- coding: utf-8 -*-

"""
  pytest_autoapi plugin:实现 pytest 与 AutoAPI YAML 资产之间的桥接 hook.

  生命周期约定（参考 plans/20 §Phase B 设计基线）:
    - pytest_addoption       注册 --autoapi-data / --autoapi-env / --autoapi-target / --autoapi-run-id
    - pytest_configure       仅当 --autoapi-data 存在时启用 AutoAPI 链路,避免污染框架内单测
    - pytest_sessionstart    一次性 YamlRepository.load + Executor + 写 alluredir/environment+categories
    - pytest_collect_file    识别 cases.yaml / Scenarios/*.yaml / plans.yaml,分别 yield 三类 item
    - pytest_collection_modifyitems  按 --autoapi-target 过滤 items
    - pytest_sessionfinish   聚合 RunResult → 写 history → 生成 HTML → 暴露模块级 holder

  模块级 holder 命名规则（重要）:
    - LAST_RUN_RESULT       最近一次 sessionfinish 聚合的 RunResult,单 target 时直接复用
                            Executor 产出的对象
    - LAST_RUN_ARTIFACTS    最近一次 sessionfinish 触发的 Allure HTML 产物（含 results/report dir、warning）
    - LAST_SENSITIVE_KEYS   最近一次 sessionstart 加载的 config.sensitive_keys,
                            run.py 用它做 stdout 脱敏

  这里为什么要用模块级变量？
  因为 pytest 插件 hook 是由 pytest 调用的,普通 CLI 代码不容易直接拿到 hook 内部的局部变量.
  所以这里用模块级 holder 做一次 "桥接": pytest 插件内部执行完,把结果放到模块变量里,外部再通过模块路径读取
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import List, Optional

from Core.repository import YamlRepository
from Engine.executor import Executor
from Engine.history_writer import HistoryWriter
from Engine.results import RunResult, StepResult
from Utils.allure_reporter import AllureReporter
from Utils.allure_runtime import AllureArtifacts, AllureRuntimeReporter

from pytest_autoapi.items import (
    AutoApiCaseItem,
    AutoApiPlanItem,
    AutoApiScenarioItem,
    CasesCollector,
    PlansCollector,
    ScenariosCollector,
)


# pytest 执行结束后,给外部代码读取本次运行结果的临时出口
LAST_RUN_RESULT: Optional[RunResult] = None
LAST_RUN_ARTIFACTS: Optional[AllureArtifacts] = None
LAST_SENSITIVE_KEYS: List[str] = []


class AutoApiSessionConfig:
    """
    作用:
      把命令行参数整理成一个 session(pytest生命周期的 session) 级只读配置对象
        - plugin 启动后从 CLI 一次性收集到的命令配置:data_root / env / target / run_id.
        - session 全程只读,不允许中途变动.

    好处:
      1. 集中管理插件启动参数,避免到处 `getoption`
    """

    def __init__(
        self,
        *,
        data_root: Path,
        env_name: Optional[str],
        target: Optional[str],
        run_id: str,
    ):
        self.data_root = data_root
        self.env_name = env_name
        self.target = target
        self.run_id = run_id


class AutoApiSessionContext:
    """
    作用:
      解决 pytest session 运行过程中,多个 hook 和多个 item 之间需要共享同一套 AutoAPI 对象
        - session 级共享上下文:repo / executor / 已执行 RunResult.
        - 每个 item.runtest() 通过 ``session._autoapi`` 访问.
    """

    def __init__(
        self,
        *,
        config: AutoApiSessionConfig,
        repository: YamlRepository,
        executor: Executor,
    ):
        self.config = config
        self.repository = repository
        self.executor = executor
        self.run_results: List[RunResult] = []


def pytest_addoption(parser):
    """
      为 AutoAPI 注册 4 个 CLI 选项；不会污染 pytest 已有选项命名空间.
    """
    # getgroup() 是 pytest 命令行参数 parser 提供的方法,用来创建或获取一个 "参数分组"
    group = parser.getgroup("autoapi", "AutoAPI YAML 测试执行器")
    group.addoption(
        "--autoapi-data",
        action="store",
        default=None,
        help="YAML 资产目录（含 config.yaml/apis.yaml/cases.yaml/Scenarios/plans.yaml）",
    )
    group.addoption(
        "--autoapi-env",
        action="store",
        default=None,
        help="覆盖 config.yaml.active_env",
    )
    group.addoption(
        "--autoapi-target",
        action="store",
        default=None,
        help="单 target 选择，例如 case:case_xxx / scenario:scn_xxx / plan:plan_xxx",
    )
    group.addoption(
        "--autoapi-run-id",
        action="store",
        default=None,
        help="本次运行的 run_id，不传则自动生成 uuid hex",
    )


def pytest_configure(config):
    """
    调用时机:
      pytest 已经解析完命令行参数、初始化好 config 对象之后, 正式开始收集测试之前

    作用:
      插件配置初始化
       - 仅当 --autoapi-data 给出时启用 AutoAPI 插件, 保证普通 pytest 测试不受影响
    """
    # 获取 YAML 数据所在目录
    data_root = config.getoption("--autoapi-data")
    if data_root is None:
        # 若为空, 则置为 None, 后续的 hook 就不启动
        config._autoapi_session_config = None
        return

    # 获取用户输入 并合并后的的命令
    config._autoapi_session_config = AutoApiSessionConfig(
        data_root=Path(data_root),
        env_name=config.getoption("--autoapi-env"),
        target=config.getoption("--autoapi-target"),
        run_id=config.getoption("--autoapi-run-id") or uuid.uuid4().hex,
    )


def pytest_sessionstart(session):
    """
      session 启动钩子: 加载 YAML 资产、构造 Executor、写 alluredir 元数据.
    """
    cfg = getattr(session.config, "_autoapi_session_config", None)
    if cfg is None:
        return
    # 加载 yaml 数据
    repo = YamlRepository(cfg.data_root)
    repo.load()

    # 构造执行器
    executor = Executor(repo)
    session._autoapi = AutoApiSessionContext(
        config=cfg,
        repository=repo,
        executor=executor,
    )

    global LAST_SENSITIVE_KEYS
    LAST_SENSITIVE_KEYS = list(repo.config.sensitive_keys or [])

    alluredir = _resolve_alluredir(session.config)
    if alluredir is not None:
        active_env = cfg.env_name or repo.config.active_env
        AllureReporter.write_environment_file(
            alluredir,
            {
                "run_id": cfg.run_id,
                "data_root": str(cfg.data_root),
                "env": active_env,
                "target": cfg.target or "",
            },
        )
        AllureReporter.write_categories_file(alluredir)


def pytest_collect_file(parent, file_path):
    """
      识别 ``<data_root>/cases.yaml``、``<data_root>/Scenarios/*.yaml`` 与
      ``<data_root>/plans.yaml`` 三类 YAML 文件,分别交给对应 collector.

      注:file_path.parent.resolve() 与 cfg.data_root.resolve() 比较,确保跨
      平台（Windows ``D:\\..`` vs 用户输入相对路径）路径判等正确.
    """
    cfg = getattr(parent.config, "_autoapi_session_config", None)
    if cfg is None:
        return None
    name = file_path.name
    parent_dir = file_path.parent
    data_root = cfg.data_root.resolve()
    parent_resolved = parent_dir.resolve()

    if name == "cases.yaml" and parent_resolved == data_root:
        return CasesCollector.from_parent(parent, path=file_path)
    if name == "plans.yaml" and parent_resolved == data_root:
        return PlansCollector.from_parent(parent, path=file_path)
    if (
        file_path.suffix == ".yaml"
        and parent_dir.name == "Scenarios"
        and parent_dir.parent.resolve() == data_root
    ):
        return ScenariosCollector.from_parent(parent, path=file_path)
    return None


def pytest_collection_modifyitems(config, items):
    """
      按 --autoapi-target 过滤 items；未传 target 时保留全部 collected items.
    """
    cfg = getattr(config, "_autoapi_session_config", None)
    if cfg is None or not cfg.target:
        return
    target_kind, _, target_id = cfg.target.partition(":")
    if not target_id:
        return

    keep = []
    for item in items:
        if (
            isinstance(item, AutoApiCaseItem)
            and target_kind == "case"
            and item.case_id == target_id
        ):
            keep.append(item)
        elif (
            isinstance(item, AutoApiScenarioItem)
            and target_kind == "scenario"
            and item.scenario_id == target_id
        ):
            keep.append(item)
        elif (
            isinstance(item, AutoApiPlanItem)
            and target_kind == "plan"
            and item.plan_id == target_id
        ):
            keep.append(item)

    deselected = [item for item in items if item not in keep]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
    items[:] = keep


def pytest_sessionfinish(session, exitstatus):
    """
      session 收束钩子:聚合 run_results → 写 JSONL history → 生成 Allure HTML →
      暴露模块级 holder 给 run.py 的 CLI 翻译层使用.
    """
    global LAST_RUN_RESULT, LAST_RUN_ARTIFACTS

    ctx = getattr(session, "_autoapi", None)
    if ctx is None:
        return
    if not ctx.run_results:
        LAST_RUN_RESULT = None
        LAST_RUN_ARTIFACTS = None
        return

    aggregate = _aggregate_run_results(ctx)
    LAST_RUN_RESULT = aggregate

    HistoryWriter().write_run(aggregate)

    alluredir = _resolve_alluredir(session.config)
    LAST_RUN_ARTIFACTS = _emit_allure_html(aggregate, alluredir=alluredir)


def _aggregate_run_results(ctx: AutoApiSessionContext) -> RunResult:
    """
      单 target 模式（CLI run.py 主路径）下只会有 1 个 RunResult,直接返回,
      字段与 v0.1 完全一致.多 target（裸 pytest 全量跑）模式下做最小合并:
      取首尾时间戳 + 拼接 steps + 聚合 status,保持 history JSONL 行为可解释.
    """
    if len(ctx.run_results) == 1:
        return ctx.run_results[0]

    cfg = ctx.config
    all_steps: List[StepResult] = []
    for item in ctx.run_results:
        all_steps.extend(item.steps)

    if any(item.status == "error" for item in ctx.run_results):
        status = "error"
    elif any(item.status == "failed" for item in ctx.run_results):
        status = "failed"
    else:
        status = "passed"

    target_kind = cfg.target.partition(":")[0] if cfg.target else "batch"
    target_id = cfg.target.partition(":")[2] if cfg.target else "batch"

    return RunResult(
        run_id=cfg.run_id,
        target_type=target_kind or "batch",
        target_id=target_id or "batch",
        env=ctx.run_results[0].env,
        status=status,
        started_at=ctx.run_results[0].started_at,
        ended_at=ctx.run_results[-1].ended_at,
        duration_ms=sum(float(item.duration_ms or 0.0) for item in ctx.run_results),
        steps=all_steps,
        error=next((item.error for item in ctx.run_results if item.error), None),
    )


def _emit_allure_html(result: RunResult, *, alluredir: Optional[Path]) -> AllureArtifacts:
    """
      在 sessionfinish 内生成 HTML 报告.alluredir 为空时退化到默认布局
      ``Reports/allure-results/<run_id>``,与 v0.1 stdout 字面保持一致.
    """
    return AllureRuntimeReporter().generate_html_for_run(
        result.run_id,
        results_dir=alluredir,
    )


def _resolve_alluredir(config) -> Optional[Path]:
    """
      读取 allure-pytest 注册的 ``--alluredir`` 选项；若用户未传,返回 None,
      由调用方决定回退路径.
    """
    raw = getattr(config.option, "allure_report_dir", None)
    if not raw:
        return None
    return Path(raw)
