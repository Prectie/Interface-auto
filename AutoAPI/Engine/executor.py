# -*- coding: utf-8 -*-

from __future__ import annotations

import time
from typing import Optional, Any, Dict, List, Tuple

from requests import Response

from Core.context import RuntimeContext
from Core.repository import YamlRepository
from Engine.extractor import Extractor

from Engine.request_resolver import RequestResolver
from Engine.transport import RequestsTransport, SessionTransport, TransportBase
from Engine.assertion_engine import AssertionEngine
from Engine.results import CaseResult, FlowResult, StepResult, ApiInvokeResult
from Exceptions.AutoApiException import to_response_snapshot, build_api_exception_context, ExceptionCode, \
    PipelineException, AutoApiException
from Schema.data_validation import ApiItem
from Utils.log_utils import LoggerManager

logger = LoggerManager.get_logger()


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
        transport: TransportBase,
        env: Dict[str, Any],
        request_defaults: Dict[str, Any],
        *,
        api_id: Optional[str] = None,
        flow_file: Optional[str] = None,
        where: str,
    ) -> Dict[str, Any]:
        """
          执行前置接口

          作用:
            - 按 order 执行指定 pre_apis
            - 支持 override.request 覆盖接口库模板请求数据
            - extract 与 assertions 均是 override 优先级最高
            - 执行 extract 写入 ctx

        :param profile_name: 前置接口名称
        :param ctx: 上下文（写入 token 等）
        :param transport: 发包器（single 用 requests，flow 用 session）
        :param env: env 当前环境数据
        :param request_defaults: static 静态配置
        :param where: 定位字符串
        :return: 整理后的提取结果 dict
        """
        try:
            # 取 config 数据对象
            cfg = self.repo.config

            # 取 auth_profiles, 允许为空
            profiles = cfg.auth_profiles or {}
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
            profile = profiles[profile_name]
            # 取 pre_apis
            pre_apis = profile.get("pre_apis", {})
            # 排序
            profile_steps = self._sort_steps(pre_apis)

            # 初始化提取结果
            extract_all: Dict[str, Any] = {}

            # 遍历每个 step
            for step_name, step_body in profile_steps:
                # 读取 is_run, 若为 False 则不执行(不填默认为 True)
                is_run = step_body.get("is_run", True)
                if not is_run:
                    # 为 False 时跳过执行
                    continue

                # 读取 ref
                ref = step_body.get("ref", "")
                # 从接口库取接口模板
                api = self.repo.get_api(ref)

                # 读取 override, 为 None 设 空dict
                override = step_body.get("override", {}) or {}

                # 执行一次完整调用
                invoke_result = self._execute_api(
                    api=api,
                    ctx=ctx,
                    transport=transport,
                    env=env,
                    request_defaults=request_defaults,
                    step_name=step_name,
                    override=override,
                )

                if invoke_result.extract:
                    ctx.update(invoke_result.extract)
                    extract_all.update(invoke_result.extract)

            # 返回提取结果
            return extract_all

        # AuthProfileError情况直接抛出
        except AutoApiException:
            # 已结构化的异常直接抛出
            raise
        # 其他异常
        except Exception as e:
            # 构建明确异常上下文
            error_context = build_api_exception_context(
                error_code=ExceptionCode.PIPELINE_ERROR,
                message="前置接口执行失败",
                reason=str(e),
                yaml_location=where,
                hint="请检查前置接口的 ref、request、extract 等数据是否正确",
            )
            raise PipelineException(error_context)

    def _sort_steps(self, pre_apis: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
        """
          对 pre_apis 下的前置接口 按 order 升序排序
        :param pre_apis: 前置接口名称
        :return: 返回 List[(step_name, step_body)]
        """
        # 初始化返回结果
        items = []

        # 遍历 dict
        for name, body in pre_apis.items():
            # 仅保留 dict
            if isinstance(body, dict):
                items.append((name, body))

        # 按 order 排序
        items.sort(key=lambda x: int(x[1].get("order", 0) or 0))

        return items

    def run_single(self, api_id: str, data_index: int) -> CaseResult:
        """
          执行 single.yaml 中的单接口用例（使用 RequestsTransport）

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
            return result

        # 构建 suite_ctx(静态 ctx, 从 config.yaml.static 获取)
        suite_ctx = self._build_suite_ctx()
        # 通过 fork, 避免污染原数据
        case_ctx = suite_ctx.fork()
        # 获取 env 数据
        env = self.repo.config.env
        # 获取 request_defaults 数据
        request_defaults = self.repo.config.request_defaults

        # 创建单次请求 transport
        transport = RequestsTransport()

        try:
            # 若该接口需要执行前置接口
            if api.auth_profile:
                # 先执行前置接口
                self._run_auth_profile(
                    profile_name=api.auth_profile,
                    ctx=case_ctx,
                    transport=RequestsTransport(),
                    env=env,
                    request_defaults=request_defaults,
                    where=f"auth_profiles.{api.auth_profile}"
                )

            # 执行一次完整接口调用
            invoke_result = self._execute_api(
                api=api,
                ctx=case_ctx,
                transport=transport,
                env=env,
                request_defaults=request_defaults,
                request_where=f"single.yaml.api.{api_id}",
            )

            # 回填结果对象, 方便日志/报告打印
            result.request = invoke_result.request
            result.response = invoke_result.response
            result.extract_out = invoke_result.extract
            result.assertions = invoke_result.assertions

            if invoke_result.extract:
                case_ctx.update(invoke_result.extract)

            # 返回结果, 用于日志/报告的打印
            return result
        except Exception as e:
            # 写入 result 错误文本
            result.error = e
            raise

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
        result = FlowResult(flow_id=flow.flow_id, is_run=bool(flow.is_run))

        # 若 flow 不执行, 则跳过
        if not flow.is_run:
            return result

        # 构建 suite_ctx(静态 ctx, 从 config.yaml.static 获取)
        suite_ctx = self._build_suite_ctx()
        # 通过 fork, 避免污染原数据
        # 注:业务流共享
        flow_ctx = suite_ctx.fork()

        # 获取 env 数据
        env = self.repo.config.env
        # 获取 request_defaults 数据(默认参数, 比如默认请求头 headers)
        request_defaults = self.repo.config.request_defaults

        # 创建 session transport(flow 使用会话进行发送请求操作)
        st = SessionTransport()

        # 记录已执行的前置接口 (避免重复)
        executed_profiles: set[str] = set()

        # 定位路径, 优先用 source(文件#序号)
        where_root = flow.source

        # 记录开始执行时间
        t0 = time.perf_counter()
        try:
            # 若 flow 的前置接口需要执行
            if flow.auth_profile:
                logger.debug(f"执行前置{flow.auth_profile}")
                self._run_auth_profile(
                    profile_name=flow.auth_profile,
                    ctx=flow_ctx,
                    transport=st,
                    env=env,
                    request_defaults=request_defaults,
                    where=f"{where_root}.auth_profiles.{flow.auth_profile}"
                )
                # 记录已执行 profile
                executed_profiles.add(flow.auth_profile)

            # 遍历 steps
            for idx, step in enumerate(flow.steps, start=1):
                # 获取 step 名称, 若没有按照顺序下标进行命名
                step_name = str(step.get("name") or f"step_{idx}")

                # 获取 step 开关 (不填默认 True)
                step_is_run = bool(step.get("is_run", True))

                # 获取 ref, 从接口库里引用的接口模板
                api_id = str(step.get("ref", ""))

                # 获取 delay_run, step 执行前的延迟秒数,
                # 不填该字段默认 0, 为假值(显式 None)时也默认为 0
                delay_run = float(step.get("delay_run", 0) or 0)

                # 初始化 StepResult, 方便日志/报告的打印
                step_result = StepResult(
                    step_name=step_name,
                    ref_api_id=api_id,
                    is_run=step_is_run,
                    delay_run=delay_run
                )

                # 把单步 step 加入 flows 总结果, 方便日志/报告的打印
                result.steps.append(step_result)

                # 若 step 不执行, 则跳过
                if not step_is_run:
                    continue

                # 获取接口模板
                api = self.repo.get_api(api_id)

                # 若该 api 需要执行单独的前置接口, 且该前置接口未执行过
                if api.auth_profile and api.auth_profile not in executed_profiles:
                    logger.debug(f"执行前置{api.auth_profile}")
                    self._run_auth_profile(
                        profile_name=api.auth_profile,
                        ctx=flow_ctx,
                        transport=st,
                        env=env,
                        request_defaults=request_defaults,
                        where=f"{where_root}.auth_profiles.{api.auth_profile}"
                    )
                    # 记录已执行的前置接口
                    executed_profiles.add(api.auth_profile)

                # 若存在延迟执行
                if delay_run > 0:
                    time.sleep(delay_run)

                # 读取 override, 为 None 时设置为 空dict
                override = step.get("override", {}) or {}

                # 执行一次完整接口调用
                invoke_result = self._execute_api(
                    api=api,
                    ctx=flow_ctx,
                    transport=st,
                    env=env,
                    request_defaults=request_defaults,
                    step_name=step_name,
                    override=override,
                )

                # 回填结果对象
                step_result.request = invoke_result.request
                step_result.response = invoke_result.response
                step_result.extract_out = invoke_result.extract
                step_result.assertions = invoke_result.assertions

                # 若有提取规则, 则执行提取
                if invoke_result.extract:
                    flow_ctx.update(invoke_result.extract)

            # 返回执行的总结果
            return result

        # 无论成功失败都释放 session
        finally:
            st.close()

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

    def _execute_api(
        self,
        api: ApiItem,
        ctx: RuntimeContext,
        transport: TransportBase,
        env: Dict[str, Any],
        request_defaults: Dict[str, Any],
        step_name: Optional[str] = None,
        override: Optional[str] = None,
        data_index: int = 0,
        extract_where_root: Optional[str] = None,
        assert_where_root: Optional[str] = None
    ):
        """
          执行一次完整调用

        :param api: 接口模板对象
        :param ctx: 运行上下文
        :param transport: 传输层对象
        :param env: 当前环境数据
        :param request_defaults: 请求默认项
        :param step_name: 业务流或前置接口步骤名称
        :param override: 覆盖/合并结构
        :param data_index: body/params/files 为 list 时使用哪一条数据
        :param extract_where_root: extract 所属规则根路径
        :param assert_where_root: assertions 所属规则根路径
        :return: 公共接口执行结果
        """
        # 初始化, 避免后续反复判空
        override = override or {}
        # 读取 override.request, 若不存在则使用空 dict
        override_request = override.get("request", {})

        # 构建完整请求
        prepared = self.resolver.resolve(
            api_request=api.request,
            request_defaults=request_defaults,
            override_request=override_request,
            ctx=ctx,
            env=env,
            api_id=api.api_id,
            step_name=step_name,
            data_index=data_index
        )

        # 发送请求
        response_obj = transport.send(prepared)

        # 合并/覆盖响应提取规则, 若 override.extract 不存在则使用接口库里的
        extract_rules = override.get("extract") if override.get("extract", None) is not None \
            else api.extract
        # 断言规则同理
        assertions_rules = override.get("assertions") if override.get("assertions", None) is not None \
            else api.assertions

        # 生成请求数据快照, 供日志/报告/报错使用
        request_snapshot = prepared.to_dict()
        # 同理, 生成响应快照
        response_snapshot = to_response_snapshot(response_obj)

        # 初始化响应提取数据后的结果
        extract_out = {}
        # 若有提取规则, 则执行提取
        if extract_rules:
            extract_out = self.extractor.apply(
                rules=extract_rules,
                response=response_obj,
                ctx=ctx,
                api_id=api.api_id,
                step_name=step_name,
                request=request_snapshot
            )

        # 执行断言, 并且写入 result 用于日志/报告的打印
        assertions = self.assert_engine.assert_all(
            assertions=assertions_rules,
            response=response_obj,
            ctx=ctx,
            api_id=api.api_id,
            step_name=step_name,
            request_snapshot=request_snapshot
        )

        # 返回公共执行结果
        return ApiInvokeResult(
            request=prepared,
            response=response_snapshot,
            extract=extract_out,
            assertions=assertions
        )

