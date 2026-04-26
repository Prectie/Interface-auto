# -*- coding: utf-8 -*-

"""
  pytest_autoapi item / collector：把 ApiCase / Scenario / TestPlan 映射成 pytest item。

  设计基线（参考 plans/20 §Phase B 设计基线）：
  - 一个 case / scenario / plan = 一个 pytest item（粗粒度）。
  - Scenario 有 datasets 时仍然是 1 个 item，dataset 多轮在 ``item.runtest()``
    调用 ``Executor.run_scenario`` 时由内核处理；dataset 信息体现在 Allure
    嵌套 step 名前缀（``[level_3] 启动任务``）。
  - item.runtest() 只负责：写 Allure 元数据 → 调 Executor 拿 RunResult →
    把每条 step 的请求/响应/提取/断言/上下文/异常挂到 ``allure.step`` 内 →
    把 RunResult 收集到 session 上下文，供 sessionfinish 聚合写 history。
"""

from __future__ import annotations

import traceback
from typing import Iterator

import allure
import pytest

from Engine.results import RunResult, StepResult
from Utils.allure_reporter import AllureReporter


class _AutoApiYamlFile(pytest.File):
    """
      AutoAPI 三种 YAML 文件的统一基类，仅做继承标识。
    """


class CasesCollector(_AutoApiYamlFile):
    """
      cases.yaml 收集器：把 repo.cases 中的所有 case_id 转成 AutoApiCaseItem。
    """

    def collect(self) -> Iterator[pytest.Item]:
        ctx = getattr(self.session, "_autoapi", None)
        if ctx is None:
            return
        for case_id in sorted(ctx.repository.cases.keys()):
            yield AutoApiCaseItem.from_parent(self, name=case_id, case_id=case_id)


class ScenariosCollector(_AutoApiYamlFile):
    """
      Scenarios/*.yaml 收集器：仅产出 ``source == self.path.name`` 的场景项，
      避免一个 scenario 文件 yield 多个其它文件的 scenario。
    """

    def collect(self) -> Iterator[pytest.Item]:
        ctx = getattr(self.session, "_autoapi", None)
        if ctx is None:
            return
        for scenario in ctx.repository.scenarios.values():
            if scenario.source != self.path.name:
                continue
            yield AutoApiScenarioItem.from_parent(
                self,
                name=scenario.id,
                scenario_id=scenario.id,
            )


class PlansCollector(_AutoApiYamlFile):
    """
      plans.yaml 收集器：把 repo.plans 中的所有 plan_id 转成 AutoApiPlanItem。
    """

    def collect(self) -> Iterator[pytest.Item]:
        ctx = getattr(self.session, "_autoapi", None)
        if ctx is None:
            return
        for plan_id in sorted(ctx.repository.plans.keys()):
            yield AutoApiPlanItem.from_parent(self, name=plan_id, plan_id=plan_id)


class AutoApiCaseItem(pytest.Item):
    """
      单个 ApiCase 对应的 pytest item。runtest() 内只调 Executor.run_case
      并把详情挂到 Allure，不重写 step 调度。
    """

    def __init__(self, *, case_id: str, **kwargs):
        super().__init__(**kwargs)
        self.case_id = case_id

    def runtest(self) -> None:
        ctx = self.session._autoapi  # type: ignore[attr-defined]
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
        # 让 pytest report 行显示 "case_xxx" 而非整行模块路径，便于人眼快速定位。
        return self.path, 0, f"case::{self.case_id}"


class AutoApiScenarioItem(pytest.Item):
    """
      单个 Scenario 对应的 pytest item。runtest() 内调 Executor.run_scenario,
      多 dataset 仍然由内核遍历，dataset 信息体现在 step 名前缀。
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
      单个 TestPlan 对应的 pytest item。runtest() 内调 Executor.run_plan,
      plan 内 scenarios + cases 全部由内核串联，外层只关心整体成败。
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
      把 RunResult.steps 转成 Allure 嵌套 step：每个 step 内挂请求 / 响应 /
      提取 / 断言 / 上下文 / 异常详情，让用户直接在 testcase 详情页看到全链路。
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
                # step.error 此时已脱离 except 块，必须显式格式化 traceback,
                # 不能依赖 traceback.format_exc() 取当前 sys.exc_info。
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
