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
from Engine.assertion_engine import AssertionEngine
from Engine.results import P0RunResult, P0StepResult, ResponseSnapshot
from Exceptions.AutoApiException import ExceptionCode
from Schema.data_models import ExecutableCase, ExecutableStep
from Utils.log_utils import LoggerManager

logger = LoggerManager.get_logger()


class Executor:
    """
      执行器, 只编排流程, 不做其它处理
      负责串起 repository/context/resolver/transport/extractor/assertion，完成 P0 case/scenario/plan 执行流程。
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


        # P0 新模型使用 Composer 做资产合成，不复用旧 deep_merge 链路。
        self.composer = Composer(repo.config)

    def run_case(
        self,
        case_id: str,
        *,
        env_name: Optional[str] = None,
        run_id: Optional[str] = None,
        ctx: Optional[RuntimeContext] = None,
        transport: Optional[TransportBase] = None,
    ) -> P0RunResult:
        """
          执行一个 P0 ApiCase。
        """
        run_id = run_id or self._new_run_id()
        resolved_env_name = env_name or self.repo.config.active_env
        return self._run_with_env_hooks(
            target_type="case",
            target_id=case_id,
            env_name=resolved_env_name,
            run_id=run_id,
            transport=transport,
            init_ctx=ctx,
            execute_target=lambda ctx, env, active_transport: self._run_case_core(
                case_id,
                env_name=resolved_env_name,
                run_id=run_id,
                ctx=ctx,
                transport=active_transport,
            ),
        )

    def run_scenario(
        self,
        scenario_id: str,
        *,
        env_name: Optional[str] = None,
        run_id: Optional[str] = None,
        transport: Optional[TransportBase] = None,
    ) -> P0RunResult:
        """
          按 steps 顺序执行一个 P0 Scenario。
        """
        scenario = self.repo.get_scenario(scenario_id)
        resolved_env_name = env_name or scenario.env or self.repo.config.active_env
        run_id = run_id or self._new_run_id()
        return self._run_with_env_hooks(
            target_type="scenario",
            target_id=scenario_id,
            env_name=resolved_env_name,
            run_id=run_id,
            transport=transport,
            execute_target=lambda ctx, env, active_transport: self._run_scenario_core(
                scenario_id,
                env_name=resolved_env_name,
                run_id=run_id,
                ctx=ctx,
                transport=active_transport,
            ),
        )

    def run_plan(
        self,
        plan_id: str,
        *,
        env_name: Optional[str] = None,
        run_id: Optional[str] = None,
        transport: Optional[TransportBase] = None,
    ) -> P0RunResult:
        """
          执行一个 P0 TestPlan。
        """
        run_id = run_id or self._new_run_id()
        resolved_env_name = env_name or self.repo.config.active_env
        return self._run_with_env_hooks(
            target_type="plan",
            target_id=plan_id,
            env_name=resolved_env_name,
            run_id=run_id,
            transport=transport,
            execute_target=lambda ctx, env, active_transport: self._run_plan_core(
                plan_id,
                env_name=resolved_env_name,
                run_id=run_id,
                ctx=ctx,
                transport=active_transport,
            ),
        )

    def _run_case_core(
        self,
        case_id: str,
        *,
        env_name: str,
        run_id: str,
        ctx: Optional[RuntimeContext],
        transport: Optional[TransportBase],
    ) -> P0RunResult:
        env = self.repo.get_env(env_name)
        ctx = ctx or RuntimeContext(dict(env.variables))
        transport = transport or SessionTransport()
        started_at = self._now()
        started_perf = time.perf_counter()
        case = self.repo.get_case(case_id)
        api = self.repo.get_api(case.api)
        executable = self.composer.compose_case(api, case)
        step_result = self._execute_p0_executable(executable, ctx, env, transport)
        ended_at = self._now()
        status = "passed" if step_result.status == "passed" else step_result.status
        return P0RunResult(
            run_id=run_id,
            target_type="case",
            target_id=case_id,
            env=env_name,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=self._duration_ms(started_perf),
            steps=[step_result],
            error=step_result.error,
        )

    def _run_scenario_core(
        self,
        scenario_id: str,
        *,
        env_name: str,
        run_id: str,
        ctx: Optional[RuntimeContext],
        transport: Optional[TransportBase],
    ) -> P0RunResult:
        scenario = self.repo.get_scenario(scenario_id)
        env = self.repo.get_env(env_name)
        ctx = ctx or RuntimeContext(dict(env.variables))
        transport = transport or SessionTransport()
        started_at = self._now()
        started_perf = time.perf_counter()
        step_results: List[P0StepResult] = []
        datasets = scenario.datasets or [None]

        for dataset_index, dataset in enumerate(datasets, start=1):
            # 每轮 dataset 都使用独立上下文，避免提取变量跨轮污染。
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
        return P0RunResult(
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
    ) -> List[P0StepResult]:
        step_results: List[P0StepResult] = []

        before_results = self._run_scenario_step_list(
            scenario.before_steps,
            scenario_id=scenario.id,
            ctx=ctx,
            env=env,
            transport=transport,
            dataset_name=dataset_name,
            dataset_index=dataset_index,
        )
        step_results.extend(before_results)

        main_passed = self._aggregate_status(before_results) == "passed"

        if main_passed:
            main_results = self._run_scenario_step_list(
                scenario.steps,
                scenario_id=scenario.id,
                ctx=ctx,
                env=env,
                transport=transport,
                dataset_name=dataset_name,
                dataset_index=dataset_index,
            )
            step_results.extend(main_results)
            main_passed = self._aggregate_status(main_results) == "passed"

        if main_passed:
            after_results = self._run_scenario_step_list(
                scenario.after_steps,
                scenario_id=scenario.id,
                ctx=ctx,
                env=env,
                transport=transport,
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
            main_passed = assertion_result.status == "passed"

        finally_results = self._run_scenario_step_list(
            scenario.finally_steps,
            scenario_id=scenario.id,
            ctx=ctx,
            env=env,
            transport=transport,
            dataset_name=dataset_name,
            dataset_index=dataset_index,
        )
        step_results.extend(finally_results)

        return step_results

    def _execute_scenario_assertions(
        self,
        scenario,
        ctx: RuntimeContext,
        *,
        dataset_name: Optional[str],
        dataset_index: Optional[int],
    ) -> P0StepResult:
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
            return P0StepResult(
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
            return P0StepResult(
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
    ) -> List[P0StepResult]:
        step_results: List[P0StepResult] = []
        for step in steps:
            if step.delay:
                time.sleep(float(step.delay))

            case = self.repo.get_case(step.use)
            api = self.repo.get_api(case.api)
            executable_case = self.composer.compose_case(api, case)
            executable_step = self.composer.compose_step(executable_case, step, scenario_id=scenario_id)
            step_result = self._execute_p0_executable(executable_step, ctx, env, transport)
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
    ) -> P0RunResult:
        plan = self.repo.get_plan(plan_id)
        started_at = self._now()
        started_perf = time.perf_counter()
        all_steps: List[P0StepResult] = []

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
        return P0RunResult(
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

    def _run_with_env_hooks(
        self,
        *,
        target_type: str,
        target_id: str,
        env_name: str,
        run_id: str,
        transport: Optional[TransportBase],
        init_ctx: Optional[RuntimeContext] = None,
        execute_target,
    ) -> P0RunResult:
        # 顶层执行只包裹一次环境 hooks，避免 plan/scenario/case 递归时重复执行登录等动作。
        env = self.repo.get_env(env_name)
        ctx = init_ctx or RuntimeContext(dict(env.variables))
        transport = transport or SessionTransport()
        started_at = self._now()
        started_perf = time.perf_counter()
        all_steps: List[P0StepResult] = []

        auth_profile = env.auth_profiles.get(env.auth_profile) if env.auth_profile else None
        setup_succeeded = True

        setup_results = self._run_env_case_list(
            env.setup_cases,
            hook_prefix="env.setup",
            env_name=env_name,
            run_id=run_id,
            ctx=ctx,
            transport=transport,
        )
        all_steps.extend(setup_results)
        if self._aggregate_status(setup_results) != "passed":
            setup_succeeded = False

        if setup_succeeded and auth_profile is not None:
            auth_setup_results = self._run_env_case_list(
                auth_profile.setup_cases,
                hook_prefix="env.auth.setup",
                env_name=env_name,
                run_id=run_id,
                ctx=ctx,
                transport=transport,
            )
            all_steps.extend(auth_setup_results)
            if self._aggregate_status(auth_setup_results) != "passed":
                setup_succeeded = False

        if setup_succeeded:
            target_result = execute_target(ctx, env, transport)
            all_steps.extend(target_result.steps)

        if auth_profile is not None:
            auth_teardown_results = self._run_env_case_list(
                auth_profile.teardown_cases,
                hook_prefix="env.auth.teardown",
                env_name=env_name,
                run_id=run_id,
                ctx=ctx,
                transport=transport,
            )
            all_steps.extend(auth_teardown_results)

        env_teardown_results = self._run_env_case_list(
            env.teardown_cases,
            hook_prefix="env.teardown",
            env_name=env_name,
            run_id=run_id,
            ctx=ctx,
            transport=transport,
        )
        all_steps.extend(env_teardown_results)

        ended_at = self._now()
        status = self._aggregate_status(all_steps)
        return P0RunResult(
            run_id=run_id,
            target_type=target_type,
            target_id=target_id,
            env=env_name,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=self._duration_ms(started_perf),
            steps=all_steps,
            error=next((item.error for item in all_steps if item.error), None),
        )

    def _run_env_case_list(
        self,
        case_ids: List[str],
        *,
        hook_prefix: str,
        env_name: str,
        run_id: str,
        ctx: RuntimeContext,
        transport: TransportBase,
    ) -> List[P0StepResult]:
        step_results: List[P0StepResult] = []
        for case_id in case_ids:
            case_result = self._run_case_core(
                case_id,
                env_name=env_name,
                run_id=run_id,
                ctx=ctx,
                transport=transport,
            )
            for step in case_result.steps:
                # 用合成的 step_id 标记环境 hook 来源，便于 CLI / Allure / history 识别。
                step.step_id = f"{hook_prefix}.{case_id}"
                step_results.append(step)
            if self._aggregate_status(case_result.steps) != "passed":
                break
        return step_results

    def _execute_p0_executable(
        self,
        executable: ExecutableCase | ExecutableStep,
        ctx: RuntimeContext,
        env,
        transport: TransportBase,
    ) -> P0StepResult:
        """
          执行一个已经合成好的 ExecutableCase 或 ExecutableStep。
        """
        started_perf = time.perf_counter()
        prepared = None
        response_snapshot = None
        extract_out: Dict[str, Any] = {}
        assertions = []
        try:
            prepared = self.resolver.resolve_executable(
                executable,
                self.repo.config.request_defaults,
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
            extract_out = self.extractor.apply(
                rules=executable.extract,
                response=response_obj,
                ctx=ctx,
                api_id=executable.api_id,
                step_id=getattr(executable, "step_id", None),
                request=request_snapshot,
            )
            assertions = self.assert_engine.assert_all(
                assertions=executable.assertions,
                response=response_obj,
                ctx=ctx,
                api_id=executable.api_id,
                step_id=getattr(executable, "step_id", None),
                request_snapshot=request_snapshot,
            )
            return P0StepResult(
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
                duration_ms=self._duration_ms(started_perf),
            )
        except Exception as e:
            return P0StepResult(
                case_id=executable.case_id,
                api_id=executable.api_id,
                status=self._error_status(e),
                step_id=getattr(executable, "step_id", None),
                scenario_id=getattr(executable, "scenario_id", None),
                request=prepared,
                response=response_snapshot,
                extract_out=extract_out,
                assertions=assertions,
                context_snapshot=ctx.snapshot(),
                error=e,
                duration_ms=self._duration_ms(started_perf),
            )

    def _aggregate_status(self, steps: List[P0StepResult]) -> str:
        if not steps:
            return "passed"
        if any(item.status == "error" for item in steps):
            return "error"
        if any(item.status == "failed" for item in steps):
            return "failed"
        return "passed"

    def _error_status(self, exc: Exception) -> str:
        error_context = getattr(exc, "error_context", None)
        error_code = getattr(error_context, "error_code", None)
        if error_code == ExceptionCode.ASSERT_ERROR:
            return "failed"
        return "error"

    def _new_run_id(self) -> str:
        return uuid.uuid4().hex

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _duration_ms(self, started_perf: float) -> float:
        return round((time.perf_counter() - started_perf) * 1000, 3)
