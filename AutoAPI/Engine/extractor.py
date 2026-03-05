# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict, List, Optional

from Engine.jsonpath_tool import JsonPathTool
from Exceptions.AutoApiException import build_api_exception_context, ExceptionPhase, ExceptionCode, ExtractException


class Extractor:
    """
      作用：
        提取器, 把响应内容按 extract 规则写入 ctx, 执行 extract 规则列表：
          - 从 response 的指定 source 读取数据（例如 response_json）
          - 用 jsonpath 提取值
          - 写入 ctx（key=as）
    """
    def __init__(self):
        # 创建 jsonpath 解析工具实例(内部维护 _jp_cache)
        self._jsonpath_toolkit = JsonPathTool()

    def apply(
            self,
            rules: List[Dict[str, Any]],
            response,
            ctx,
            where: str = "",
            api_id: Optional[str] = None,
            step_name: Optional[str] = None,
            request_snapshot: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
          作用：
            逐条执行 extract 规则，并把提取结果写入 ctx
        :param rules: extract 规则列表（每条必须包含 source/jsonpath/as）
        :param response: 响应对象（通常是 requests.Response）
        :param ctx: 运行时上下文对象（要求提供 set(key,value) 方法）
        :param where: 提取规则来源定位路径
        :param api_id: 接口 id
        :param step_name: 业务流单步 name
        :param request_snapshot: 请求数据快照
        :return: 本次提取出的变量字典 {as: value}
        """
        # 初始化输出结果
        out: Dict[str, Any] = {}
        # 遍历每条规则
        for i, rule in enumerate(rules, start=1):
            rule_where = f"{where}.extract[{i}]"
            try:
                # 读取 source、jsonpath、as
                source = rule["source"]
                expr = rule["jsonpath"]
                as_name = rule["as"]

                # 按 source 从响应数据中取数据载体
                response_payload = self._jsonpath_toolkit.read_source(source=source, response=response)
                # 执行 jsonpath 从 响应数据中 提取想要的数据
                value, matches = self._jsonpath_toolkit.extract_jsonpath(
                    response_payload=response_payload,
                    expr=expr,
                    where=rule_where
                )

                # 写入上下文（供后续 ${as_name} 渲染/断言使用）
                # 注: 这里写入的是在 响应数据中 找到的第一个匹配数据(比如找到了多个用户id, 这里只存入了第一个 用户id)
                ctx.set(as_name, value)
                # 写入输出结果（便于日志/Allure 附件）
                out[as_name] = value
            except Exception as e:
                # 构建明确异常上下文
                error_context = build_api_exception_context(
                    phase=ExceptionPhase.RESPONSE_EXTRACT,
                    error_code=ExceptionCode.RESPONSE_EXTRACT_ERROR,
                    message="响应数据提取失败",
                    reason=str(e),
                    yaml_where=rule_where,
                    api_id=api_id,
                    step_name=step_name,
                    request_snapshot=request_snapshot,
                    response_data=response,
                    rule=rule,
                    hint="请检查 source/jsonpath 是否正确, 或确认响应数据结构是否正确"
                )
                raise ExtractException(error_context) from e

        return out






