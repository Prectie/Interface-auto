# -*- coding: utf-8 -*-

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


from Core.composer import Composer
from Core.context import RuntimeContext
from Core.repository import YamlRepository
from Engine.extractor import Extractor

from Engine.request_resolver import RequestResolver
from Engine.transport import SessionTransport, TransportBase
from Engine.action_runner import ActionOutcome, run_action
from Engine.assertion_engine import AssertionEngine
from Engine.results import RunResult, StepResult, ResponseSnapshot
from Exceptions.AutoApiException import ExceptionCode
from Schema.data_models import ExecutableCase, ExecutableStep, HookStep
from Utils.log_utils import LoggerManager

logger = LoggerManager.get_logger()


def execute_one(
    executable: "ExecutableCase | ExecutableStep",
    ctx: RuntimeContext,
    env,
    transport: TransportBase,
    *,
    resolver: RequestResolver,
    extractor: Extractor,
    assert_engine: AssertionEngine,
    request_defaults: Dict[str, Any],
) -> StepResult:
    """
      原子执行入口:把"已经合成好的 ExecutableCase / ExecutableStep"发出去,并组装为单条 StepResult.

      纯函数化设计要点:
      - 不持有调度状态（hooks / 多 step / dataset 等编排责任在调度层）.
      - 协作组件（resolver / extractor / assert_engine / request_defaults）通过关键字参数显式注入,
        v0.1 由 Executor 注入；v0.2 由 pytest_autoapi 插件注入.
      - 异常分类、duration_ms 计算、StepResult 字段集合与 v0.1 _execute_executable 严格等价.
    """
    started_perf = time.perf_counter()
    prepared = None
    response_snapshot = None
    extract_out: Dict[str, Any] = {}
    assertions: List = []
    try:
        prepared = resolver.resolve_executable(
            executable,
            request_defaults,
            ctx,
            env,
        )
        response_obj = transport.send(
            prepared,
            api_id=executable.api_id,
            step_id=getattr(executable, "step_id", None),
        )
        response_snapshot = ResponseSnapshot.format_response(response_obj)
        request_snapshot = prepared.to_dict()
        extract_out = extractor.apply(
            rules=executable.extract,
            response=response_obj,
            ctx=ctx,
            api_id=executable.api_id,
            step_id=getattr(executable, "step_id", None),
            request=request_snapshot,
        )
        assertions = assert_engine.assert_all(
            assertions=executable.assertions,
            response=response_obj,
            ctx=ctx,
            api_id=executable.api_id,
            step_id=getattr(executable, "step_id", None),
            request_snapshot=request_snapshot,
        )
        return StepResult(
            case_id=executable.case_id,
            api_id=executable.api_id,
            status="passed",
            step_id=getattr(executable, "step_id", None),
            scenario_id=getattr(executable, "scenario_id", None),
            request=prepared,
            response=response_snapshot,
            extract_out=extract_out,
            assertions=assertions,
            context_snapshot=ctx.snapshot(),
            duration_ms=_perf_to_ms(started_perf),
        )
    except Exception as e:
        return StepResult(
            case_id=executable.case_id,
            api_id=executable.api_id,
            status=_classify_error_status(e),
            step_id=getattr(executable, "step_id", None),
            scenario_id=getattr(executable, "scenario_id", None),
            request=prepared,
            response=response_snapshot,
            extract_out=extract_out,
            assertions=assertions,
            context_snapshot=ctx.snapshot(),
            error=e,
            duration_ms=_perf_to_ms(started_perf),
        )


def _classify_error_status(exc: BaseException) -> str:
    """
      将异常映射为 StepResult.status:
      - 断言失败（ExceptionCode.ASSERT_ERROR）映射为 "failed"
      - 其它异常映射为 "error"
    """
    error_context = getattr(exc, "error_context", None)
    error_code = getattr(error_context, "error_code", None)
    if error_code == ExceptionCode.ASSERT_ERROR:
        return "failed"
    return "error"


def _perf_to_ms(started_perf: float) -> float:
    """
      把 perf_counter 起点换算为耗时毫秒数,保留 3 位小数.
    """
    return round((time.perf_counter() - started_perf) * 1000, 3)


