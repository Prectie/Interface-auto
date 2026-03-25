# -*- coding: utf-8 -*-

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List


from Core.context import RuntimeContext
from Core.repository import YamlRepository
from Engine.extractor import Extractor

from Engine.request_resolver import RequestResolver
from Engine.transport import SessionTransport, TransportBase
from Engine.assertion_engine import AssertionEngine
from Engine.results import CaseResult, FlowResult, StepResult, ApiInvokeResult, ResponseSnapshot
from Exceptions.AutoApiException import build_api_exception_context, ExceptionCode, \
    PipelineException, AutoApiException
from Schema.data_validation import ApiItem
from Utils.allure_reporter import AllureReporter
from Utils.log_utils import LoggerManager

logger = LoggerManager.get_logger()


@dataclass
class ExecutionState:
    """
      单次生命周期运行态状态对象
    """
    # 当前生命周期内已执行的 auth_profile 集合
    executed_profiles: set[str] = field(default_factory=set)
    # 当前生命周期内已执行的 depends_on 去重集合
    executed_depends: set[str] = field(default_factory=set)
    # 当前 depends_on 递归访问链, 防止存在循环依赖 "环", 导致死循环(作为运行期第二套兜底方案)
    visiting_api_chain: List[str] = field(default_factory=list)
    # 后置 cleanup 执行失败信息列表
    cleanup_errors: List[Dict[str, Any]] = field(default_factory=list)


