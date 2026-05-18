# -*- coding: utf-8 -*-

"""
  pytest_autoapi item / collector:把 ApiCase / Scenario / TestPlan 映射成 pytest item.

  设计基线:
    - 一个 case / scenario / plan = 一个 pytest item（粗粒度）.
    - Scenario 有 datasets 时仍然是 1 个 item,dataset 多轮在 ``item.runtest()``
      调用 ``Executor.run_scenario`` 时由内核处理；dataset 信息体现在 Allure
      嵌套 step 名前缀（``[level_3] 启动任务``）.
    - item.runtest() 只负责:写 Allure 元数据 → 调 Executor 拿 RunResult →
      把每条 step 的请求/响应/提取/断言/上下文/异常挂到 ``allure.step`` 内 →
      把 RunResult 收集到 session 上下文,供 sessionfinish 聚合写 history.
"""

from __future__ import annotations

import traceback
from typing import Iterator, Iterable

import allure
import pytest
from _pytest.nodes import Item, Collector

from Engine.results import RunResult, StepResult
from Utils.allure_reporter import AllureReporter


class _AutoApiYamlFile(pytest.File):
    """
      AutoAPI 三种 YAML 文件的统一基类, 只负责接入 pytest 的文件收集体系。

      通俗理解:
        pytest 扫描到一个 YAML 文件时, 会先在 plugin.py 的 pytest_collect_file()
        里调用 XxxCollector.from_parent(parent, path=file_path)。这个 from_parent()
        不是我们自己写的, 而是 pytest.File 基类提供的标准工厂方法。

        from_parent(parent, path=file_path) 会创建一个 collector 对象, 并把
        当前文件路径保存到这个对象的 self.path 上。后续 pytest 调用 collect()
        时, 方法里的 self 就是“当前这个 collector 对象”。
    """

    def collect(self) -> Iterable[Item | Collector]:
        """
        collect() 来自 pytest 的 collector 协议。

        collector 负责“继续往下收集”, 通常 yield 出一个或多个 pytest.Item。
        这里的 yield 只是把 item 交给 pytest 的收集列表, 不是立刻执行测试;
        pytest 会等所有 item 收集完成、过滤完成后, 再调用 item.runtest()。
        """
        pass


class CasesCollector(_AutoApiYamlFile):
    """
      cases.yaml 收集器: 把 repo.cases 中的所有 case_id 转成 AutoApiCaseItem.
    """

    def collect(self) -> Iterator[pytest.Item]:
        ctx = getattr(self.session, "_autoapi", None)
        if ctx is None:
            return
        for case_id in sorted(ctx.repository.cases.keys()):
            yield AutoApiCaseItem.from_parent(self, name=case_id, case_id=case_id)


class ScenariosCollector(_AutoApiYamlFile):
    """
      Scenarios/*.yaml 收集器: 把当前 scenario YAML 文件里的场景转成 pytest item。

      self 是什么:
        self 就是当前这个 ScenariosCollector 对象。它由 plugin.py 中的
        ScenariosCollector.from_parent(parent, path=file_path) 创建。

      self.path.name 是什么:
        pytest.File 会把 from_parent() 传进来的 path=file_path 保存到 self.path。
        所以如果 pytest 当前扫描的是 Scenarios/login.yaml, 那么:
          self.path      ~= Scenarios/login.yaml
          self.path.name == "login.yaml"

      为什么要比较 scenario.source 和 self.path.name:
        repository.load() 已经一次性加载了所有 Scenarios/*.yaml,
        ctx.repository.scenarios 里放的是全部场景。当前 collector 只应该产出
        当前文件里的场景, 否则每个 scenario 文件的 collector 都会把全部场景
        yield 一遍, 造成重复收集。
    """

    def collect(self) -> Iterator[pytest.Item]:
        # self.session 是 pytest 给当前 collector 绑定的全局 Session;
        # _autoapi 是 plugin.py 在 pytest_sessionstart() 中挂上去的 AutoAPI 上下文。
        ctx = getattr(self.session, "_autoapi", None)
        if ctx is None:
            return

        # 遍历所有已加载的 scenario, 但这里只收集 “属于当前 YAML 文件” 的那部分。
        for scenario in ctx.repository.scenarios.values():
            # self.path.name 是当前 collector 负责的文件名, scenario.source 是该场景来源文件名
            # 当前 collector 只处理当前 YAML 文件里的场景(一个yaml文件里包含多个场景)
            # 不是这个文件的场景则跳过收集, 避免重复收集
            if scenario.source != self.path.name:
                continue

            # yield 表示 "发现一个 pytest item, 交给 pytest 收集"。
            # 这里不会马上执行 scenario, 真正执行发生在 AutoApiScenarioItem.runtest()。
            # from_parent(self, ...) 里的 self 表示: 把新 item 挂到当前 collector 下面。
            yield AutoApiScenarioItem.from_parent(
                self,
                name=scenario.id,
                scenario_id=scenario.id,
            )


class PlansCollector(_AutoApiYamlFile):
    """
      plans.yaml 收集器:把 repo.plans 中的所有 plan_id 转成 AutoApiPlanItem.
    """

    def collect(self) -> Iterator[pytest.Item]:
        ctx = getattr(self.session, "_autoapi", None)
        if ctx is None:
            return
        for plan_id in sorted(ctx.repository.plans.keys()):
            yield AutoApiPlanItem.from_parent(self, name=plan_id, plan_id=plan_id)


