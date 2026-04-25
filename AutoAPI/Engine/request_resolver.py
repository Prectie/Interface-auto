# -*- coding: utf-8 -*-

from __future__ import annotations

import mimetypes
import re
from base64 import b64encode
from pathlib import Path
from typing import Any, Dict, Optional

from Core.context import RuntimeContext
from Core.data_processing import render_any

from Engine.host_resolver import HostResolver
from Engine.results import PreparedRequest
from Exceptions.AutoApiException import build_api_exception_context, ExceptionCode, \
    RequestBuildException, VarResolveException
from Schema.data_models import EnvProfile, ExecutableCase, ExecutableStep

RAW_CONTENT_TYPES = {
    "text": "text/plain",
    "xml": "application/xml",
    "html": "text/html",
    "javascript": "application/javascript",
}


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

            # path 先按 path_params 渲染为最终路径，再参与 host_rules 路由和 URL 拼接。
            path = self._render_path_with_params(
                rendered.get("path", ""),
                rendered.get("path_params"),
            )
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
            reserved = {
                "method",
                "path",
                "path_params",
                "query",
                "cookies",
                "auth",
                "body_mode",
                "raw",
                "form_urlencoded",
                "form_data",
                "binary",
            }
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

            # query 是新的正式 URL 查询参数输入，最终仍映射到 requests 的 params。
            query_item = self._pick_data_item(rendered.get("query"), data_index)
            if query_item is not None:
                kwargs["params"] = query_item

            # cookies 是正式独立输入，不再依赖 headers.Cookie。
            cookies_item = self._pick_data_item(rendered.get("cookies"), data_index)
            if cookies_item is not None:
                kwargs["cookies"] = cookies_item

            # auth 属于语义化输入，需要翻译到 headers / params / cookies。
            self._apply_auth(rendered.get("auth"), kwargs)

            # raw(json) 是当前第一阶段正式支持的请求体模式。
            self._apply_body_by_mode(rendered, kwargs, data_index)

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
          从请求字段节点里选择当前要使用的数据（支持 list 或 dict 或 None）

        :param data_node: 请求字段节点，例如 query/raw/form_urlencoded/binary
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

    def _apply_body_by_mode(self, rendered: Dict[str, Any], kwargs: Dict[str, Any], data_index: int) -> None:
        """
          根据 body_mode 把请求体映射到 requests kwargs。
        """
        body_mode = rendered.get("body_mode")
        if not body_mode or body_mode == "none":
            return

        if body_mode == "form_urlencoded":
            body_item = self._pick_data_item(rendered.get("form_urlencoded"), data_index)
            if body_item is not None:
                kwargs["data"] = body_item
            return

        if body_mode == "form_data":
            # form_data 本身就是 multipart item 列表，不能按“数据驱动列表”再取第 0 项。
            form_item = rendered.get("form_data")
            if form_item is not None:
                kwargs["files"] = self._build_multipart_files(form_item)
            return

        if body_mode == "binary":
            binary_item = self._pick_data_item(rendered.get("binary"), data_index)
            if binary_item is not None:
                self._apply_binary(binary_item, kwargs)
            return

        # 第一阶段先从 raw(json) 起步，第二阶段继续支持 form 类请求。
        if body_mode == "raw":
            raw_node = self._pick_data_item(rendered.get("raw"), data_index)
            if raw_node is None:
                return
            raw_type = raw_node.get("raw_type") if isinstance(raw_node, dict) else None
            content = raw_node.get("content") if isinstance(raw_node, dict) else None
            if raw_type == "json":
                kwargs["json"] = content
                return
            if raw_type in RAW_CONTENT_TYPES:
                kwargs["data"] = content if isinstance(content, str) else str(content)
                headers = self._ensure_mapping(kwargs, "headers")
                headers.setdefault("Content-Type", RAW_CONTENT_TYPES[raw_type])
                return
            raise ValueError(f"当前阶段不支持 raw.raw_type: {raw_type}")

        raise ValueError(f"当前阶段暂不支持 body_mode: {body_mode}")

    def _apply_auth(self, auth_node: Any, kwargs: Dict[str, Any]) -> None:
        """
          将语义化 auth 配置翻译成 requests 可接受的 headers / params / cookies。
        """
        if not auth_node:
            return
        if not isinstance(auth_node, dict):
            raise ValueError("auth 必须是对象")

        auth_type = auth_node.get("type", "none")
        if auth_type == "none":
            return

        if auth_type == "bearer":
            token = auth_node.get("token")
            if token in (None, ""):
                raise ValueError("bearer auth 缺少 token")
            headers = self._ensure_mapping(kwargs, "headers")
            headers["Authorization"] = f"Bearer {token}"
            return

        if auth_type == "basic":
            username = auth_node.get("username")
            password = auth_node.get("password")
            if username is None or password is None:
                raise ValueError("basic auth 缺少 username 或 password")
            raw_value = f"{username}:{password}".encode("utf-8")
            headers = self._ensure_mapping(kwargs, "headers")
            headers["Authorization"] = f"Basic {b64encode(raw_value).decode('ascii')}"
            return

        if auth_type == "api_key":
            target = auth_node.get("in")
            key = auth_node.get("key")
            value = auth_node.get("value")
            if not target or not key:
                raise ValueError("api_key auth 缺少 in 或 key")
            if value is None:
                raise ValueError("api_key auth 缺少 value")

            if target == "header":
                headers = self._ensure_mapping(kwargs, "headers")
                headers[str(key)] = value
                return
            if target == "query":
                params = self._ensure_mapping(kwargs, "params")
                params[str(key)] = value
                return
            if target == "cookie":
                cookies = self._ensure_mapping(kwargs, "cookies")
                cookies[str(key)] = value
                return
            raise ValueError(f"未知 api_key.in: {target}")

        raise ValueError(f"未知 auth.type: {auth_type}")

    def _build_multipart_files(self, form_items: Any) -> list[tuple[str, tuple]]:
        """
          将 form_data 标准结构转换成 requests 可接受的 multipart files 列表。
        """
        if not isinstance(form_items, list):
            raise ValueError("form_data 必须是列表")

        multipart_files: list[tuple[str, tuple]] = []
        for item in form_items:
            if not isinstance(item, dict):
                raise ValueError("form_data 项必须是对象")

            kind = item.get("kind")
            name = item.get("name")
            if not name:
                raise ValueError("form_data 项缺少 name")

            if kind == "field":
                value = item.get("value", "")
                multipart_files.append((str(name), (None, str(value))))
                continue

            if kind == "file":
                multipart_files.append((str(name), self._build_file_part(item)))
                continue

            raise ValueError(f"未知 form_data.kind: {kind}")

        return multipart_files

    def _build_file_part(self, item: Dict[str, Any]) -> tuple:
        """
          将单个 file item 转换成 requests multipart tuple。
        """
        raw_path = item.get("path")
        if not raw_path:
            raise ValueError("form_data file 项缺少 path")

        file_path = Path(str(raw_path))
        if not file_path.exists() or not file_path.is_file():
            raise ValueError(f"form_data file 路径不存在: {file_path}")

        filename = file_path.name
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        content = file_path.read_bytes()
        return filename, content, content_type

    def _apply_binary(self, binary_item: Any, kwargs: Dict[str, Any]) -> None:
        """
          将 binary 请求体转换成 requests 的 data bytes。
        """
        if not isinstance(binary_item, dict):
            raise ValueError("binary 必须是对象")

        source = binary_item.get("source")
        if source != "path":
            raise ValueError(f"当前阶段仅支持 binary source=path，实际为: {source}")

        raw_path = binary_item.get("path")
        if not raw_path:
            raise ValueError("binary 缺少 path")

        file_path = Path(str(raw_path))
        if not file_path.exists() or not file_path.is_file():
            raise ValueError(f"binary 路径不存在: {file_path}")

        content = file_path.read_bytes()
        kwargs["data"] = content

        content_type = binary_item.get("content_type") or mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        headers = self._ensure_mapping(kwargs, "headers")
        headers.setdefault("Content-Type", content_type)

    def _ensure_mapping(self, kwargs: Dict[str, Any], key: str) -> Dict[str, Any]:
        """
          确保 kwargs[key] 是 dict，并返回可直接写入的映射对象。
        """
        value = kwargs.get(key)
        if value is None:
            kwargs[key] = {}
            return kwargs[key]
        if not isinstance(value, dict):
            raise ValueError(f"{key} 必须是对象")
        return value

    def _render_path_with_params(self, path: str, path_params: Optional[Dict[str, Any]]) -> str:
        """
          将 /path/{id} 这种模板路径替换成最终可请求的 path。
        """
        if not path:
            return path

        path_params = path_params or {}

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in path_params:
                raise KeyError(f"path_params 缺少字段: {key}")
            value = path_params[key]
            if value is None:
                raise ValueError(f"path_params 字段值为空: {key}")
            return str(value)

        return re.sub(r"\{([^{}]+)\}", replace, path)