class Executor:
    """
      执行器, 只编排流程, 不做其它处理
      负责串起 repository/context/resolver/transport/extractor/assertion,完成 case/scenario/plan 执行流程.
    """
    def __init__(self, repo: YamlRepository):
        # 保存仓库
        self.repo = repo

        # 初始化请求解析器
        self.resolver = RequestResolver()

        # 初始化提取器
        self.extractor = Extractor()

        # 初始化断言引擎
        self.assert_engine = AssertionEngine()


        # 新模型使用 Composer 做资产合成,不复用旧 deep_merge 链路.
        self.composer = Composer(repo.config)

    def run_case(
        self,
        case_id: str,
        *,
        env_name: Optional[str] = None,
        run_id: Optional[str] = None,
        ctx: Optional[RuntimeContext] = None,
        transport: Optional[TransportBase] = None,
    ) -> RunResult:
        """
          执行一个 ApiCase.
        """
        resolved_env_name = env_name or self.repo.config.active_env
        return self._run_case_core(
            case_id,
            env_name=resolved_env_name,
            run_id=run_id,
            ctx=ctx,
            transport=transport,
        )

    def run_scenario(
        self,
        scenario_id: str,
        *,
        env_name: Optional[str] = None,
        run_id: Optional[str] = None,
        transport: Optional[TransportBase] = None,
    ) -> RunResult:
        """
          按 steps 顺序执行一个 Scenario.
        """
        scenario = self.repo.get_scenario(scenario_id)
        resolved_env_name = env_name or scenario.env or self.repo.config.active_env
        run_id = run_id or self._new_run_id()
        return self._run_scenario_core(
            scenario_id,
            env_name=resolved_env_name,
            run_id=run_id,
            ctx=None,
            transport=transport,
        )

    def run_plan(
        self,
        plan_id: str,
        *,
        env_name: Optional[str] = None,
        run_id: Optional[str] = None,
        transport: Optional[TransportBase] = None,
    ) -> RunResult:
        """
          执行一个 TestPlan.
        """
        run_id = run_id or self._new_run_id()
        resolved_env_name = env_name or self.repo.config.active_env
        return self._run_plan_core(
            plan_id,
            env_name=resolved_env_name,
            run_id=run_id,
            ctx=None,
            transport=transport,
        )

    def _run_case_core(
        self,
        case_id: str,
        *,
        env_name: str,
        run_id: str,
        ctx: Optional[RuntimeContext],
        transport: Optional[TransportBase],
    ) -> RunResult:
        env = self.repo.get_env(env_name)
        ctx = ctx or RuntimeContext(dict(env.variables))
        transport = transport or SessionTransport()
        started_at = self._now()
        started_perf = time.perf_counter()
        case = self.repo.get_case(case_id)
        api = self.repo.get_api(case.use)
        executable = self.composer.compose_case(api, case)
        step_results = self._execute_executable_with_hooks(executable, ctx, env, transport)
        ended_at = self._now()
        status = self._aggregate_status(step_results)
        return RunResult(
            run_id=run_id,
            target_type="case",
            target_id=case_id,
            env=env_name,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=self._duration_ms(started_perf),
            steps=step_results,
            error=next((item.error for item in step_results if item.error), None),
        )

    def _run_scenario_core(
        self,
        scenario_id: str,
        *,
        env_name: str,
        run_id: str,
        ctx: Optional[RuntimeContext],
        transport: Optional[TransportBase],
    ) -> RunResult:
        scenario = self.repo.get_scenario(scenario_id)
        env = self.repo.get_env(env_name)
        ctx = ctx or RuntimeContext(dict(env.variables))
        transport = transport or SessionTransport()
        started_at = self._now()
        started_perf = time.perf_counter()
        step_results: List[StepResult] = []
        datasets = scenario.datasets or [None]

        for dataset_index, dataset in enumerate(datasets, start=1):
            # 每轮 dataset 都使用独立上下文,避免提取变量跨轮污染.
            base_snapshot = ctx.snapshot()
            dataset_ctx = RuntimeContext(base_snapshot)
            if dataset is not None:
                dataset_ctx.update(dataset.variables)

            iteration_results = self._run_scenario_iteration(
                scenario,
                dataset_ctx,
                env,
                transport,
                dataset_name=dataset.name if dataset is not None else None,
                dataset_index=dataset_index if dataset is not None else None,
            )
            step_results.extend(iteration_results)

            if self._aggregate_status(iteration_results) != "passed":
                break

        ended_at = self._now()
        status = self._aggregate_status(step_results)
        return RunResult(
            run_id=run_id,
            target_type="scenario",
            target_id=scenario_id,
            env=env_name,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=self._duration_ms(started_perf),
            steps=step_results,
            error=next((item.error for item in step_results if item.error), None),
        )

    def _run_scenario_iteration(
        self,
        scenario,
        ctx: RuntimeContext,
        env,
        transport: TransportBase,
        *,
        dataset_name: Optional[str],
        dataset_index: Optional[int],
    ) -> List[StepResult]:
        """
          单轮 dataset 内的场景调度顺序:
            1. before_steps （hooks, 仅辅助 wait/sql/script）
            2. steps        （主流程, 支持 use 和 inline action）
            3. after_steps  （hooks, 仅在主流程通过时执行）
            4. scenario.assertions （仅在主流程 + after_steps 都通过时执行）

          v0.2 取消 finally_steps 概念: 兜底语义改由 steps[].always_run=True 承担,
          因此本函数不再做"无论成败都执行的兜底队列".
        """
        step_results: List[StepResult] = []

        before_results = self._run_hook_step_list(
            scenario.before_steps,
            scenario_id=scenario.id,
            ctx=ctx,
            dataset_name=dataset_name,
            dataset_index=dataset_index,
        )
        step_results.extend(before_results)

        # v0.2: 即使 before_steps 失败, 也要尝试执行 steps[] 中标了 always_run 的兜底步骤.
        # 因此 main_passed 只用来决定 after_steps / assertions 是否执行, steps[] 自有调度.
        main_passed = self._aggregate_status(before_results) == "passed"

        main_results = self._run_scenario_step_list(
            scenario.steps,
            scenario_id=scenario.id,
            ctx=ctx,
            env=env,
            transport=transport,
            dataset_name=dataset_name,
            dataset_index=dataset_index,
            preceded_by_failure=not main_passed,
        )
        step_results.extend(main_results)
        if main_passed:
            main_passed = self._aggregate_status(main_results) == "passed"

        if main_passed:
            after_results = self._run_hook_step_list(
                scenario.after_steps,
                scenario_id=scenario.id,
                ctx=ctx,
                dataset_name=dataset_name,
                dataset_index=dataset_index,
            )
            step_results.extend(after_results)
            main_passed = self._aggregate_status(after_results) == "passed"

        if main_passed and (scenario.assertions_ref or scenario.assertions):
            assertion_result = self._execute_scenario_assertions(
                scenario,
                ctx,
                dataset_name=dataset_name,
                dataset_index=dataset_index,
            )
            step_results.append(assertion_result)

        return step_results

    def _execute_scenario_assertions(
        self,
        scenario,
        ctx: RuntimeContext,
        *,
        dataset_name: Optional[str],
        dataset_index: Optional[int],
    ) -> StepResult:
        started_perf = time.perf_counter()
        assertions_ref, assertions = self.composer.compose_scenario_assertions(
            assertions_ref=scenario.assertions_ref,
            assertions=scenario.assertions,
        )
        try:
            assertion_results = self.assert_engine.assert_all(
                assertions=assertions,
                response=None,
                ctx=ctx,
                api_id="scenario.assertions",
                step_id="scenario.assertions",
            )
            return StepResult(
                case_id="scenario.assertions",
                api_id="scenario.assertions",
                status="passed",
                step_id="scenario.assertions",
                scenario_id=scenario.id,
                dataset_name=dataset_name,
                dataset_index=dataset_index,
                assertions=assertion_results,
                context_snapshot=ctx.snapshot(),
                duration_ms=self._duration_ms(started_perf),
                extract_out={"assertions_ref": assertions_ref},
            )
        except Exception as e:
            return StepResult(
                case_id="scenario.assertions",
                api_id="scenario.assertions",
                status=self._error_status(e),
                step_id="scenario.assertions",
                scenario_id=scenario.id,
                dataset_name=dataset_name,
                dataset_index=dataset_index,
                context_snapshot=ctx.snapshot(),
                error=e,
                duration_ms=self._duration_ms(started_perf),
                extract_out={"assertions_ref": assertions_ref},
            )

    def _run_scenario_step_list(
        self,
        steps: List,
        *,
        scenario_id: str,
        ctx: RuntimeContext,
        env,
        transport: TransportBase,
        dataset_name: Optional[str],
        dataset_index: Optional[int],
        preceded_by_failure: bool = False,
    ) -> List[StepResult]:
        """
          v0.2 多 step 调度新增三条规则（PRD §6 决策 1）:
            - 普通 step (always_run=False & continue_on_error=False): 失败立即停止后续非 always_run step
              （等价 v0.1 行为）.
            - continue_on_error=True 的 step: 失败时记录 failed/error 状态, 但继续往后走.
            - always_run=True 的 step: 即使前序 step 失败 / before_steps 失败, 仍然执行;
              其自身失败也不会回头去重启普通 step 流.

          preceded_by_failure 参数: 当 scenario.before_steps 已经失败时, 普通 step 全部跳过,
          只剩 always_run step 仍然执行（用作"无论成功失败都跑的清理"）.
        """
        step_results: List[StepResult] = []
        # halted_by_failure 表示"普通 step 流被失败截停", 之后的普通 step 全部跳过, 仅 always_run 仍执行.
        halted_by_failure = preceded_by_failure
        for step in steps:
            if not step.always_run and halted_by_failure:
                # 普通 step 在前序失败后跳过, 不进入结果集（保持 v0.1 stdout 字面）.
                continue

            if step.delay:
                time.sleep(float(step.delay))

            current_results = self._execute_scenario_step(
                step,
                scenario_id=scenario_id,
                ctx=ctx,
                env=env,
                transport=transport,
            )
            for step_result in current_results:
                step_result.dataset_name = dataset_name
                step_result.dataset_index = dataset_index
            step_results.extend(current_results)

            current_status = self._aggregate_status(current_results)
            if current_status != "passed":
                # 当前 step 失败时:
                #   - continue_on_error=True: 不截停, 普通 step 与 always_run 都继续走.
                #   - 否则: 截停普通 step 流, 但 always_run step 在后续循环中仍然会被执行.
                if not step.continue_on_error:
                    halted_by_failure = True

        return step_results

    def _execute_scenario_step(
        self,
        step,
        *,
        scenario_id: str,
        ctx: RuntimeContext,
        env,
        transport: TransportBase,
    ) -> List[StepResult]:
        """
          根据 step 类型分发: use → 走 case 主链路 (compose + execute_one + hooks);
          action → 复用 hooks 的 _execute_action_hook 内核, 让"清理 case"与"清理 SQL"等价.

          step.always_run / continue_on_error 在调度层 (_run_scenario_step_list) 处理,
          这里只负责执行单个 step 并产出 StepResult 列表.
        """
        if step.use is not None:
            case = self.repo.get_case(step.use)
            api = self.repo.get_api(case.use)
            executable_case = self.composer.compose_case(api, case)
            executable_step = self.composer.compose_step(executable_case, step, scenario_id=scenario_id)
            return self._execute_executable_with_hooks(executable_step, ctx, env, transport)

        # inline action step: 包成 HookStep 走同一份 _execute_action_hook 内核,
        # 这样"sql 清理"在 hook 与 inline step 中行为完全一致, 不再需要两份实现.
        hook = HookStep(id=step.id, action=step.action or {}, raw=step.action or {})
        result = self._execute_action_hook(
            hook,
            ctx,
            executable=None,
            scenario_id=scenario_id,
        )
        return [result]

    def _run_hook_step_list(
        self,
        steps: List[HookStep],
        *,
        scenario_id: str,
        ctx: RuntimeContext,
        dataset_name: Optional[str],
        dataset_index: Optional[int],
    ) -> List[StepResult]:
        step_results: List[StepResult] = []
        for step in steps:
            step_result = self._execute_action_hook(
                step,
                ctx,
                scenario_id=scenario_id,
            )
            step_result.dataset_name = dataset_name
            step_result.dataset_index = dataset_index
            step_results.append(step_result)

            if step_result.status != "passed":
                break

        return step_results

    def _run_plan_core(
        self,
        plan_id: str,
        *,
        env_name: str,
        run_id: str,
        ctx: Optional[RuntimeContext],
        transport: Optional[TransportBase],
    ) -> RunResult:
        plan = self.repo.get_plan(plan_id)
        started_at = self._now()
        started_perf = time.perf_counter()
        all_steps: List[StepResult] = []

        for scenario_id in plan.scenarios:
            scenario_result = self._run_scenario_core(
                scenario_id,
                env_name=env_name,
                run_id=run_id,
                ctx=ctx,
                transport=transport,
            )
            all_steps.extend(scenario_result.steps)
            if scenario_result.status != "passed":
                break

        if self._aggregate_status(all_steps) == "passed":
            for case_id in plan.cases:
                case_result = self._run_case_core(
                    case_id,
                    env_name=env_name,
                    run_id=run_id,
                    ctx=ctx,
                    transport=transport,
                )
                all_steps.extend(case_result.steps)
                if case_result.status != "passed":
                    break

        ended_at = self._now()
        status = self._aggregate_status(all_steps)
        return RunResult(
            run_id=run_id,
            target_type="plan",
            target_id=plan_id,
            env=env_name,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=self._duration_ms(started_perf),
            steps=all_steps,
            error=next((item.error for item in all_steps if item.error), None),
        )

    def _execute_executable_with_hooks(
        self,
        executable: ExecutableCase | ExecutableStep,
        ctx: RuntimeContext,
        env,
        transport: TransportBase,
    ) -> List[StepResult]:
        step_results: List[StepResult] = []

        before_results = self._execute_action_hooks(
            executable.before_steps,
            ctx,
            executable=executable,
        )
        step_results.extend(before_results)
        if self._aggregate_status(before_results) != "passed":
            return step_results

        main_result = self._execute_executable(executable, ctx, env, transport)
        step_results.append(main_result)
        if main_result.status != "passed":
            return step_results

        after_results = self._execute_action_hooks(
            executable.after_steps,
            ctx,
            executable=executable,
        )
        step_results.extend(after_results)
        return step_results

    def _execute_action_hooks(
        self,
        hooks: List[HookStep],
        ctx: RuntimeContext,
        *,
        executable: ExecutableCase | ExecutableStep,
    ) -> List[StepResult]:
        results: List[StepResult] = []
        for hook in hooks or []:
            result = self._execute_action_hook(
                hook,
                ctx,
                executable=executable,
                scenario_id=getattr(executable, "scenario_id", None),
            )
            results.append(result)
            if result.status != "passed":
                break
        return results

    def _execute_action_hook(
        self,
        hook: HookStep,
        ctx: RuntimeContext,
        *,
        executable: Optional[ExecutableCase | ExecutableStep] = None,
        scenario_id: Optional[str] = None,
    ) -> StepResult:
        """
          hooks 与 inline action 共享的薄壳: 执行细节全部下沉到 Engine.action_runner.

          失败语义分两层（与 action_runner 设计对齐）:
            - run_action 返回 ActionOutcome(status="failed", error=...): 业务期望不符
              （script returncode != expect_returncode）, 直接落到 StepResult.status="failed".
            - run_action 抛异常: 环境/资源/未实现 错误, 走 _classify_error_status 归类为 "error".
        """
        started_perf = time.perf_counter()
        try:
            if hook.delay:
                time.sleep(float(hook.delay))

            outcome: ActionOutcome = run_action(hook.action or {}, ctx)
            return StepResult(
                case_id=getattr(executable, "case_id", "action"),
                api_id=getattr(executable, "api_id", "action"),
                status=outcome.status,
                step_id=hook.id,
                scenario_id=scenario_id,
                extract_out=outcome.extract_out,
                context_snapshot=ctx.snapshot(),
                error=outcome.error,
                duration_ms=self._duration_ms(started_perf),
            )
        except Exception as e:
            return StepResult(
                case_id=getattr(executable, "case_id", "action"),
                api_id=getattr(executable, "api_id", "action"),
                status=self._error_status(e),
                step_id=hook.id,
                scenario_id=scenario_id,
                extract_out={"action": hook.action or {}},
                context_snapshot=ctx.snapshot(),
                error=e,
                duration_ms=self._duration_ms(started_perf),
            )

    def _execute_executable(
        self,
        executable: ExecutableCase | ExecutableStep,
        ctx: RuntimeContext,
        env,
        transport: TransportBase,
    ) -> StepResult:
        """
          执行单条 Executable 的薄壳:把请求/提取/断言全部委托给模块级 execute_one.

          v0.1 调度层（run_case / run_scenario / run_plan）继续走这条路径；v0.2 pytest 内核
          切换后,pytest_autoapi 插件可以直接 import execute_one 复用同一份实现,避免重写.
        """
        return execute_one(
            executable,
            ctx,
            env,
            transport,
            resolver=self.resolver,
            extractor=self.extractor,
            assert_engine=self.assert_engine,
            request_defaults=self.repo.config.request_defaults,
        )

    def _aggregate_status(self, steps: List[StepResult]) -> str:
        if not steps:
            return "passed"
        if any(item.status == "error" for item in steps):
            return "error"
        if any(item.status == "failed" for item in steps):
            return "failed"
        return "passed"

    def _error_status(self, exc: Exception) -> str:
        # 转发模块级实现,保留旧调用入口供 _execute_action_hook / _execute_scenario_assertions 使用.
        return _classify_error_status(exc)

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _duration_ms(self, started_perf: float) -> float:
        # 转发模块级实现,保留旧调用入口供 hook / scenario.assertions 等流程使用.
        return _perf_to_ms(started_perf)