class AutoApiCaseItem(pytest.Item):
    """
      单个 ApiCase 对应的 pytest item.runtest() 内只调 Executor.run_case
      并把详情挂到 Allure,不重写 step 调度.
    """

    def __init__(self, *, case_id: str, **kwargs):
        super().__init__(**kwargs)
        self.case_id = case_id

    def runtest(self) -> None:
        # 获取 AutoAPI 上下文, 拿到配置对象、仓库对象、执行器
        ctx = self.session._autoapi
        # 获取要执行的 case
        case = ctx.repository.get_case(self.case_id)
        active_env = ctx.config.env_name or ctx.repository.config.active_env
        AllureReporter.set_case_metadata(self.case_id, case.use, active_env)
        result = ctx.executor.run_case(
            self.case_id,
            env_name=ctx.config.env_name,
            run_id=ctx.config.run_id,
        )
        ctx.run_results.append(result)
        _attach_run_steps(result)
        if result.status != "passed":
            pytest.fail(_failure_summary(result), pytrace=False)

    def reportinfo(self) -> tuple:
        # 让 pytest report 行显示 "case_xxx" 而非整行模块路径,便于人眼快速定位.
        return self.path, 0, f"case::{self.case_id}"


class AutoApiScenarioItem(pytest.Item):
    """
      单个 Scenario 对应的 pytest item.runtest() 内调 Executor.run_scenario,
      多 dataset 仍然由内核遍历,dataset 信息体现在 step 名前缀.
    """

    def __init__(self, *, scenario_id: str, **kwargs):
        super().__init__(**kwargs)
        self.scenario_id = scenario_id

    def runtest(self) -> None:
        ctx = self.session._autoapi  # type: ignore[attr-defined]
        active_env = ctx.config.env_name or ctx.repository.config.active_env
        AllureReporter.set_scenario_metadata(self.scenario_id, active_env)
        result = ctx.executor.run_scenario(
            self.scenario_id,
            env_name=ctx.config.env_name,
            run_id=ctx.config.run_id,
        )
        ctx.run_results.append(result)
        _attach_run_steps(result)
        if result.status != "passed":
            pytest.fail(_failure_summary(result), pytrace=False)

    def reportinfo(self) -> tuple:
        return self.path, 0, f"scenario::{self.scenario_id}"


class AutoApiPlanItem(pytest.Item):
    """
      单个 TestPlan 对应的 pytest item.runtest() 内调 Executor.run_plan,
      plan 内 scenarios + cases 全部由内核串联,外层只关心整体成败.
    """

    def __init__(self, *, plan_id: str, **kwargs):
        super().__init__(**kwargs)
        self.plan_id = plan_id

    def runtest(self) -> None:
        ctx = self.session._autoapi  # type: ignore[attr-defined]
        active_env = ctx.config.env_name or ctx.repository.config.active_env
        AllureReporter.set_plan_metadata(self.plan_id, active_env)
        result = ctx.executor.run_plan(
            self.plan_id,
            env_name=ctx.config.env_name,
            run_id=ctx.config.run_id,
        )
        ctx.run_results.append(result)
        _attach_run_steps(result)
        if result.status != "passed":
            pytest.fail(_failure_summary(result), pytrace=False)

    def reportinfo(self) -> tuple:
        return self.path, 0, f"plan::{self.plan_id}"


def _attach_run_steps(result: RunResult) -> None:
    """
      把 RunResult.steps 转成 Allure 嵌套 step:每个 step 内挂请求 / 响应 /
      提取 / 断言 / 上下文 / 异常详情,让用户直接在 testcase 详情页看到全链路.
    """
    for index, step in enumerate(result.steps, start=1):
        title = _build_step_title(step, index)
        with allure.step(title):
            AllureReporter.attach_prepared_request(step.request)
            AllureReporter.attach_response_snapshot(step.response)
            AllureReporter.attach_extract_out(step.extract_out)
            for assert_index, assertion in enumerate(step.assertions, start=1):
                AllureReporter.attach_assertion_result(assert_index, assertion)
            if step.context_snapshot:
                AllureReporter.attach_json("上下文快照", step.context_snapshot)
            if step.error is not None:
                # step.error 此时已脱离 except 块,必须显式格式化 traceback,
                # 不能依赖 traceback.format_exc() 取当前 sys.exc_info.
                tb_text = "".join(
                    traceback.format_exception(
                        type(step.error),
                        step.error,
                        step.error.__traceback__,
                    )
                )
                AllureReporter.attach_exception(step.error, traceback_text=tb_text)


def _build_step_title(step: StepResult, index: int) -> str:
    label = step.step_id or step.case_id
    prefix = f"{index:02d}."
    if step.dataset_name:
        return f"{prefix} [{step.dataset_name}] {label}"
    return f"{prefix} {label}"


def _failure_summary(result: RunResult) -> str:
    problem = next((step for step in result.steps if step.status != "passed"), None)
    if problem is None:
        return f"AutoAPI {result.target_type} {result.target_id} 失败 (status={result.status})"
    label = problem.step_id or problem.case_id
    return (
        f"AutoAPI {result.target_type} {result.target_id} 失败: "
        f"step={label}, status={problem.status}"
    )
