# -*- coding: utf-8 -*-

from __future__ import annotations

import time
from typing import Optional

from requests import Response

from Core.context import RuntimeContext
from Core.repository import YamlRepository
from Engine.extractor import Extractor

from Engine.request_resolver import RequestResolver
from Engine.transport import RequestsTransport, SessionTransport
from Engine.auth_runner import AuthRunner
from Engine.assertion_engine import AssertionEngine
from Engine.results import CaseResult, FlowResult, StepResult


class Executor:  # （，不做 schema 兜底）  #
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

        # 初始化前置模板 执行器 runner
        self.auth = AuthRunner(repo=repo, resolver=self.resolver, extractor=self.extractor)

    def run_single(self, api_id: str) -> CaseResult:
        """
          执行 single.yaml 中的单接口用例（使用 RequestsTransport）

        :param api_id: 接口 id
        :return: CaseResult
        """
        # 确保 repo 已加载
        self._ensure_loaded()

        # 获取接口定义
        api = self.repo.get_api(api_id)

        # 根据 config.yaml 里的 run_control 决定是否 跳过/仅执行 某些 api
        should_run = self._should_run_single(api_id=api_id, api_is_run=api.is_run)

        # 初始化结果, 方便日志/报告的打印
        result = CaseResult(api_id=api.api_id, case_id=api.case_id, is_run=should_run)

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

        # 记录执行开始时间
        t0 = time.perf_counter()
        try:
            # 若该接口需要执行前置接口
            if api.auth_profile:
                # 先执行前置接口
                self.auth.run(
                    profile_name=api.auth_profile,
                    ctx=case_ctx,
                    transport=RequestsTransport(),
                    env=env,
                    request_defaults=request_defaults,
                    where=f"auth_profiles.{api.auth_profile}"
                )

            # 构建 "可直接发送" 的请求信息
            prepared = self.resolver.resolve(
                api_request=api.request,
                request_defaults=request_defaults,
                override_request=None,
                ctx=case_ctx,
                env=env,
                where=f"single.apis.{api_id}",
                api_id=api_id
            )
            # 将构建好的请求信息, 存入结果中, 方便日志/报告的打印
            result.request = prepared

            # 发送请求, 获取响应
            resp = RequestsTransport().send(prepared)

            # 写入状态码
            result.status_code = resp.status_code
            # 写入 response.text
            result.response_text = self._summary_text(resp)

            # 若存在提取规则
            if api.extract:
                # 从响应中提取指定数据存入 ctx 中, 并且写入 result 用于日志/报告的打印
                result.extract_out = self.extractor.apply(
                    rules=api.extract,
                    response=resp,
                    ctx=case_ctx,
                    where=f"single.apis.{api_id}.extract"
                )

            # 执行断言, 并且写入 result 用于日志/报告的打印
            result.assertions = self.assert_engine.assert_all(
                assertions=api.assertions,
                response=resp,
                ctx=case_ctx,
                where=f"single.apis.{api_id}"
            )

            # 写入 result 耗时
            result.elapsed_ms = (time.perf_counter() - t0) * 1000.0

            # 返回结果, 用于日志/报告的打印
            return result
        except Exception as e:
            # 写入 result 耗时
            result.elapsed_ms = (time.perf_counter() - t0) * 1000.0
            # 写入 result 错误文本
            result.error = str(e)
            raise

    def run_flow(self, flow_id: Optional[str] = None) -> FlowResult:  # 执行业务流  #
        """
          执行业务流, multiple.yaml 里的 flows
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

        # 定义定位路径, 优先用 source(文件#序号)
        where_root = flow.source or f"flows.{flow.flow_id}"

        # 记录开始执行时间
        t0 = time.perf_counter()
        try:
            # 若 flow 的前置接口需要执行
            if flow.auth_profile:
                self.auth.run(
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

                # 初始化 StepResult, 方便日志/报告的打印
                step_result = StepResult(step_name=step_name, api_id=api_id, is_run=step_is_run)

                # 把单步 step 加入 flows 总结果, 方便日志/报告的打印
                result.steps.append(step_result)

                # 若 step 不执行, 则跳过
                if not step_is_run:
                    continue

                # 获取接口模板
                api = self.repo.get_api(api_id)

                # 若该 api 需要执行单独的前置接口, 且该前置接口未执行过
                if api.auth_profile and api.auth_profile not in executed_profiles:
                    self.auth.run(
                        profile_name=api.auth_profile,
                        ctx=flow_ctx,
                        transport=st,
                        env=env,
                        request_defaults=request_defaults,
                        where=f"{where_root}.auth_profiles.{api.auth_profile}"
                    )
                    # 记录已执行的前置接口
                    executed_profiles.add(api.auth_profile)

                # 读取 override, 为 None 时设置为 空dict
                override = step.get("override", {}) or {}

                # 取 override.request (业务流需要覆盖的数据)
                override_request = override.get("request", {}) if isinstance(override, dict) else {}

                # 定位字符串, 方便报错调试
                where = f"{where_root}.steps[{idx}].{step_name}"

                # 构建 "可直接发送" 的请求信息
                prepared = self.resolver.resolve(
                    api_request=api.request,
                    request_defaults=request_defaults,
                    override_request=override_request,
                    ctx=flow_ctx, env=env,
                    where=where,
                    api_id=api_id,
                    step_name=step_name
                )
                # 将构建好的请求信息, 存入结果中, 方便日志/报告的打印
                step_result.request = prepared

                # 发送请求
                resp = st.send(prepared)

                # 往结果中存入本次响应状态码, 方便日志/报告的打印
                step_result.status_code = resp.status_code
                # 往结果中存入本次响应摘要, 方便日志/报告的打印
                step_result.response_text = self._summary_text(resp)

                # 获取 业务流引用的重写 提取/断言数据 内容 (若引用的该部分获取为 None, 则使用 接口库里的数据)
                # step override.extract 优先
                extract_rules = override.get("extract") if override.get("extract", None) is not None else api.extract
                # step override.assertions 优先
                assertions_rules = override.get("assertions") if override.get("assertions", None) is not None else api.assertions

                # 若有提取规则, 则执行提取
                if extract_rules:
                    # 从响应中提取指定数据存入 ctx 中, 并且写入 result 用于日志/报告的打印
                    step_result.extract_out = self.extractor.apply(
                        rules=extract_rules,
                        response=resp,
                        ctx=flow_ctx,
                        where=f"{where}.extract"
                    )

                # 执行断言, 并且写入 result 用于日志/报告的打印
                step_result.assertions = self.assert_engine.assert_all(
                    assertions=assertions_rules,
                    response=resp,
                    ctx=flow_ctx,
                    where=where,
                )

            # 写入耗时
            result.elapsed_ms = (time.perf_counter() - t0) * 1000.0

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

    def _should_run_single(self, api_id: str, api_is_run: Optional[bool]) -> bool:
        """
          根据 config.yaml 里的 run_control 决定是否 跳过/仅执行 某些 api

        :param api_id: 接口 id
        :param api_is_run: 根据名单决定该 api 是否执行
        :return: 返回 bool, 决定是否执行
        """
        # 读取 run_control, 为 None 时设为 空dict
        rc = self.repo.config.run_control or {}

        # 全局开关, 不填默认为 True, 如果全局开关为 False, 则全部不执行
        global_is_run = rc.get("is_run", True)
        if not global_is_run:
            return False

        # 仅执行的接口列表
        only_apis = set(rc.get("only_apis", []) or [])
        # 若白名单非空, 但该 api 不在白名单中, 则该 api 不执行
        if only_apis and api_id not in only_apis:
            return False

        # 跳过执行的接口列表
        skip_apis = set(rc.get("skip_apis", []) or [])
        # 若当前 api 在黑名单中, 跳过执行
        if api_id in skip_apis:
            return False

        # 若 single.yaml 里的 api 显式写了 is_run, 在全局开关为 True, 且在白名单, 不在黑名单(或两个名单为空) 情况下生效
        # 优先级最低
        if api_is_run is False:
            return False

        # 其它情况下允许执行
        return True

    def _summary_text(self, resp: Response, limit: int = 500) -> str:  # 响应摘要  #
        """
          获取响应摘要
          注意: 返回的是 response.text, 而不是 response.json或其它
        :param resp: 响应包
        :param limit: 获取前 limit 个文本
        :return: 返回响应摘要
        """
        try:
            # 取 text, 并返回
            txt = resp.text or ""
            return txt
        except Exception:
            return "<response.text decode error>"
