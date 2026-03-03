# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from requests import Response

from Base.context import RuntimeContext
from Base.data_processing import render_any
from Base.jsonpath_tool import JsonPathTool
from Exceptions.var_resolve_exception import VarResolveError

from Runtime.results import AssertionResult
from Exceptions.runtime_exception import AssertionFailed, RuntimeErrorDetail, ResponseProcessError


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
    ) -> List[AssertionResult]:
        """
          逐条执行断言并返回结果列表
        :param assertions: 断言规则列表
        :param response: 响应对象
        :param ctx: 上下文（用于 expected 渲染）
        :param where: assertions 定位路径
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
                first_match, matches = self._jsonpath_toolkit.extract_jsonpath(response_payload=payload, expr=expr, where=rule_where)

                # 计算断言结果
                passed, msg = self._eval_op(op=op, actual=first_match, expected=expected, matches=matches)

                # 记录结果
                results.append(
                    AssertionResult(passed=passed, rule=rule, actual=first_match, expected=expected, message=msg)
                )

            # expected 渲染失败情况
            except VarResolveError as e:
                detail = RuntimeErrorDetail(where=rule_where, message="断言 expected 渲染失败（变量未解析）", extra=str(e))
                raise ResponseProcessError(detail) from e
            # 若已经是 AssertionFailed, 直接向上抛
            except AssertionFailed:
                raise
            # 其他异常
            except Exception as e:
                detail = RuntimeErrorDetail(where=rule_where, message="断言执行异常", extra=str(e))
                raise ResponseProcessError(detail) from e

        return results

    def _eval_op(self, op: str, actual, expected, matches: List[Any]) -> tuple[bool, str]:  # 执行 op 比较  #
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
            return ok, "exists 判断"

        if op == "==":
            return actual == expected, "=="
        if op == "!=":
            return actual != expected, "!="
        if op == ">":
            return actual > expected, ">"
        if op == ">=":
            return actual >= expected, ">="
        if op == "<":
            return actual < expected, "<"
        if op == "<=":
            return actual <= expected, "<="

        # 判断是否包含 expected
        if op == "contains":
            return expected in actual, "contains"  # 返回  #

        # regex：正则匹配（expected 必须是 pattern）
        if op == "regex":
            # 转字符串
            pat = str(expected)
            s = "" if actual is None else str(actual)
            ok = re.search(pat, s) is not None
            return ok, "regex"

        # 不支持的 op 类型直接报错
        raise ValueError(f"不支持的 op：{op}")
