# -*- coding: utf-8 -*-  # 声明源码编码，避免中文注释乱码  #

from __future__ import annotations  # 允许前向引用类型注解  #

from typing import Any, Dict, Optional, Tuple, List  # 导入类型注解  #

from Base.context import RuntimeContext  # 导入运行时上下文  #
from Base.repository import YamlRepository  # 导入仓库  #
from Base.extractor import Extractor, extract_error  # 导入提取器与提取异常  #

from Runtime.request_resolver import RequestResolver  # 导入请求解析器  #
from Runtime.transport import TransportBase  # 导入传输层抽象  #
from Runtime.runtime_exception import AuthProfileError, RuntimeErrorDetail, ResponseProcessError  # 导入鉴权异常  #


class AuthRunner:  # 鉴权 runner（执行 auth_profiles.<name>.pre_apis）  #
    """auth_runner 类实现  # 类说明
    auth_runner 负责执行鉴权前置接口链，并把提取结果写入 ctx（典型 token）。  # 类职责说明
    """  # 类说明结束  #

    def __init__(self, repo: YamlRepository, resolver: RequestResolver, extractor: Optional[Extractor] = None):  # 初始化  #
        self.repo = repo  # 保存 repo  #
        self.resolver = resolver  # 保存 resolver  #
        self.extractor = extractor or Extractor()  # 保存 extractor（未传则新建）  #

    def run(  # 执行指定 profile  #
        self,  # self 说明  #
        profile_name: str,  # profile 名称  #
        ctx: RuntimeContext,  # 上下文（写入 token 等）  #
        transport: TransportBase,  # 发包器（single 用 requests，flow 用 session）  #
        env: Dict[str, Any],  # env 当前环境体  #
        static: Dict[str, Any],  # static 静态配置  #
        where: str,  # 定位字符串  #
    ) -> Dict[str, Any]:  # 返回聚合的 extract_out  #
        """run 方法  # 方法说明
        功能说明：按 order 执行 pre_apis；enabled=false 的 step 跳过；执行 extract 写入 ctx。  # 功能说明
        参数说明：profile_name/ctx/transport/env/static/where。  # 参数说明
        返回值说明：聚合的提取结果 dict。  # 返回值说明
        在系统中的作用：把鉴权链与主执行流程解耦。  # 系统作用
        调用关系：被 executor.run_single/run_flow 调用。  # 调用关系
        """  # 方法说明结束  #
        try:  # 捕获鉴权链异常  #
            cfg = self.repo.config  # 取 config bundle  #
            if cfg is None:  # 若 repo 未 load  #
                raise Exception("repository 未加载 config")  # 抛错  #
            profiles = cfg.auth_profiles or {}  # 取 auth_profiles  #
            if profile_name not in profiles:  # 若 profile 不存在  #
                detail = RuntimeErrorDetail(where=where, message=f"auth_profile 不存在：{profile_name}", extra=list(profiles.keys()))  # 构造 detail  #
                raise AuthProfileError(detail)  # 抛出统一异常  #

            profile = profiles[profile_name]  # 取 profile 体  #
            pre_apis = profile.get("pre_apis", {})  # 取 pre_apis  #
            steps = self._sort_steps(pre_apis)  # 排序步骤  #

            extract_all: Dict[str, Any] = {}  # 聚合提取结果  #

            for step_name, step_body in steps:  # 遍历每个 step  #
                enabled = bool(step_body.get("enabled", False))  # 读取 enabled  #
                if not enabled:  # 若 disabled  #
                    continue  # 跳过该 step（你要求 enabled=false 表示不执行）  #

                ref = str(step_body.get("ref", "")).strip()  # 读取 ref  #
                api = self.repo.get_api(ref)  # 从接口库取模板  #

                override = step_body.get("override", {}) or {}  # 读取 override  #
                override_request = override.get("request", {}) if isinstance(override, dict) else {}  # 取 override.request  #

                step_where = f"{where}.pre_apis.{step_name}"  # 组装定位  #
                prepared = self.resolver.resolve(  # 构建请求  #
                    api_request=api.request,  # 模板 request  #
                    override_request=override_request,  # 覆盖 request  #
                    ctx=ctx,  # 上下文  #
                    env=env,  # env  #
                    static=static,  # static  #
                    where=step_where,  # 定位  #
                    api_id=ref,  # api_id  #
                    step_name=step_name,  # step_name  #
                )  # resolve 调用结束  #

                resp = transport.send(prepared)  # 发送请求  #

                rules = step_body.get("extract", []) or []  # 读取 auth step extract  #
                if rules:  # 若存在规则  #
                    out = self.extractor.apply(rules=rules, response=resp, ctx=ctx, where=f"{step_where}.extract")  # 执行提取  #
                    extract_all.update(out)  # 聚合结果  #

            return extract_all  # 返回聚合提取结果  #
        except AuthProfileError:  # 若已是统一异常  #
            raise  # 直接抛出  #
        except extract_error as e:  # 提取失败  #
            detail = RuntimeErrorDetail(where=where, message="鉴权链提取失败", extra=str(e))  # 构造 detail  #
            raise ResponseProcessError(detail) from e  # 抛出响应处理异常  #
        except Exception as e:  # 其他异常  #
            detail = RuntimeErrorDetail(where=where, message="鉴权链执行失败", extra=str(e))  # 构造 detail  #
            raise AuthProfileError(detail) from e  # 抛出鉴权异常  #

    def _sort_steps(self, pre_apis: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:  # 对 pre_apis 排序  #
        """_sort_steps 方法  # 方法说明
        功能说明：把 dict 的 pre_apis 转为 list 并按 order 升序排序。  # 功能说明
        参数说明：pre_apis：dict。  # 参数说明
        返回值说明：List[(step_name, step_body)]。  # 返回值说明
        在系统中的作用：确保鉴权链按配置顺序执行。  # 系统作用
        调用关系：被 run 调用。  # 调用关系
        """  # 方法说明结束  #
        items: List[Tuple[str, Dict[str, Any]]] = []  # 初始化 items  #
        for name, body in pre_apis.items():  # 遍历 dict  #
            if isinstance(body, dict):  # 仅保留 dict  #
                items.append((name, body))  # 加入 items  #
        items.sort(key=lambda x: int(x[1].get("order", 0) or 0))  # 按 order 排序  #
        return items  # 返回排序结果  #
