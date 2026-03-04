# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict, Optional

from Base.context import RuntimeContext
from Base.data_processing import deep_merge, render_any
from Exceptions.var_resolve_exception import VarResolveError

from Runtime.results import PreparedRequest
from Exceptions.runtime_exception import RequestBuildError, RuntimeErrorDetail


class RequestResolver:
    """
      作用:
        请求解析器, 合并 + 注入默认项 + 渲染 + 输出 prepared_request(完整请求数据)
        负责把 "ApiItem.request + override.request + env/static + ctx" 合成 prepared_request
    """
    def resolve(
        self,
        api_request: Dict[str, Any],
        request_defaults: Optional[Dict[str, Any]],
        override_request: Optional[Dict[str, Any]],
        ctx: RuntimeContext,
        env: Dict[str, Any],
        where: str,
        api_id: Optional[str] = None,
        step_name: Optional[str] = None,
        data_index: int = 0,
    ) -> PreparedRequest:
        """
          作用:
            - 合并 api_request 与 override_request
            - 合并注入config.yaml 里的 static.default_headers 与 env.request_options
            - 对最终 request 结构执行 render_any（展开 ${var}）
            - 将 request_type + data 映射为 requests 的 params/json/data/files
            - 输出 prepared_request 交给 transport 发送

        :param api_request: single.yaml 中 api 的 request dict
        :param request_defaults: config.yaml 里的 request_defaults, 请求默认值, 后续 api 请求数据带有默认值, 可被覆盖
        :param override_request: override.request dict（可为空, 一般来自 config 和 multiple 里的 ref）
        :param ctx: RuntimeContext, 运行时上下文, 用于变量渲染
        :param env: config 当前环境体
        :param where: 定位路径（用于错误提示）
        :param api_id: 用于结果/错误定位
        :param step_name: 用于结果/错误定位
        :param data_index: 当 request.data 为 list 时取第几条（默认取第 0 条）
        :return: 可直接交给 requests/session.request 的 PreparedRequest 对象
        """
        try:
            # 合并默认值 与 模板 api 的 request
            base = deep_merge(request_defaults or {}, api_request)
            # 合并 ref 引入的 override 和 已经合并过的 base
            merged = deep_merge(base, override_request or {})

            # 渲染变量, 按照 ctx 里的变量值替换成真实值
            rendered = render_any(data=merged, ctx=ctx.snapshot(), path=f"{where}.request")    #

            # 读取 method 并规范化为小写
            method = rendered.get("method")

            # 读取 url path, 若不存在则获取空串
            url_path = rendered.get("url", "")
            # 读取 host 并去掉末尾 /
            host = env.get("host", "").rstrip("/")
            full_url = f"{host}{url_path}"

            # 初始化 requests kwargs
            kwargs = {}
            # 定义已经处理好的字段
            reserved = {"method", "url", "request_type", "data"}
            # 遍历渲染后的 request 字段
            for k, v in rendered.items():
                # 若为已经处理好的字段, 则跳过
                if k in reserved:
                    continue
                # 处理 timeout 是元组的情况
                if k == "timeout" and isinstance(v, list) and len(v) == 2:
                    kwargs["timeout"] = (v[0], v[1])
                    continue
                # 剩下的字段直接存
                kwargs[k] = v

            # 读取 request_type, 允许不存在, 不存在时为空串
            request_type = rendered.get("request_type", "")
            # 读取 data（支持 list/dict/None）
            data_node = rendered.get("data", None)
            # 选择一条数据(默认选择第一条), 因为 pytest 收集机制会让每条测试函数只有一条 data 数据
            data_item = self._pick_data_item(data_node=data_node, data_index=data_index)
            # 若存在 data 数据, 则根据类型写入 kwargs
            if data_item is not None:
                self._apply_body_by_type(
                    request_type=request_type,
                    data_item=data_item,
                    kwargs=kwargs
                )

            # 构造 meta 信息, 方便报错/日志
            meta = {
                "where": where,
                "api_id": api_id,
                "step_name": step_name,
            }
            # 返回整理好的 prepared_request
            return PreparedRequest(method=method, url=full_url, kwargs=kwargs, meta=meta)
        # 捕获变量渲染失败的情况
        except VarResolveError as e:
            detail = RuntimeErrorDetail(
                where=where,
                api_id=api_id,
                step_name=step_name,
                message="请求渲染失败（变量未解析）",
                extra=str(e)
            )
            raise RequestBuildError(detail) from e
        # 捕获其他请求构建异常
        except Exception as e:
            detail = RuntimeErrorDetail(
                where=where,
                api_id=api_id,
                step_name=step_name,
                message="请求构建失败",
                extra=str(e)
            )
            raise RequestBuildError(detail) from e

    def _pick_data_item(self, data_node, data_index: int):
        """
          从 request.data 里选择要使用的那条数据（支持 list 或 dict 或 None）

        :param data_node: request.data
        :param data_index: 当 data_node 是 list 时选择第几条
        :return: 返回选中的数据对象（dict/None/其他）
        """
        # 若 data_node 不存在, 返回 None
        if data_node is None:
            return None
        # 若 data_node 是 dict, 直接返回
        if isinstance(data_node, dict):
            return data_node
        # 若 data_node 是 list
        if isinstance(data_node, list):
            # 若 list 为空, 返回 None
            if not data_node:
                return None
            # 防止越界, 越界情况默认选择 data[0]
            idx = data_index if 0 <= data_index < len(data_node) else 0
            return data_node[idx]
        # 其他类型原样返回
        return data_node

    def _apply_body_by_type(self, request_type: str, data_item, kwargs: Dict[str, Any]):
        """
          根据 request_type 把 data_item 写入 params/json/data/files, 并存入kwargs
        :param request_type: 数据类型
        :param data_item: 数据
        :param kwargs: 待写入 kwargs
        """
        # params 情况
        if request_type == "params":
            kwargs["params"] = data_item
            return
        # json body 情况
        if request_type == "json":
            kwargs["json"] = data_item
            return
        # form body(data 情况)
        if request_type == "data":
            kwargs["data"] = data_item
            return
        # # 文件上传情况
        if request_type == "file":
            kwargs["files"] = data_item
            return
        # 未知类型
        raise ValueError("数据类型未知, 请检查")
