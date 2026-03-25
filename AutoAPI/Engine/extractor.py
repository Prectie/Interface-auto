# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict, List, Optional

from requests import Response

from Engine.jsonpath_tool import JsonPathTool
from Exceptions.AutoApiException import build_api_exception_context, ExceptionCode, ExtractException


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
        response: Response,
        ctx,
        *,
        api_id: Optional[str] = None,
        flow_file: Optional[str] = None,
        step_id: Optional[str] = None,
        profile_name: Optional[str] = None,
        yaml_file: Optional[str] = None,
        request: Optional[Dict[str, Any]] = None,
        trace_collector: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
          作用：
            逐条执行 extract 规则，并把提取结果写入 ctx
        :param rules: extract 规则列表（每条必须包含 source/jsonpath/as）
        :param response: 响应对象（通常是 requests.Response）
        :param ctx: 运行时上下文对象（要求提供 set(key,value) 方法）
        :param api_id: 接口库的接口id
        :param flow_file: 业务流文件
        :param step_id: 业务流的步骤名称
        :param profile_name: 前置接口名称
        :param yaml_file: 当前错误应归属于哪个 yaml 文件
        :param request: 请求数据快照
        :param trace_collector: 提取执行轨迹收集列表
        :return: 本次提取出的变量字典 {as: value}
        """
        # 初始化输出结果
        out: Dict[str, Any] = {}
        # 遍历每条规则
        for i, rule in enumerate(rules, start=1):
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
                )

                # 写入上下文（供后续 ${as_name} 渲染/断言使用）
                # 注: 这里写入的是在 响应数据中 找到的第一个匹配数据(比如找到了多个用户id, 这里只存入了第一个 用户id)
                ctx.set(as_name, value)
                # 写入输出结果（便于日志/Allure 附件）
                out[as_name] = value

                if trace_collector is not None:
                    trace_collector.append(
                        {
                            "当前提取规则序号": i,
                            "当前提取规则": rule,
                            "当前提取源": source,
                            "当前提取表达式": expr,
                            "写入变量名": as_name,
                            "首个命中值": value,
                            "全部命中值": matches
                        }
                    )
            except Exception as e:
                # 构建明确异常上下文
                error_context = build_api_exception_context(
                    error_code=ExceptionCode.RESPONSE_EXTRACT_ERROR,
                    message="响应数据提取失败",
                    reason=e,
                    yaml_file=yaml_file,
                    flow_file=flow_file,
                    api_id=api_id,
                    step_id=step_id,
                    profile_name=profile_name,
                    request=request,
                    response=response,
                    hint="请检查 source/jsonpath 是否正确, 或确认响应数据结构是否正确",
                    extra={"extract_rule_index": i, "extract_rule": rule}
                )
                raise ExtractException(error_context) from e

        return out