class Executor:
    """
      执行器, 只编排流程, 不做其它处理
      负责串起 repository/context/resolver/transport/extractor/assertion/auth，完成 single/multiple 执行流程
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

    def _run_auth_profile(
        self,
        profile_name: str,
        ctx: RuntimeContext,
        state: ExecutionState,
        transport: TransportBase,
        env: Dict[str, Any],
        request_defaults: Dict[str, Any],
        *,
        api_id: Optional[str] = None,
        flow_file: Optional[str] = None,
        flow_step_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
          执行前置接口

          作用:
            - 支持 override.request 覆盖接口库模板请求数据
            - extract 与 assertions 均是 override 优先级最高
            - 执行 extract 写入 ctx

        :param profile_name: 前置接口名称
        :param ctx: 上下文（写入 token 等）
        :param transport: 发包器（single 用 requests，flow 用 session）
        :param env: env 当前环境数据
        :param request_defaults: static 静态配置
        :param api_id: 接口库的接口id
        :param flow_file: 业务流文件
        :param flow_step_id: 业务流的步骤名称
        :return: 整理后的提取结果 dict
        """
        # 若当前公共前置在当前生命周期已经执行过, 直接跳过
        if profile_name in state.executed_profiles:
            with AllureReporter.step(f"跳过前置 auth_profile | profile={profile_name} | 原因=已执行"):
                AllureReporter.attach_text("跳过执行原因", f"前置接口 {profile_name} 在当前生命周期已执行")
            return {}

        try:
            # 取 auth_profiles, 允许为空
            profiles = self.repo.config.auth_profiles or {}

            # 若 profile 不存在, 报错
            if profile_name not in profiles:
                # 构建明确异常上下文
                error_context = build_api_exception_context(
                    error_code=ExceptionCode.PIPELINE_ERROR,
                    message=f"前置接口不存在",
                    reason=f"接口: [{api_id}] 需要调用的前置接口: [{profile_name}] 不存在",
                    yaml_file="config.yaml",
                    flow_file=flow_file,
                    profile_name=profile_name,
                    hint="请检查 config.yaml.auth_profiles 下是否存在需要调用的前置接口",
                    extra={"可用 profiles": list(profiles.keys())},
                )
                raise PipelineException(error_context)

            # 取 profile 体, 取不到直接报错
            profile_steps = profiles[profile_name]

            # 初始化当前公共前置总提取结果
            extract_all: Dict[str, Any] = {}

            # 创建执行前置接口总步骤
            with AllureReporter.step(f"执行前置 auth_profile | profile={profile_name}"):
                # 前置接口的上下文快照
                AllureReporter.attach_context("前置接口执行前的上下文", ctx)
                AllureReporter.attach_json("前置接口原始数据", profile_steps)

                # 按 yaml 列表顺序逐个执行步骤
                for index, step in enumerate(profile_steps, start=1):
                    # 读取 is_run, 若为 False 则不执行(不填默认为 True)
                    is_run = step.get("is_run", True)

                    # 读取 ref
                    ref = step.get("ref", "")

                    # 读取 override, 为 None 设 空dict
                    override = step.get("override", {}) or {}

                    # 优先使用 id 作为步骤名, 次之则按顺序命名
                    step_id = step.get("id") or f"profile_step_{index}"

                    with AllureReporter.step(f"前置步骤 | profile={profile_name} | step={step_id} | ref={ref}"):
                        AllureReporter.attach_json("当前 auth_profile 的 step 数据", step)
                        if not is_run:
                            # 为 False 时跳过执行
                            AllureReporter.attach_text("跳过执行原因", "当前前置步骤 is_run=False, 已跳过执行")
                            continue

                        # 从接口库取接口模板
                        api = self.repo.get_api(ref)
                        # 执行一次完整调用
                        invoke_result = self._execute_api(
                            api=api,
                            ctx=ctx,
                            transport=transport,
                            env=env,
                            request_defaults=request_defaults,
                            override=override,
                            step_id=step_id,  # 此处传的是 前置接口 的 step_id
                        )

                        if invoke_result.extract:
                            extract_all.update(invoke_result.extract)
                            AllureReporter.attach_json("当前 auth_profile 响应提取结果", extract_all)

                # 记录已经执行过的 前置接口
                state.executed_profiles.add(profile_name)
                AllureReporter.attach_context("执行前置接口后的上下文", ctx)
                AllureReporter.attach_json("最终 auth_profile 响应提取总结果", extract_all)
                # 返回提取结果
                return extract_all

        # AuthProfileError情况直接抛出
        except AutoApiException as e:
            # 挂异常文本
            AllureReporter.attach_exception(e, traceback_text=traceback.format_exc())
            # 已结构化的异常直接抛出
            raise
        # 其他异常
        except Exception as e:
            # 构建明确异常上下文
            error_context = build_api_exception_context(
                error_code=ExceptionCode.PIPELINE_ERROR,
                message="前置接口执行失败",
                reason=str(e),
                yaml_file="config.yaml",
                flow_file=flow_file,
                api_id=api_id,
                step_id=flow_step_id,   # 发生在哪个业务流步骤
                profile_name=profile_name,  # 引用的前置接口名称
                hint="请检查前置接口的 ref、request、extract 等数据是否正确",
            )
            # 构建统一的流程异常对象
            wrapped = PipelineException(error_context)
            AllureReporter.attach_exception(wrapped, traceback_text=traceback.format_exc())
            raise wrapped from e

    def _run_depends_on(
        self,
        api: ApiItem,
        ctx: RuntimeContext,
        state: ExecutionState,
        transport: TransportBase,
        env: Dict[str, Any],
        request_defaults: Dict[str, Any],
        *,
        yaml_location
    ):
        """
          递归执行接口的 depends_on 字段

          当前规则:
            - 对于依赖节点 ref_api, 执行顺序为:
              1.先递归执行 ref_api 自己的 depends_on 子树
              2.再执行 ref_api 自己的 auth_profile
              3.最后执行 ref_api 自己的 request
            - 该顺序要求子树依赖顺序自洽

        :param api: 当前接口对象
        :param ctx: 运行时期上下文对象
        :param state: 当前生命周期对象
        :param transport: 统一传输层对象
        :param env: 当前环境配置
        :param request_defaults: 全局默认请求参数
        :param yaml_location: 错误处的精确定位路径
        :return: 当前接口执行后总的响应提取结果
        """
        # 当前接口未定义 depends_on, 返回空结果
        if not api.depends_on:
            return {}

        # 若当前接口已处于递归访问链中, 说明发生循环引用
        if api.api_id in state.visiting_api_chain:
            cycle_chain = state.visiting_api_chain + [api.api_id]
            error_context = build_api_exception_context(
                error_code=ExceptionCode.PIPELINE_ERROR,
                message="检测到 depends_on 存在循环依赖",
                reason=" -> ".join(cycle_chain),  # 把循环依赖链路串起来, 方便定位
                yaml_location=yaml_location,
                hint="请检查 single.yaml 中各接口的 depends_on 配置, 避免互相引用"
            )
            wrapped = PipelineException(error_context)
            AllureReporter.attach_exception(wrapped)
            raise wrapped

        # 不存在于递归访问链中, 则存入当前生命周期的递归链中
        state.visiting_api_chain.append(api.api_id)

        try:
            # 初始化当前接口总响应提取结果
            extract_all: Dict[str, Any] = {}

            # 创建 depends_on 总步骤
            with AllureReporter.step(f"执行 depends_on | api={api.api_id}"):
                AllureReporter.attach_json("当前 depends_on 数据", api.depends_on)
                AllureReporter.attach_context("depends_on 执行前的上下文", ctx)
                # 按 YAML 列表顺序逐个执行 depends_on 步骤
                for index, step in enumerate(api.depends_on, start=1):
                    # 读取 is_run, 不写默认为 True
                    is_run = step.get("is_run", True)
                    # 为 False 时跳过执行
                    if not is_run:
                        with AllureReporter.step(f"跳过 depends_on | api={api.api_id} | index={index}"):
                            AllureReporter.attach_json("当前 depends_on_step 数据", step)
                            AllureReporter.attach_text("跳过执行原因", "当前 depends_on 步骤的 is_run=False, 已跳过执行")
                        continue

                    # 获取去重键
                    dedupe_key = self._build_depends_dedupe_key(step)
                    if dedupe_key in state.executed_depends:
                        # 若在当前生命周期已经执行过该 depends, 跳过执行
                        with AllureReporter.step(f"跳过 depends_on | dedupe={dedupe_key} | 原因=已执行"):
                            AllureReporter.attach_json("当前 depends_on_step 数据", step)
                            AllureReporter.attach_text("跳过执行原因", f"depends_on 去重键={dedupe_key} 已在当前生命周期执行过, 本次跳过")
                        continue

                    # 读取被引用的接口 id
                    ref_api_id = step.get("ref", "")
                    # 优先使用 id 作为当前步骤名, 次之使用当前步骤顺序
                    step_id = step.get("id") or f"depends_on_{index}"
                    # 读取局部覆盖 override
                    override = step.get("override", {})
                    # 通过被引用的接口id, 获取它的接口模板数据
                    ref_api = self.repo.get_api(ref_api_id)

                    # 创建单个步骤报告
                    with AllureReporter.step(f"depends_on 步骤 | ref={ref_api_id} | step={step_id}"):
                        AllureReporter.attach_json("depends_on 当前 step 数据", step)
                        # 先递归执行当前依赖接口自己的 depends_on 子树
                        self._run_depends_on(
                            api=ref_api,
                            ctx=ctx,
                            state=state,
                            transport=transport,
                            env=env,
                            request_defaults=request_defaults,
                            yaml_location=f"single.yaml.apis.{ref_api.api_id}.depends_on"
                        )

                        # 再执行当前依赖接口自己的公共前置
                        if ref_api.auth_profile:
                            self._run_auth_profile(
                                profile_name=ref_api.auth_profile,
                                ctx=ctx,
                                state=state,
                                transport=transport,
                                env=env,
                                request_defaults=request_defaults,
                                api_id=ref_api_id
                            )

                        # 执行当前 depends 引用的 api
                        invoke_result = self._execute_api(
                            api=ref_api,
                            ctx=ctx,
                            transport=transport,
                            env=env,
                            request_defaults=request_defaults,
                            override=override,
                            step_id=step_id
                        )

                        # 若存在响应提取结果, 则更新到总结果中
                        if invoke_result.extract:
                            AllureReporter.attach_json("当前 depends_on 响应提取结果", extract_all)
                            extract_all.update(invoke_result.extract)

                        # 当前 depends 步骤执行完成后, 写入去重集合
                        state.executed_depends.add(dedupe_key)

                AllureReporter.attach_context("depends_on 执行后的上下文", ctx)
                AllureReporter.attach_json("最终 depends_on 响应提取总结果", extract_all)
                return extract_all

        except AutoApiException as e:
            AllureReporter.attach_exception(e, traceback_text=traceback.format_exc())
            raise
        except Exception as e:
            error_context = build_api_exception_context(
                error_code=ExceptionCode.PIPELINE_ERROR,
                message="depends_on 执行失败",
                reason=e,
                yaml_location=yaml_location,
                hint="请检查 depends_on 的 ref、override、依赖关系是否正确"
            )
            # 构建统一的流程异常对象
            wrapped = PipelineException(error_context)
            AllureReporter.attach_exception(wrapped, traceback_text=traceback.format_exc())
            raise wrapped from e

        finally:
            # 仅当当前接口位于访问链尾部时弹出
            if state.visiting_api_chain and state.visiting_api_chain[-1] == api.api_id:
                state.visiting_api_chain.pop()

    def _run_cleanup(
        self,
        cleanup: Optional[Dict[str, Any]],
        ctx: RuntimeContext,
        state: ExecutionState,
        transport: TransportBase,
        env: Dict[str, Any],
        request_defaults: Dict[str, Any],
        *,
        main_success: bool,
        yaml_location: str
    ):
        """
          执行后置操作, 清理脏数据
        :param cleanup: cleanup配置数据结构
        :param ctx: 运行器业务变量上下文对象
        :param state: 当前生命周期状态对象
        :param transport: 统一传输层对象
        :param env: 当前环境配置
        :param request_defaults: 全局默认请求参数
        :param main_success: 主流程是否成功
        :param yaml_location: YAML具体定位路径
        """
        # 若未配置 cleanup, 则直接返回
        if not cleanup:
            return

        # 读取 cleanup 触发条件, 不写默认 always
        when = cleanup.get("when", "always") or "always"
        # 若策略是仅成功时清理, 但主流程执行失败了, 跳过执行
        if when == "on_success" and not main_success:
            with AllureReporter.step(f"跳过 cleanup | when={when} | main_success={main_success}"):
                AllureReporter.attach_json("cleanup 数据", cleanup)
                AllureReporter.attach_text("跳过执行原因", "cleanup 配置为 on_success, 但主流程未成功, 已跳过")
            return
        # 若策略是仅失败时清理, 但主流程执行成功了, 跳过执行
        if when == "on_fail" and main_success:
            with AllureReporter.step(f"跳过 cleanup | when={when} | main_success={main_success}"):
                AllureReporter.attach_json("cleanup 数据", cleanup)
                AllureReporter.attach_text("skip_reason", "cleanup 配置为 on_fail, 但主流程成功, 已跳过")
            return

        # 读取 continue_on_error 决定主流程失败后是否继续执行
        continue_on_error = cleanup.get("continue_on_error", True)
        # 读取 cleanup 执行步骤列表
        steps: List[Dict[str, Any]] = cleanup.get("steps", []) or []

        # 创建 cleanup 总步骤
        with AllureReporter.step(f"执行 cleanup | when={when} | continue_on_error={continue_on_error}"):
            AllureReporter.attach_json("cleanup 数据", cleanup)
            AllureReporter.attach_context("cleanup 执行前的上下文", ctx)
            # cleanup 步骤默认逆序执行
            for index, step in enumerate(reversed(steps), start=1):
                # 读取 cleanup 单步骤开关, 不填默认 True
                is_run = step.get("is_run", True)
                # 读取被引用接口的 id
                ref_api_id = step.get("ref")
                # 优先使用 id 作为步骤名, 次之按顺序命名
                step_id = step.get("id") or f"cleanup_step_{index}"
                # 读取局部覆盖 override, 为空或假值时转为空 dict
                override = step.get("override", {}) or {}

                # 创建 cleanup 单步步骤
                with AllureReporter.step(f"cleanup 步骤 | step={step_id} | ref={ref_api_id}"):
                    AllureReporter.attach_json("cleanup 当前 step 数据", step)

                    if not is_run:
                        AllureReporter.attach_text("跳过执行原因", "当前 cleanup 步骤 is_run=False, 已跳过执行")
                        continue

                    try:
                        # 读取被引用接口的数据模板
                        ref_api = self.repo.get_api(ref_api_id)

                        # 先递归执行当前依赖接口自己的 depends_on 子树
                        self._run_depends_on(
                            api=ref_api,
                            ctx=ctx,
                            state=state,
                            transport=transport,
                            env=env,
                            request_defaults=request_defaults,
                            yaml_location=f"single.yaml.apis.{ref_api.api_id}.depends_on"
                        )

                        # 再执行当前依赖接口自己的公共前置
                        if ref_api.auth_profile:
                            self._run_auth_profile(
                                profile_name=ref_api.auth_profile,
                                ctx=ctx,
                                state=state,
                                transport=transport,
                                env=env,
                                request_defaults=request_defaults,
                                api_id=ref_api_id
                            )

                        # 执行当前 depends 引用的 api
                        self._execute_api(
                            api=ref_api,
                            ctx=ctx,
                            transport=transport,
                            env=env,
                            request_defaults=request_defaults,
                            override=override,
                            step_id=step_id
                        )

                    except Exception as e:
                        state.cleanup_errors.append(
                            {
                                "yaml_location": yaml_location,
                                "step_id": step_id,
                                "ref_api_id": ref_api_id,
                                "error": e
                            }
                        )
                        AllureReporter.attach_exception(e, traceback_text=traceback.format_exc())
                        AllureReporter.attach_json("cleanup_errors_accumulator", state.cleanup_errors)

                        # 若 continue_on_error 设置为 cleanup 执行失败后不继续执行, 则直接抛出异常
                        if not continue_on_error:
                            raise

        # 挂 cleanup 执行后上下文快照
        AllureReporter.attach_context("cleanup 执行后的上下文", ctx)
        # 若存在 cleanup 错误, 则挂最终错误列表
        if state.cleanup_errors:
            AllureReporter.attach_json("cleanup 最终错误列表", state.cleanup_errors)

    def run_single(self, api_id: str, data_index: int) -> CaseResult:
        """
          执行 single.yaml 中的单接口用例

        :param api_id: 接口 id
        :param data_index: 当 request 的数据(body/params/files) 为 list 时, 根据优先级取第几条数据
        :return: CaseResult
        """
        # 确保 repo 已加载
        self._ensure_loaded()

        # 获取接口定义
        api = self.repo.get_api(api_id)
        # 根据 config.yaml 里的 run_control 决定是否 跳过/仅执行 某些 api
        should_run = self.repo.should_run_single_api(api_id=api_id)

        # 初始化结果, 方便日志/报告的打印
        result = CaseResult(api_id=api.api_id, is_run=should_run)

        # 若不执行, 直接返回
        if not should_run:
            with AllureReporter.step(f"跳过 single 用例 | api={api_id}"):
                AllureReporter.attach_text("跳过执行原因", "当前接口被 run_control 跳过, 未执行请求")
                # 即便跳过也挂最终结果摘要
                AllureReporter.attach_case_result(result)
            return result

        # 构建 suite_ctx(静态 ctx, 从 config.yaml.static 获取)
        suite_ctx = self._build_suite_ctx()
        # 通过 fork, 避免污染原数据
        case_ctx = suite_ctx.fork()
        # 创建当前 single 生命周期状态对象
        state = ExecutionState()
        # 获取 env 数据
        env = self.repo.config.env
        # 获取 request_defaults 数据
        request_defaults = self.repo.config.request_defaults

        # 创建单次请求 transport
        transport = SessionTransport()

        # 记录主流程是否执行成功, 供 finally cleanup 判断 when 条件使用
        main_success = False

        try:
            # 创建 single 总步骤
            with AllureReporter.step(f"执行 single 用例 | api={api_id} | data_index={data_index}"):
                AllureReporter.attach_context("静态上下文数据", suite_ctx)
                AllureReporter.attach_context("接口执行前的上下文数据", case_ctx)
                # 若该接口需要执行前置接口
                if api.auth_profile:
                    # 先执行前置接口
                    self._run_auth_profile(
                        profile_name=api.auth_profile,
                        ctx=case_ctx,
                        state=state,
                        transport=transport,
                        env=env,
                        request_defaults=request_defaults,
                        api_id=api_id,
                    )

                # 再执行当前接口自身的 depends_on
                self._run_depends_on(
                    api=api,
                    ctx=case_ctx,
                    state=state,
                    transport=transport,
                    env=env,
                    request_defaults=request_defaults,
                    yaml_location=f"single.yaml.apis.{api_id}.depends_on"
                )

                # 执行一次完整接口调用
                invoke_result = self._execute_api(
                    api=api,
                    ctx=case_ctx,
                    transport=transport,
                    env=env,
                    request_defaults=request_defaults,
                    data_index=data_index,   # 接口库支持依照 data条数 生成 测试函数条数
                    step_id=api.api_id,
                    yaml_file="single.yaml"
                )

                # 回填结果对象, 方便日志/报告打印
                result.request = invoke_result.request
                result.response = invoke_result.response
                result.extract_out = invoke_result.extract
                result.assertions = invoke_result.assertions

                # 主流程执行成功
                main_success = True
                # 返回结果, 用于日志/报告的打印
                return result
        except Exception as e:
            # 写入 result 错误文本
            result.error = e
            # 挂异常附件
            AllureReporter.attach_exception(e, traceback_text=traceback.format_exc())
            raise
        finally:
            try:
                self._run_cleanup(
                    cleanup=api.cleanup,
                    ctx=case_ctx,
                    state=state,
                    transport=transport,
                    env=env,
                    request_defaults=request_defaults,
                    main_success=main_success,
                    yaml_location=f"single.yaml.apis.{api_id}.cleanup"  
                )
            finally:
                # cleanup 执行结束后, 再统一回填当前生命周期最终状态
                result.cleanup_errors = list(state.cleanup_errors)
                result.executed_auth_profiles = sorted(state.executed_profiles)
                result.executed_depends_keys = sorted(state.executed_depends)

                # 挂生命周期执行状态摘要
                AllureReporter.attach_execution_state(state)
                AllureReporter.attach_context("接口执行完毕后的上下文数据", case_ctx)
                # 挂 case 最终汇总结果
                AllureReporter.attach_case_result(result)
                transport.close()

    def run_flow(self, flow_id: Optional[str] = None) -> FlowResult:
        """
          执行业务流(flows)
        :param flow_id: 业务流唯一标识
        :return: flow 业务流总执行结果, 包含多个 steps 的执行结果
        """
        # 确保 repo 已加载
        self._ensure_loaded()

        # 获取 flow 数据
        flow = self.repo.get_flow(flow_id)

        # 初始化结果, 方便日志/报告的打印
        result = FlowResult(flow_id=flow.flow_id, is_run=flow.is_run)

        # 若 flow 不执行, 则跳过
        if not flow.is_run:
            with AllureReporter.step(f"跳过 flow 用例 | flow={flow.flow_id}"):
                AllureReporter.attach_text("跳过执行原因", "当前 flow 的 is_run=False, 已跳过执行")
                # 即便跳过也挂最终汇总结果
                AllureReporter.attach_flow_result(result)
            return result

        # 构建 suite_ctx(静态 ctx, 从 config.yaml.static 获取)
        suite_ctx = self._build_suite_ctx()
        # 通过 fork, 避免污染原数据
        # 注:业务流共享
        flow_ctx = suite_ctx.fork()

        # 创建当前 flow 生命周期状态对象
        state = ExecutionState()

        # 获取 env 数据
        env = self.repo.config.env
        # 获取 request_defaults 数据(默认参数, 比如默认请求头 headers)
        request_defaults = self.repo.config.request_defaults

        # 创建 session transport(flow 使用会话进行发送请求操作)
        transport = SessionTransport()

        # 记录当前主流程是否执行成功
        main_success = False

        try:
            # 创建 flow 总步骤
            with AllureReporter.step(f"执行业务流 | flow={flow.flow_id}"):
                AllureReporter.attach_context("静态上下文数据", suite_ctx)
                AllureReporter.attach_context("业务流执行前的上下文数据", flow_ctx)
            # 若 flow 的前置接口需要执行
            if flow.auth_profile:
                self._run_auth_profile(
                    profile_name=flow.auth_profile,
                    ctx=flow_ctx,
                    state=state,
                    transport=transport,
                    env=env,
                    request_defaults=request_defaults,
                    flow_file=flow.source
                )

            # 遍历 steps
            for index, step in enumerate(flow.steps, start=1):
                # 获取 step 名称, 若没有按照顺序下标进行命名
                step_id = step.get("id") or f"step_{index}"

                # 获取 step 开关 (不填默认 True)
                step_is_run = step.get("is_run", True)

                # 获取 ref, 从接口库里引用的接口模板
                ref_api_id = step.get("ref", "")

                # 获取 delay_run, step 执行前的延迟秒数,
                # 不填该字段默认 0, 为假值(显式 None)时也默认为 0
                delay_run = float(step.get("delay_run", 0) or 0)

                # 初始化 StepResult, 方便日志/报告的打印
                step_result = StepResult(
                    step_id=step_id,
                    ref_api_id=ref_api_id,
                    is_run=step_is_run,
                    delay_run=delay_run
                )

                # 把单步 step 加入 flows 总结果, 方便日志/报告的打印
                result.steps.append(step_result)

                # 创建当前 flow 单步步骤
                with AllureReporter.step(f"flow 步骤 | step={step_id} | ref={ref_api_id} | delay_run={delay_run}"):
                    AllureReporter.attach_json("当前 flow 单步 step 数据", step)
                    # 若 step 不执行, 则跳过
                    if not step_is_run:
                        AllureReporter.attach_text("跳过执行原因", "当前 flow 步骤 is_run=False, 已跳过执行")
                        continue

                    try:
                        # 获取接口模板
                        api = self.repo.get_api(ref_api_id)
                        # 若该 api 需要执行单独的前置接口, 且该前置接口未执行过
                        if api.auth_profile:
                            self._run_auth_profile(
                                profile_name=api.auth_profile,
                                ctx=flow_ctx,
                                state=state,
                                transport=transport,
                                env=env,
                                request_defaults=request_defaults,
                                api_id=ref_api_id,
                                flow_file=flow.source,
                                flow_step_id=step_id
                            )

                        # 执行当前接口的 depends_on
                        self._run_depends_on(
                            api=api,
                            ctx=flow_ctx,
                            state=state,
                            transport=transport,
                            env=env,
                            request_defaults=request_defaults,
                            yaml_location=f"single.yaml.apis.{api.api_id}.depends_on"
                        )

                        # 若存在延迟执行
                        if delay_run > 0:
                            with AllureReporter.step(f"延迟执行 | step={step_id} | seconds={delay_run}"):
                                AllureReporter.attach_text("延迟执行秒数", delay_run)
                            time.sleep(delay_run)

                        # 读取 override, 为 None 时设置为 空dict
                        override = step.get("override", {}) or {}

                        # 执行一次完整接口调用
                        invoke_result = self._execute_api(
                            api=api,
                            ctx=flow_ctx,
                            transport=transport,
                            env=env,
                            request_defaults=request_defaults,
                            override=override,
                            step_id=step_id,
                            flow_file=flow.source,
                        )

                        # 回填结果对象
                        step_result.request = invoke_result.request
                        step_result.response = invoke_result.response
                        step_result.extract_out = invoke_result.extract
                        step_result.assertions = invoke_result.assertions

                        # 挂当前 step 的阶段性结果
                        AllureReporter.attach_json("当前 flow step 执行结果", step_result.to_dict())

                    except Exception as e:
                        # 把当前单步 step 错误写入 step 结果对象中
                        step_result.error = e
                        # 挂当前 step 异常附件
                        AllureReporter.attach_exception(e, traceback_text=traceback.format_exc())
                        # 继续向上抛出, 触发 flow 外层异常处理
                        raise

            # 主流程执行成功
            main_success = True
            # 返回执行的总结果
            return result

        except Exception as e:
            # 捕获 flow 主流程异常, 并抛出
            result.error = e
            # 挂 flow 异常附件
            AllureReporter.attach_exception(e, traceback_text=traceback.format_exc())
            raise

        # 无论成功失败都释放 session 以及执行 cleanup
        finally:
            try:
                self._run_cleanup(
                    cleanup=flow.cleanup,
                    ctx=flow_ctx,
                    state=state,
                    transport=transport,
                    env=env,
                    request_defaults=request_defaults,
                    main_success=main_success,
                    yaml_location=flow.source,
                )
            finally:
                # flow.cleanup 执行结束后, 再统一回填当前生命周期最终状态
                result.cleanup_errors = list(state.cleanup_errors)
                result.executed_auth_profiles = sorted(state.executed_profiles)
                result.executed_depends_keys = sorted(state.executed_depends)

                # 挂生命周期执行状态摘要
                AllureReporter.attach_execution_state(state)
                AllureReporter.attach_context("业务流执行完毕后的上下文数据", flow_ctx)
                # 挂 flow 最终汇总结果
                AllureReporter.attach_flow_result(result)

                transport.close()

    def _ensure_loaded(self):
        """
          确保 repo 已执行 load 方法
        """
        # 判断是否未加载
        if self.repo.config is None or self.repo.apis is None or self.repo.flows is None:
            self.repo.load()

    def _build_suite_ctx(self) -> RuntimeContext:
        """
          将 static 注入 suite_ctx
        :return: RuntimeContext 上下文
        """
        # 创建空 ctx
        ctx = RuntimeContext({})
        # 注入 static, 可在 YAML 用 ${} 直接引用
        ctx.update(self.repo.config.static or {})
        return ctx

    def _build_depends_dedupe_key(self, step: Dict[str, Any]) -> str:
        """
          构建 depends_on 的去重键

          规则:
            1.优先使用 id 去重
            2.id 不存在时使用 ref 引用名
        :param step: depends_on 单个步骤结构
        :return: 去重键字符串
        """
        # 读取步骤 id
        step_id = step.get("id")
        if step_id:
            return step_id
        return step.get("ref")

    def _execute_api(
        self,
        api: ApiItem,
        ctx: RuntimeContext,
        transport: TransportBase,
        env: Dict[str, Any],
        request_defaults: Dict[str, Any],
        override: Optional[Dict[str, Any]] = None,
        data_index: int = 0,
        *,
        step_id: Optional[str] = None,
        flow_file: Optional[str] = None,
        profile_name: Optional[str] = None,
        yaml_file: Optional[str] = None,
    ):
        """
          执行一次完整调用

        :param api: 接口模板对象
        :param ctx: 运行上下文
        :param transport: 传输层对象
        :param env: 当前环境数据
        :param request_defaults: 请求默认项
        :param override: 覆盖/合并结构
        :param data_index: body/params/files 为 list 时使用哪一条数据
        :param step_id: 业务流的步骤名称
        :param flow_file: 业务流文件
        :param profile_name: 前置接口名称
        :param yaml_file: 当前错误应归属于哪个 yaml 文件
        :return: 公共接口执行结果
        """
        # 初始化, 避免后续反复判空
        override = override or {}
        # 读取 override.request, 若不存在则使用空 dict
        override_request = override.get("request", {})

        # 合并/覆盖响应提取规则, 若 override.extract 不存在则使用接口库里的
        extract_rules = override.get("extract") if override.get("extract", None) is not None \
            else api.extract
        # 断言规则同理
        assertions_rules = override.get("assertions") if override.get("assertions", None) is not None \
            else api.assertions

        # 初始化提取轨迹列表, 供 Allure 报告展示
        extract_trace: List[Dict[str, Any]] = []

        try:
            # 创建请求构建步骤
            with AllureReporter.step(f"构建请求 | api={api.api_id} | step={step_id or api.api_id}"):

                AllureReporter.attach_context("构建请求前的上下文数据", ctx)
                AllureReporter.attach_json("全局默认请求参数", request_defaults)
                AllureReporter.attach_json("当前步骤的局部覆盖/合并数据", override_request)

                # 构建完整请求
                prepared = self.resolver.resolve(
                    api_request=api.request,
                    request_defaults=request_defaults,
                    override_request=override_request,
                    ctx=ctx,
                    env=env,
                    data_index=data_index,
                    api_id=api.api_id,
                    flow_file=flow_file,
                    step_id=step_id,
                    profile_name=profile_name,
                    yaml_file=yaml_file
                )
                # 把已构建请求挂到当前步骤
                AllureReporter.attach_prepared_request(prepared)

            # 创建发送请求步骤
            with AllureReporter.step(f"发送请求 | {prepared.method.upper()} {prepared.url}"):
                # 发送请求
                response_obj = transport.send(
                    prepared,
                    api_id=api.api_id,
                    flow_file=flow_file,
                    step_id=step_id,
                    profile_name=profile_name,
                    yaml_file=yaml_file
                )
                # 生成响应快照
                response_snapshot = ResponseSnapshot.format_response(response_obj)
                # 挂响应摘要附件
                AllureReporter.attach_response_snapshot(response_snapshot)

            # 生成请求数据快照, 供日志/报告/报错使用
            request_snapshot = prepared.to_dict()

            # 初始化响应提取数据后的结果
            extract_out = {}

            # 创建提取变量步骤
            with AllureReporter.step(f"提取变量 | count={len(extract_rules or [])}"):
                # 若有提取规则, 则执行提取
                if extract_rules:
                    AllureReporter.attach_json("提取规则", extract_rules)
                    extract_out = self.extractor.apply(
                        rules=extract_rules,
                        response=response_obj,
                        ctx=ctx,
                        api_id=api.api_id,
                        flow_file=flow_file,
                        step_id=step_id,
                        profile_name=profile_name,
                        yaml_file=yaml_file,
                        request=request_snapshot,
                        trace_collector=extract_trace,
                    )
                # 挂提取执行轨迹
                AllureReporter.attach_extract_trace(extract_trace)
                # 挂最终提取结果
                AllureReporter.attach_extract_out(extract_out)
                # 遍历每条提取轨迹, 生成更细粒度的子步骤
                for item in extract_trace:
                    # 读取当前提取变量名, 取不到时回退为 unknown
                    label = item.get("as") or item.get("rule", {}).get("as") or "unknown"
                    # 创建单条提取明细步骤
                    with AllureReporter.step(f"extract 明细 | as={label}"):
                        AllureReporter.attach_json("当前提取轨迹详情", item)
                # 若没有提取规则, 则挂说明文本
                else:
                    AllureReporter.attach_text("extract_info", "当前接口未配置 extract 规则")

            # 创建断言执行步骤
            with AllureReporter.step(f"执行断言 | count={len(assertions_rules or [])}"):
                # 若存在断言规则, 则先挂规则列表
                if assertions_rules:
                    AllureReporter.attach_json("断言规则列表", assertions_rules)
                else:
                    AllureReporter.attach_text("assertions_info", "当前接口未配置 assertions 规则")

                # 执行断言, 并且写入 result 用于日志/报告的打印
                assertions = self.assert_engine.assert_all(
                    assertions=assertions_rules,
                    response=response_obj,
                    ctx=ctx,
                    api_id=api.api_id,
                    flow_file=flow_file,
                    step_id=step_id,
                    profile_name=profile_name,
                    yaml_file=yaml_file,
                    request_snapshot=request_snapshot
                )
                # 遍历断言结果列表
                for index, item in enumerate(assertions, start=1):
                    # 创建单条断言明细步骤
                    with AllureReporter.step(f"断言明细 | index={index} | passed={item.passed}"):
                        # 挂当前断言结果详情
                        AllureReporter.attach_assertion_result(index, item)

            # 返回公共执行结果
            return ApiInvokeResult(
                request=prepared,
                response=response_snapshot,
                extract=extract_out,
                assertions=assertions
            )
        # 若执行链任意阶段失败, 则在此统一挂异常并继续抛出
        except Exception as e:
            # 若失败前已经有提取轨迹, 则优先挂出现场数据
            if extract_trace:
                AllureReporter.attach_extract_trace(extract_trace)
            # 挂异常文本、上下文与栈信息
            AllureReporter.attach_exception(e, traceback_text=traceback.format_exc())
            raise

