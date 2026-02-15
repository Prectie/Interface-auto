# -*- coding: utf-8 -*-  # 声明源码编码，避免中文注释乱码  #

from __future__ import annotations  # 允许前向引用类型注解  #

from typing import Any, Dict, Optional, Mapping  # 导入类型注解  #

from Base.context import RuntimeContext  # 导入运行时上下文  #
from Base.data_processing import deep_merge, render_any, var_resolve_error  # 导入合并/渲染/变量解析异常  #

from Runtime.results import PreparedRequest  # 导入 prepared_request  #
from Runtime.runtime_exception import RequestBuildError, RuntimeErrorDetail  # 导入请求构建异常与详情  #


class RequestResolver:  # 请求解析器（合并 + 注入默认项 + 渲染 + 输出 prepared_request）  #
    """request_resolver 类实现  # 类说明
    request_resolver 负责把“ApiItem.request + override.request + env/static + ctx”合成 prepared_request。  # 类职责说明

    1. 类变量说明  # 模板：类变量说明
        1) 无强制类变量；本类主要提供 resolve 方法。  # 变量说明
    """  # 类说明结束  #

    def resolve(  # 解析入口  #
        self,  # self 说明  #
        api_request: Dict[str, Any],  # 接口模板 request  #
        override_request: Optional[Dict[str, Any]],  # 覆盖 request  #
        ctx: RuntimeContext,  # 运行时上下文  #
        env: Dict[str, Any],  # 当前环境配置（host/request_options）  #
        static: Dict[str, Any],  # 静态配置（default_headers）  #
        where: str,  # 定位字符串  #
        api_id: Optional[str] = None,  # api_id（可选）  #
        step_name: Optional[str] = None,  # step_name（可选）  #
        data_index: int = 0,  # data list 的选择索引（默认取第 0 条）  #
    ) -> PreparedRequest:  # 返回 prepared_request  #
        """resolve 方法  # 方法说明
        功能说明：  # 功能说明
            1) 深合并 api_request 与 override_request；  # 功能点
            2) 合并注入 static.default_headers 与 env.request_options；  # 功能点
            3) 对最终 request 结构执行 render_any（展开 ${var}）；  # 功能点
            4) 将 request_type + data 映射为 requests 的 params/json/data/files；  # 功能点
            5) 输出 prepared_request 交给 transport 发送。  # 功能点
        参数说明：  # 参数说明
            1) api_request：single.yaml 中 api 的 request dict；  # 参数说明
            2) override_request：override.request dict（可为空）；  # 参数说明
            3) ctx：RuntimeContext，用于变量渲染；  # 参数说明
            4) env：config 当前环境体（至少包含 host/request_options）；  # 参数说明
            5) static：config.static（至少包含 default_headers）；  # 参数说明
            6) where：定位字符串（用于错误提示）；  # 参数说明
            7) api_id/step_name：用于结果/错误定位；  # 参数说明
            8) data_index：当 request.data 为 list 时取第几条。  # 参数说明
        返回值说明：  # 返回值说明
            1) prepared_request：可直接交给 requests/session.request 的对象。  # 返回值说明
        在系统中的作用：  # 系统作用
            将“配置数据”转换成“可执行请求”，承接 data_processing 与 transport 的边界。  # 系统作用
        调用关系：  # 调用关系
            1) 被 executor.run_single/run_flow 调用；  # 调用关系
            2) 被 auth_runner.run 调用构建鉴权 pre_api 请求；  # 调用关系
            3) 内部调用 deep_merge/render_any 完成合并与渲染。  # 调用关系
        """  # 方法说明结束  #
        try:  # 捕获构建阶段异常并转为 request_build_error  #
            merged = deep_merge(api_request, override_request or {})  # 合并 request（override 优先）  #

            merged = self._inject_default_headers(merged=merged, static=static)  # 注入默认 headers  #
            merged = self._inject_default_options(merged=merged, env=env)  # 注入默认 options  #

            rendered = render_any(data=merged, ctx=ctx.snapshot(), path=f"{where}.request")  # 渲染变量（${token}）  #

            method = str(rendered.get("method", "")).strip().lower()  # 读取 method 并规范化为小写  #
            url_path = str(rendered.get("url", "")).strip()  # 读取 url path  #
            host = str(env.get("host", "")).rstrip("/")  # 读取 host 并去掉末尾 /  #
            full_url = f"{host}{url_path}"  # 拼接完整 url  #

            kwargs: Dict[str, Any] = {}  # 初始化 requests kwargs  #

            headers = rendered.get("headers", None)  # 读取 headers  #
            if isinstance(headers, dict):  # 若 headers 为 dict  #
                kwargs["headers"] = headers  # 写入 kwargs.headers  #

            explicit_params = rendered.get("params", None)  # 读取显式 params（可选扩展）  #
            if isinstance(explicit_params, dict):  # 若显式 params 存在  #
                kwargs["params"] = explicit_params  # 写入 kwargs.params  #

            options = rendered.get("options", None)  # 读取 options  #
            if isinstance(options, dict):  # 若 options 为 dict  #
                self._apply_options_into_kwargs(options=options, kwargs=kwargs)  # 把 options 展开到 kwargs  #

            request_type = str(rendered.get("request_type", "")).strip().lower()  # 读取 request_type  #
            data_node = rendered.get("data", None)  # 读取 data（支持 list/dict/None）  #
            data_item = self._pick_data_item(data_node=data_node, data_index=data_index)  # 选择一条数据  #

            if data_item is not None:  # 若存在 data_item  #
                self._apply_body_by_type(request_type=request_type, data_item=data_item, kwargs=kwargs)  # 根据类型写入 kwargs  #

            meta = {  # 构造 meta 信息  #
                "where": where,  # 记录 where  #
                "api_id": api_id,  # 记录 api_id  #
                "step_name": step_name,  # 记录 step_name  #
            }  # meta 构造结束  #

            return PreparedRequest(method=method, url=full_url, kwargs=kwargs, meta=meta)  # 返回 prepared_request  #
        except var_resolve_error as e:  # 捕获变量渲染失败（缺变量）  #
            detail = RuntimeErrorDetail(where=where, api_id=api_id, step_name=step_name, message="请求渲染失败（变量未解析）", extra=str(e))  # 构造 detail  #
            raise RequestBuildError(detail) from e  # 抛出统一异常  #
        except Exception as e:  # 捕获其他请求构建异常  #
            detail = RuntimeErrorDetail(where=where, api_id=api_id, step_name=step_name, message="请求构建失败", extra=str(e))  # 构造 detail  #
            raise RequestBuildError(detail) from e  # 抛出统一异常  #

    def _inject_default_headers(self, merged: Dict[str, Any], static: Dict[str, Any]) -> Dict[str, Any]:  # 注入默认 headers  #
        """_inject_default_headers 方法  # 方法说明
        功能说明：合并 static.default_headers 与 request.headers（request 优先）。  # 功能说明
        参数说明：merged：当前 request dict；static：config.static。  # 参数说明
        返回值说明：返回合并后的 request dict（新对象）。  # 返回值说明
        在系统中的作用：把默认 header 收口在 resolver。  # 系统作用
        调用关系：被 resolve 调用。  # 调用关系
        """  # 方法说明结束  #
        default_headers = static.get("default_headers", {})  # 读取 default_headers  #
        req_headers = merged.get("headers", {})  # 读取 request.headers  #
        if req_headers is None:  # 允许 null  #
            req_headers = {}  # 转空 dict  #
        if not isinstance(default_headers, dict):  # 若 default_headers 不是 dict  #
            default_headers = {}  # 兜底为空 dict（不做校验，避免崩）  #
        if not isinstance(req_headers, dict):  # 若 req_headers 不是 dict  #
            req_headers = {}  # 兜底为空 dict  #
        merged2 = deep_merge(merged, {})  # 深拷贝 merged（避免原对象被污染）  #
        merged2["headers"] = deep_merge(default_headers, req_headers)  # 合并 headers（request 优先）  #
        return merged2  # 返回合并结果  #

    def _inject_default_options(self, merged: Dict[str, Any], env: Dict[str, Any]) -> Dict[str, Any]:  # 注入默认 options  #
        """_inject_default_options 方法  # 方法说明
        功能说明：合并 env.request_options 与 request.options（request 优先）。  # 功能说明
        参数说明：merged：当前 request dict；env：当前环境体。  # 参数说明
        返回值说明：返回合并后的 request dict（新对象）。  # 返回值说明
        在系统中的作用：把 requests 公共参数收口在 resolver。  # 系统作用
        调用关系：被 resolve 调用。  # 调用关系
        """  # 方法说明结束  #
        default_options = env.get("request_options", {})  # 读取 env.request_options  #
        req_options = merged.get("options", {})  # 读取 request.options  #
        if req_options is None:  # 允许 null  #
            req_options = {}  # 转空 dict  #
        if not isinstance(default_options, dict):  # 若 default_options 不是 dict  #
            default_options = {}  # 兜底为空 dict  #
        if not isinstance(req_options, dict):  # 若 req_options 不是 dict  #
            req_options = {}  # 兜底为空 dict  #
        merged2 = deep_merge(merged, {})  # 深拷贝 merged  #
        merged2["options"] = deep_merge(default_options, req_options)  # 合并 options（request 优先）  #
        return merged2  # 返回合并结果  #

    def _apply_options_into_kwargs(self, options: Dict[str, Any], kwargs: Dict[str, Any]) -> None:  # 展开 options 到 kwargs  #
        """_apply_options_into_kwargs 方法  # 方法说明
        功能说明：把 options 中的键值展开为 requests kwargs（含 cookies/auth/timeout 等）。  # 功能说明
        参数说明：options：合并后的 options dict；kwargs：待写入的 kwargs。  # 参数说明
        返回值说明：无（原地写入 kwargs）。  # 返回值说明
        在系统中的作用：把 options 统一转换为 transport 可直接使用的 kwargs。  # 系统作用
        调用关系：被 resolve 调用。  # 调用关系
        """  # 方法说明结束  #
        for k, v in options.items():  # 遍历 options 键值  #
            if k == "timeout" and isinstance(v, list) and len(v) == 2:  # 若 timeout 是 [connect, read]  #
                kwargs["timeout"] = (v[0], v[1])  # 转为 tuple（requests 推荐）  #
                continue  # 结束本次循环  #
            kwargs[k] = v  # 其他项原样写入 kwargs（不做校验）  #

        if "cookies" in kwargs and kwargs["cookies"] is None:  # 若 cookies 显式为 None  #
            kwargs.pop("cookies", None)  # 移除 cookies，避免 requests 处理异常  #

    def _pick_data_item(self, data_node: Any, data_index: int) -> Any:  # 从 request.data 中选一条数据  #
        """_pick_data_item 方法  # 方法说明
        功能说明：从 request.data 里选择要使用的那条数据（支持 list 或 dict 或 None）。  # 功能说明
        参数说明：  # 参数说明
            1) data_node：request.data（可能是 list/dict/None）；  # 参数说明
            2) data_index：当 data_node 是 list 时选择第几条。  # 参数说明
        返回值说明：  # 返回值说明
            1) 返回选中的数据对象（dict/None/其他）。  # 返回值说明
        在系统中的作用：  # 系统作用
            统一 data 入口，支持你“一个用例一条 data”的原则，同时保留后续扩展空间。  # 系统作用
        调用关系：被 resolve 调用。  # 调用关系
        """  # 方法说明结束  #
        if data_node is None:  # 若 data_node 不存在  #
            return None  # 直接返回 None  #
        if isinstance(data_node, dict):  # 若 data_node 是 dict  #
            return data_node  # 直接返回 dict  #
        if isinstance(data_node, list):  # 若 data_node 是 list  #
            if not data_node:  # 若 list 为空  #
                return None  # 返回 None  #
            idx = data_index if 0 <= data_index < len(data_node) else 0  # 防止越界（不做校验，只做保底选择）  #
            return data_node[idx]  # 返回选中项  #
        return data_node  # 其他类型原样返回（保持灵活）  #

    def _apply_body_by_type(self, request_type: str, data_item: Any, kwargs: Dict[str, Any]) -> None:  # 根据 request_type 写入 kwargs  #
        """_apply_body_by_type 方法  # 方法说明
        功能说明：根据 request_type，把 data_item 写入 params/json/data/files。  # 功能说明
        参数说明：request_type：请求类型；data_item：请求数据；kwargs：待写入 kwargs。  # 参数说明
        返回值说明：无（原地写入 kwargs）。  # 返回值说明
        在系统中的作用：统一你的 YAML 请求描述到 requests 参数映射规则。  # 系统作用
        调用关系：被 resolve 调用。  # 调用关系
        """  # 方法说明结束  #
        if request_type == "params":  # query 参数  #
            kwargs["params"] = data_item  # 写入 params  #
            return  # 返回  #
        if request_type == "json":  # json body  #
            kwargs["json"] = data_item  # 写入 json  #
            return  # 返回  #
        if request_type == "data":  # form body  #
            kwargs["data"] = data_item  # 写入 data  #
            return  # 返回  #
        if request_type == "file":  # 文件上传  #
            kwargs["files"] = data_item  # 写入 files（按 requests 约定）  #
            return  # 返回  #
        # 未知类型：不做校验，直接不写 body（把错误留给请求/后续 schema 完善）  #
        return  # 结束  #
