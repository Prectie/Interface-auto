# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List

from Core.context import RuntimeContext
from Core.repository import YamlRepository
from Engine.extractor import Extractor

from Engine.request_resolver import RequestResolver
from Engine.transport import TransportBase
from Exceptions.AutoApiException import build_api_exception_context, ExceptionPhase, ExceptionCode, PipelineException, \
    ExtractException


class AuthRunner:
    """
      config.yaml 里的 前置模板(auth_profiles.<name>.pre_apis) 执行器, 并把提取结果写入 ctx
    """
    def __init__(self, repo: YamlRepository, resolver: RequestResolver, extractor: Optional[Extractor] = None):
        # yaml 数据
        self.repo = repo

        # 请求数据解析器(整合完整的request请求数据)
        self.resolver = resolver

        # 提取器, 未传则新建
        self.extractor = extractor or Extractor()

    def run(
        self,
        profile_name: str,
        ctx: RuntimeContext,
        transport: TransportBase,
        env: Dict[str, Any],
        request_defaults: Dict[str, Any],
        where: str,
    ) -> Dict[str, Any]:
        """
          作用:
            - 按 order 执行指定 pre_apis
            - enabled=false 的 step 跳过
            - 执行 extract 写入 ctx

        :param profile_name: profile 名称
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

            # 若 config 数据为空, 则报错
            if cfg is None:
                # 构建明确异常上下文
                error_context = build_api_exception_context(
                    phase=ExceptionPhase.PIPELINE,
                    error_code=ExceptionCode.PIPELINE_ERROR,
                    message="前置接口执行失败",
                    reason="repository 未加载 config",
                    yaml_location=where,
                    hint="请先执行 repository.load() 再运行执行器"
                )
                raise PipelineException(error_context)

            # 取 auth_profiles, 允许为空
            profiles = cfg.auth_profiles or {}
            # 若 profile 不存在, 报错
            if profile_name not in profiles:
                # 构建明确异常上下文
                error_context = build_api_exception_context(
                    phase=ExceptionPhase.PIPELINE,
                    error_code=ExceptionCode.PIPELINE_ERROR,
                    message="需要调用的前置接口不存在",
                    reason=f"auth_profile 不存在：{profile_name}",
                    yaml_location=where,
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
                # 取 override.request
                override_request = override.get("request", {}) if isinstance(override, dict) else {}

                # 组装定位
                step_where = f"{where}.pre_apis.{step_name}"

                # 构建完整请求
                prepared = self.resolver.resolve(
                    api_request=api.request,
                    request_defaults=request_defaults,
                    override_request=override_request,
                    ctx=ctx,
                    env=env,
                    where=step_where,
                    api_id=ref,
                    step_name=step_name,
                )

                # 发送请求
                resp = transport.send(prepared)

                # 读取 auth step extract, 为 None 时设为 空list
                rules = step_body.get("extract", []) or []
                if rules:
                    # 将响应数据按提取规则, 存入 ctx 中
                    out = self.extractor.apply(rules=rules, response=resp, ctx=ctx, where=f"{step_where}.extract")
                    # 更新提取后的结果
                    extract_all.update(out)

            # 返回提取结果
            return extract_all

        # AuthProfileError情况直接抛出
        except (PipelineException, ExtractException):
            # 已结构化的异常直接抛出
            raise
        # 其他异常
        except Exception as e:
            # 构建明确异常上下文
            error_context = build_api_exception_context(
                phase=ExceptionPhase.PIPELINE,
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
