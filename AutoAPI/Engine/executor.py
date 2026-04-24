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
        self.composer = Composer()

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
        # 统一生成 run_id，便于 history 将 run 与 result 关联。
        run_id = run_id or self._new_run_id()
        # 解析本次执行环境，CLI --env 未传时使用 config.active_env。
        env_name = env_name or self.repo.config.active_env
        env = self.repo.get_env(env_name)
        # 单 case 默认使用环境变量初始化上下文。
        ctx = ctx or RuntimeContext(dict(env.variables))
        # case 单独执行也使用 session transport，保持后续扩展一致。
        transport = transport or SessionTransport()
        started_at = self._now()
        started_perf = time.perf_counter()

        # 根据 case 找到对应 api template，再合成可执行对象。
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
        run_id = run_id or self._new_run_id()
        scenario = self.repo.get_scenario(scenario_id)
        # 环境优先级：CLI --env > scenario.env > config.active_env。
        resolved_env_name = env_name or scenario.env or self.repo.config.active_env
        env = self.repo.get_env(resolved_env_name)
        ctx = RuntimeContext(dict(env.variables))
        transport = transport or SessionTransport()
        started_at = self._now()
        started_perf = time.perf_counter()
        step_results: List[P0StepResult] = []

        for step in scenario.steps:
            if step.delay:
                time.sleep(float(step.delay))

            case = self.repo.get_case(step.use)
            api = self.repo.get_api(case.api)
            executable_case = self.composer.compose_case(api, case)
            executable_step = self.composer.compose_step(executable_case, step, scenario_id=scenario.id)
            step_result = self._execute_p0_executable(executable_step, ctx, env, transport)
            step_results.append(step_result)

            # P0 默认失败即停止，continue_on_error 放到 P1。
            if step_result.status != "passed":
                break

        ended_at = self._now()
        status = self._aggregate_status(step_results)
        return P0RunResult(
            run_id=run_id,
            target_type="scenario",
            target_id=scenario_id,
            env=resolved_env_name,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=self._duration_ms(started_perf),
            steps=step_results,
            error=next((item.error for item in step_results if item.error), None),
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
        plan = self.repo.get_plan(plan_id)
        resolved_env_name = env_name or self.repo.config.active_env
        started_at = self._now()
        started_perf = time.perf_counter()
        all_steps: List[P0StepResult] = []

        for scenario_id in plan.scenarios:
            scenario_result = self.run_scenario(
                scenario_id,
                env_name=env_name,
                run_id=run_id,
                transport=transport,
            )
            all_steps.extend(scenario_result.steps)
            if scenario_result.status != "passed":
                break

        # 只有场景全部通过时，才继续执行 plan 中独立 case。
        if self._aggregate_status(all_steps) == "passed":
            for case_id in plan.cases:
                case_result = self.run_case(
                    case_id,
                    env_name=resolved_env_name,
                    run_id=run_id,
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
            env=resolved_env_name,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=self._duration_ms(started_perf),
            steps=all_steps,
            error=next((item.error for item in all_steps if item.error), None),
        )

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
