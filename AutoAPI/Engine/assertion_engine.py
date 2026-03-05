# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from requests import Response

from Core.context import RuntimeContext
from Core.data_processing import render_any
from Engine.jsonpath_tool import JsonPathTool

from Engine.results import AssertionResult
from Exceptions.AutoApiException import build_api_exception_context, ExceptionPhase, ExceptionCode, AssertException


class AssertionEngine:
    """
      该模块负责执行断言, 具体为 YAML 里的 assertions：source/jsonpath/op/expected
    """

    def __init__(self):
        # 创建 jsonpath 解析工具实例(内部维护 _jp_cache)
        self._jsonpath_toolkit = JsonPathTool()

    def assert_all(
        self,
        assertions: Optional[List[Dict[str, Any]]],
        response: Response,
        ctx: RuntimeContext,
        where: str,
        api_id: Optional[str] = None,
        step_name: Optional[str] = None,
        request_snapshot: Optional[Dict[str, Any]] = None
    ) -> List[AssertionResult]:
        """
          逐条执行断言并返回结果列表
        :param assertions: 断言规则列表
        :param response: 响应对象
        :param ctx: 上下文（用于 expected 渲染）
        :param where: assertions 定位路径
        :param api_id: 接口 id
        :param step_name: 业务流单步 step 名称
        :param request_snapshot: 请求数据快照
        :return: 返回断言结果列表
        """
        # 若无断言, 返回空结果
        if not assertions:
            return []

        # 初始化结果列表
        results: List[AssertionResult] = []

        # 遍历每条断言
        for i, rule in enumerate(assertions, start=1):
            # 构造规则定位
            rule_where = f"{where}.assertions[{i}]"
            try:
                # 读取 source、jsonpath、op、expected
                source = rule["source"]
                expr = rule["jsonpath"]
                op = rule["op"]
                # 允许为 None 值(在断言字段存在时)
                expected_raw = rule.get("expected", None)

                # 渲染 expected（允许 ${var}）, 存在断言数据依赖 extract 的提取结果, 比如 {user_id}
                expected = render_any(data=expected_raw, ctx=ctx.snapshot(), path=f"{rule_where}.expected")

                # 按 source 从响应数据中取数据载体
                payload = self._jsonpath_toolkit.read_source(source=source, response=response)

                # 执行 jsonpath 从 响应数据中 提取想要的数据
                first_match, matches = self._jsonpath_toolkit.extract_jsonpath(
                    response_payload=payload,
                    expr=expr,
                    where=rule_where
                )

                # 计算断言结果
                passed, msg = self._eval_op(op=op, actual=first_match, expected=expected, matches=matches)

                # 记录结果
                results.append(
                    AssertionResult(passed=passed, rule=rule, actual=first_match, expected=expected, message=msg)
                )

            # 其他异常
            except Exception as e:
                # 构建明确异常上下文
                error_context = build_api_exception_context(
                    phase=ExceptionPhase.ASSERT,
                    error_code=ExceptionCode.ASSERT_ERROR,
                    message="断言执行异常",
                    reason=str(e),
                    yaml_location=rule_where,
                    api_id=api_id,
                    step_name=step_name,
                    request_snapshot=request_snapshot,
                    hint="请检查 source/jsonpath/op 的组合是否可执行1"
                )
                raise AssertException(error_context) from e

        return results

    def _eval_op(self, op: str, actual, expected, matches: List[Any]) -> tuple[bool, str]:
        """
          执行比较规则
        :param op: 断言规则
        :param actual: 提取到的第一个匹配的实际数据
        :param expected: 期望数据
        :param matches: 提取到的所有匹配的实际数据
        :return: 返回断言结果 与 比较规则msg (元组)
        """
        # 存在判断, 断言该字段是否存在, 没有 expected
        if op == "exists":
            ok = bool(matches)
            assert ok
            return ok, "exists 判断"

        if op == "==":
            assert actual == expected
            return actual == expected, "=="
        if op == "!=":
            assert actual != expected
            return actual != expected, "!="
        if op == ">":
            assert actual > expected
            return actual > expected, ">"
        if op == ">=":
            assert actual >= expected
            return actual >= expected, ">="
        if op == "<":
            assert actual < expected
            return actual < expected, "<"
        if op == "<=":
            assert actual <= expected
            return actual <= expected, "<="

        # 判断是否包含 expected
        if op == "contains":
            try:
                assert expected in actual
                return expected in actual, "contains"
            # 若 actual 不是可迭代类型, 将其导致的异常进行捕获处理
            except TypeError as e:
                return False, f"contains 判断失败, actual 不支持 'in' 判断, type={type(actual)}, error={e}"

        # regex：正则匹配（expected 必须是 pattern）
        if op == "regex":
            # 转字符串
            pat = str(expected)
            s = "" if actual is None else str(actual)
            ok = re.search(pat, s) is not None
            return ok, "regex"

        # 不支持的 op 类型直接报错
        raise ValueError(f"不支持的 op：{op}")
