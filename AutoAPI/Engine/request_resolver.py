# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict, Optional

from Core.context import RuntimeContext
from Core.data_processing import render_any

from Engine.host_resolver import HostResolver
from Engine.results import PreparedRequest
from Exceptions.AutoApiException import build_api_exception_context, ExceptionCode, \
    RequestBuildException, VarResolveException
from Schema.data_models import EnvProfile, ExecutableCase, ExecutableStep


class RequestResolver:
    """
      作用:
        P0 请求解析器, 注入默认项 + 变量渲染 + host_rules 解析 + 输出 PreparedRequest。
    """
    def __init__(self):
        # P0 新模型统一通过 host_rules 解析 base_url。
        self.host_resolver = HostResolver()

    def resolve_executable(
        self,
        executable: ExecutableCase | ExecutableStep,
        request_defaults: Optional[Dict[str, Any]],
        ctx: RuntimeContext,
        env: EnvProfile,
        data_index: int = 0,
    ) -> PreparedRequest:
        """
          P0 新模型请求构建入口。

          新模型使用 request.path + env.host_rules，不再读取 request.host/url。
        """
        try:
            # 先复制全局默认请求参数，保证后续 update 不会修改 config 缓存。
            merged = dict(request_defaults or {})
            # 可执行对象的 request 覆盖默认值；这里是浅层覆盖，符合 P0 字段级覆盖结果。
            merged.update(executable.request or {})

            # 在 host 解析前完成变量渲染，确保 path/body/headers 中的 ${var} 都变成真实值。
            rendered = render_any(
                data=merged,
                ctx=ctx.snapshot(),
                path="request"
            )

            # P0 request 使用 path，不再使用旧结构中的 url/host 字段。
            path = rendered.get("path", "")
            # 根据 api_id、module、path 从当前环境的 host_rules 中解析 base_url。
            base_url = self.host_resolver.resolve_base_url(
                env,
                api_id=executable.api_id,
                module=(executable.api_meta or {}).get("module", ""),
                path=path,
            )
            # 统一去掉 base_url 尾部斜杠，再拼接以 / 开头的 path。
            full_url = base_url.rstrip("/") + path

            # kwargs 保存最终传给 requests/session.request 的附加参数。
            kwargs = {}
            # 这些字段会被单独处理，不能原样透传到 requests kwargs。
            reserved = {"method", "path", "body_type", "body", "params", "files"}
            # 遍历渲染后的请求字段，把非保留字段直接作为 requests 参数。
            for k, v in rendered.items():
                # method/path/body 等核心字段已有专门处理逻辑，因此跳过。
                if k in reserved:
                    continue
                # YAML 中 timeout 用 list 表达，requests 需要 tuple。
                if k == "timeout" and isinstance(v, list) and len(v) == 2:
                    kwargs["timeout"] = (v[0], v[1])
                    continue
                # headers、verify、allow_redirects 等其它字段原样透传。
                kwargs[k] = v

            # params/files/body 都支持 list 数据驱动，这里按 data_index 取当前条。
            params_item = self._pick_data_item(rendered.get("params"), data_index)
            files_item = self._pick_data_item(rendered.get("files"), data_index)
            body_item = self._pick_data_item(rendered.get("body"), data_index)

            # params 存在时放入 requests kwargs。
            if params_item is not None:
                kwargs["params"] = params_item
            # files 存在时放入 requests kwargs。
            if files_item is not None:
                kwargs["files"] = files_item
            # body 存在时根据 body_type 映射到 json 或 data。
            if body_item is not None:
                self._apply_body_by_type(rendered.get("body_type", ""), body_item, kwargs)

            # 返回执行器可直接发送的请求对象。
            return PreparedRequest(
                method=rendered.get("method"),
                url=full_url,
                kwargs=kwargs,
            )
        except VarResolveException:
            # 变量解析异常已经带有明确上下文，保持原异常向上抛。
            raise
        except Exception as e:
            # 其它异常统一包装为 P0 请求构建失败，并附带 request/env 快照。
            error_context = build_api_exception_context(
                error_code=ExceptionCode.REQUEST_BUILD_ERROR,
                message="P0 请求构建失败",
                reason=str(e),
                api_id=executable.api_id,
                step_id=getattr(executable, "step_id", None),
                request={
                    "request": executable.request,
                    "request_defaults": request_defaults,
                    "env_hosts": env.hosts,
                },
                hint="请检查 request、变量渲染和 host_rules 配置",
            )
            raise RequestBuildException(error_context) from e

    def _pick_data_item(self, data_node, data_index: int):
        """
          从 request.data 里选择要使用的那条数据（支持 list 或 dict 或 None）

        :param data_node: request数据节点(body/params/files)
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

    def _apply_body_by_type(self, body_type: str, body_item, kwargs: Dict[str, Any]):
        """
          根据 request_type 把 body_item 写入 json/data, 并存入kwargs
        :param body_type: 数据类型
        :param body_item: 数据
        :param kwargs: 待写入 kwargs
        """
        # json body 情况
        if body_type == "json":
            kwargs["json"] = body_item
            return
        # form body(data 情况)
        if body_type == "data":
            kwargs["data"] = body_item
            return
        # 未知类型
        raise ValueError("数据类型未知, 请检查")
