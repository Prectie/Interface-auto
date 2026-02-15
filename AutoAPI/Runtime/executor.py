# -*- coding: utf-8 -*-  # 声明源码编码，避免中文注释乱码  #

from __future__ import annotations  # 允许前向引用类型注解  #

import time  # 导入 time，用于耗时统计  #
from typing import Any, Dict, Optional, List  # 导入类型注解  #

from requests import Response  # 导入 Response  #

from Base.context import RuntimeContext  # 导入运行时上下文  #
from Base.repository import YamlRepository  # 导入 yaml 仓库  #
from Base.extractor import Extractor, extract_error  # 导入提取器与异常  #

from Runtime.request_resolver import RequestResolver  # 导入请求解析器  #
from Runtime.transport import RequestsTransport, SessionTransport  # 导入传输层实现  #
from Runtime.auth_runner import AuthRunner  # 导入鉴权 runner  #
from Runtime.assertion_engine import AssertionEngine  # 导入断言引擎  #
from Runtime.results import CaseResult, FlowResult, StepResult  # 导入结果对象  #
from Runtime.runtime_exception import ApiRuntimeError, RuntimeErrorDetail, ResponseProcessError  # 导入执行期异常  #


class Executor:  # 执行器（只编排，不做 schema 兜底）  #
    """executor 类实现  # 类说明
    executor 负责串起 repository/context/resolver/transport/extractor/assertion/auth，完成 single/multiple 执行流程。  # 类职责说明
    """  # 类说明结束  #

    def __init__(self, repo: YamlRepository):  # 初始化执行器  #
        self.repo = repo  # 保存仓库  #
        self.resolver = RequestResolver()  # 初始化请求解析器  #
        self.extractor = Extractor()  # 初始化提取器  #
        self.assert_engine = AssertionEngine()  # 初始化断言引擎  #
        self.auth = AuthRunner(repo=repo, resolver=self.resolver, extractor=self.extractor)  # 初始化鉴权 runner  #

    def run_single(self, api_id: str, fail_fast: bool = True) -> CaseResult:  # 执行单接口  #
        """run_single 方法  # 方法说明
        功能说明：执行 single.yaml 中的单接口用例（使用 RequestsTransport）。  # 功能说明
        参数说明：api_id：接口 id；fail_fast：断言失败是否立即抛错（这里用于断言引擎内部）。  # 参数说明
        返回值说明：CaseResult。  # 返回值说明
        在系统中的作用：提供最小执行单元，支持 pytest 参数化逐条跑接口库。  # 系统作用
        调用关系：pytest 用例调用本方法。  # 调用关系
        """  # 方法说明结束  #
        self._ensure_loaded()  # 确保 repo 已加载  #

        api = self.repo.get_api(api_id)  # 获取接口定义  #
        should_run = self._should_run_single(api_id=api_id, api_is_run=api.is_run)  # 决策是否执行  #
        result = CaseResult(api_id=api.api_id, case_id=api.case_id, is_run=should_run)  # 初始化结果  #

        if not should_run:  # 若不执行  #
            return result  # 直接返回  #

        suite_ctx = self._build_suite_ctx()  # 构建 suite_ctx  #
        case_ctx = suite_ctx.fork()  # fork case_ctx（隔离）  #

        env = self.repo.config.env  # 当前 env 体  #
        static = self.repo.config.static  # static 体  #

        t0 = time.perf_counter()  # 记录开始时间  #
        try:  # 捕获执行异常  #
            if api.auth_profile:  # 若该接口需要鉴权  #
                self.auth.run(profile_name=api.auth_profile, ctx=case_ctx, transport=RequestsTransport(), env=env, static=static, where=f"auth_profiles.{api.auth_profile}")  # 执行鉴权链  #

            prepared = self.resolver.resolve(api_request=api.request, override_request=None, ctx=case_ctx, env=env, static=static, where=f"single.apis.{api_id}", api_id=api_id)  # 构建请求  #
            resp = RequestsTransport().send(prepared)  # 发包获取响应  #

            result.prepared = prepared  # 写入 prepared  #
            result.status_code = resp.status_code  # 写入状态码  #
            result.response_text = self._summary_text(resp)  # 写入响应摘要  #

            if api.extract:  # 若存在提取规则  #
                result.extract_out = self.extractor.apply(rules=api.extract, response=resp, ctx=case_ctx, where=f"single.apis.{api_id}.extract")  # 提取并写 ctx  #

            result.assertions = self.assert_engine.assert_all(assertions=api.assertions, response=resp, ctx=case_ctx, where=f"single.apis.{api_id}", fail_fast=fail_fast)  # 执行断言  #

            result.elapsed_ms = (time.perf_counter() - t0) * 1000.0  # 写入耗时  #
            return result  # 返回结果  #
        except Exception as e:  # 捕获异常  #
            result.elapsed_ms = (time.perf_counter() - t0) * 1000.0  # 写入耗时  #
            result.error = str(e)  # 写入错误文本  #
            raise  # 直接向上抛（pytest 失败更明显；你也可改为不抛只记录）  #

    def run_flow(self, flow_id: Optional[str] = None, fail_fast: bool = True) -> FlowResult:  # 执行业务流  #
        """run_flow 方法  # 方法说明
        功能说明：执行 multiple.yaml 中的业务流（使用 SessionTransport）。  # 功能说明
        参数说明：flow_id：可选，若不传则执行 YAML 中的 flow_id；fail_fast：断言失败是否立即抛错。  # 参数说明
        返回值说明：FlowResult。  # 返回值说明
        在系统中的作用：支持企业接口自动化最常见的“多接口依赖链路”验证。  # 系统作用
        调用关系：pytest 用例调用本方法。  # 调用关系
        """  # 方法说明结束  #
        self._ensure_loaded()  # 确保 repo 已加载  #

        flow = self.repo.get_flow()  # 获取 flow 定义  #
        fid = flow.flow_id if flow_id is None else str(flow_id).strip()  # 决定 flow_id  #
        res = FlowResult(flow_id=fid, is_run=bool(flow.is_run))  # 初始化结果  #

        if not flow.is_run:  # 若 flow 不执行  #
            return res  # 直接返回  #

        suite_ctx = self._build_suite_ctx()  # 构建 suite_ctx  #
        flow_ctx = suite_ctx.fork()  # fork flow_ctx（业务流共享）  #

        env = self.repo.config.env  # env 体  #
        static = self.repo.config.static  # static 体  #

        st = SessionTransport()  # 创建 session transport（贯穿全 flow）  #

        executed_profiles: set[str] = set()  # 记录已执行的鉴权模板（避免重复）  #

        t0 = time.perf_counter()  # 记录开始时间  #
        try:  # 捕获执行异常  #
            if flow.auth_profile:  # 若 flow 级鉴权存在  #
                self.auth.run(profile_name=flow.auth_profile, ctx=flow_ctx, transport=st, env=env, static=static, where=f"auth_profiles.{flow.auth_profile}")  # 执行鉴权  #
                executed_profiles.add(flow.auth_profile)  # 记录已执行 profile  #

            for idx, step in enumerate(flow.steps, start=1):  # 遍历 steps  #
                step_name = str(step.get("name") or f"step_{idx}")  # 获取 step 名称  #
                step_is_run = bool(step.get("is_run", True))  # 获取 step 开关（默认 True）  #
                api_id = str(step.get("ref", "")).strip()  # 获取 ref  #

                sr = StepResult(step_name=step_name, api_id=api_id, is_run=step_is_run)  # 初始化 StepResult  #
                res.steps.append(sr)  # 加入 flow 结果  #

                if not step_is_run:  # 若 step 不执行  #
                    continue  # 跳过  #

                api = self.repo.get_api(api_id)  # 获取接口模板  #

                if api.auth_profile and api.auth_profile not in executed_profiles:  # 若该 api 需要额外鉴权且未执行过  #
                    self.auth.run(profile_name=api.auth_profile, ctx=flow_ctx, transport=st, env=env, static=static, where=f"auth_profiles.{api.auth_profile}")  # 执行鉴权  #
                    executed_profiles.add(api.auth_profile)  # 记录已执行  #

                override = step.get("override", {}) or {}  # 读取 override  #
                override_request = override.get("request", {}) if isinstance(override, dict) else {}  # 取 override.request  #

                where = f"multiple.flow.{fid}.steps[{idx}].{step_name}"  # 定位字符串  #
                prepared = self.resolver.resolve(api_request=api.request, override_request=override_request, ctx=flow_ctx, env=env, static=static, where=where, api_id=api_id, step_name=step_name)  # 构建请求  #
                resp = st.send(prepared)  # 发包  #

                sr.prepared = prepared  # 写入 prepared  #
                sr.status_code = resp.status_code  # 写入状态码  #
                sr.response_text = self._summary_text(resp)  # 写入响应摘要  #

                extract_rules = override.get("extract") if isinstance(override, dict) and isinstance(override.get("extract"), list) else api.extract  # step override.extract 优先  #
                assertions_rules = override.get("assertions") if isinstance(override, dict) and isinstance(override.get("assertions"), list) else api.assertions  # step override.assertions 优先  #

                if extract_rules:  # 若有提取规则  #
                    sr.extract_out = self.extractor.apply(rules=extract_rules, response=resp, ctx=flow_ctx, where=f"{where}.extract")  # 执行提取  #

                sr.assertions = self.assert_engine.assert_all(assertions=assertions_rules, response=resp, ctx=flow_ctx, where=where, fail_fast=fail_fast)  # 执行断言  #

            res.elapsed_ms = (time.perf_counter() - t0) * 1000.0  # 写入耗时  #
            return res  # 返回 flow 结果  #
        finally:  # 无论成功失败都释放 session  #
            st.close()  # 关闭 session  #

    def _ensure_loaded(self) -> None:  # 确保 repo 已 load  #
        """_ensure_loaded 方法  # 方法说明
        功能说明：若 repo 未 load，则调用 repo.load。  # 功能说明
        参数说明：无。  # 参数说明
        返回值说明：无。  # 返回值说明
        在系统中的作用：确保 executor 可直接使用。  # 系统作用
        调用关系：被 run_single/run_flow 调用。  # 调用关系
        """  # 方法说明结束  #
        if self.repo.config is None or self.repo.apis is None or self.repo.flows is None:  # 判断是否未加载  #
            self.repo.load()  # 加载 yaml  #

    def _build_suite_ctx(self) -> RuntimeContext:  # 构建 suite_ctx  #
        """_build_suite_ctx 方法  # 方法说明
        功能说明：将 env/static 注入 suite_ctx。  # 功能说明
        参数说明：无。  # 参数说明
        返回值说明：RuntimeContext。  # 返回值说明
        在系统中的作用：提供环境级变量与默认项。  # 系统作用
        调用关系：被 run_single/run_flow 调用。  # 调用关系
        """  # 方法说明结束  #
        ctx = RuntimeContext({})  # 创建空 ctx  #
        ctx.update(self.repo.config.env or {})  # 注入 env（host/request_options 等）  #
        ctx.update(self.repo.config.static or {})  # 注入 static（default_headers 等）  #
        return ctx  # 返回 ctx  #

    def _should_run_single(self, api_id: str, api_is_run: Optional[bool]) -> bool:  # 决策 single 是否执行  #
        """_should_run_single 方法  # 方法说明
        功能说明：根据 config.run_control 与 api.is_run 决策是否执行 single 用例。  # 功能说明
        参数说明：api_id/api_is_run。  # 参数说明
        返回值说明：bool。  # 返回值说明
        在系统中的作用：把运行控制收口到 executor 编排层。  # 系统作用
        调用关系：被 run_single 调用。  # 调用关系
        """  # 方法说明结束  #
        rc = self.repo.config.run_control or {}  # 读取 run_control  #
        global_is_run = rc.get("is_run", True)  # 全局开关  #
        only_apis = rc.get("only_apis", []) or []  # 白名单  #
        skip_apis = rc.get("skip_apis", []) or []  # 黑名单  #

        if api_is_run is not None:  # 若 api 显式写 is_run  #
            return bool(api_is_run)  # api 层最高优先级  #

        if only_apis:  # 若白名单非空  #
            return api_id in only_apis  # 仅执行白名单  #

        if api_id in skip_apis:  # 若在跳过列表  #
            return False  # 跳过  #

        return bool(global_is_run)  # 默认使用全局开关  #

    def _summary_text(self, resp: Response, limit: int = 500) -> str:  # 响应摘要  #
        """_summary_text 方法  # 方法说明
        功能说明：截断响应文本，避免结果对象过大。  # 功能说明
        参数说明：resp/limit。  # 参数说明
        返回值说明：str。  # 返回值说明
        在系统中的作用：提高结果可读性，便于日志/Allure 展示。  # 系统作用
        调用关系：被 run_single/run_flow 调用。  # 调用关系
        """  # 方法说明结束  #
        try:  # 捕获编码异常  #
            txt = resp.text or ""  # 取 text  #
            return txt[:limit]  # 截断返回  #
        except Exception:  # 若异常  #
            return "<response.text decode error>"  # 返回占位  #
