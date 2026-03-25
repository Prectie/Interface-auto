# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from requests import Response

from Core.context import RuntimeContext
from Core.data_processing import render_any
from Engine.jsonpath_tool import JsonPathTool

from Engine.results import AssertionResult
from Exceptions.AutoApiException import build_api_exception_context, ExceptionCode, AssertException


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
        *,
        api_id: Optional[str] = None,
        flow_file: Optional[str] = None,
        step_id: Optional[str] = None,
        profile_name: Optional[str] = None,
        yaml_file: Optional[str] = None,
        request_snapshot: Optional[Dict[str, Any]] = None
    ) -> List[AssertionResult]:
        """
          逐条执行断言并返回结果列表
        :param assertions: 断言规则列表
        :param response: 响应对象
        :param ctx: 上下文（用于 expected 渲染）
        :param api_id: 接口库的接口id
        :param flow_file: 业务流文件
        :param step_id: 业务流的步骤名称
        :param profile_name: 前置接口名称
        :param yaml_file: 当前错误应归属于哪个 yaml 文件
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
            try:
                # 读取 source、jsonpath、op、expected
                source = rule["source"]
                expr = rule["jsonpath"]
                op = rule["op"]
                # 允许为 None 值(在断言字段存在时)
                expected_raw = rule.get("expected", None)

                # 渲染 expected（允许 ${var}）, 存在断言数据依赖 extract 的提取结果, 比如 {user_id}
                expected = render_any(
                    data=expected_raw,
                    ctx=ctx.snapshot(),
                    path="expected"
                )

                # 按 source 从响应数据中取数据载体
                payload = self._jsonpath_toolkit.read_source(
                    source=source,
                    response=response
                )

                # 执行 jsonpath 从 响应数据中 提取想要的数据
                first_match, matches = self._jsonpath_toolkit.extract_jsonpath(
                    response_payload=payload,
                    expr=expr,
                )

                # 计算断言结果
                passed, msg = self._eval_op(
                    op=op,
                    actual=first_match,
                    expected=expected,
                    matches=matches
                )

                # 记录结果
                results.append(
                    AssertionResult(passed=passed, rule=rule, actual=first_match, expected=expected, message=msg)
                )
            except AssertionError:
                raise
            # 其他异常
            except Exception as e:
                # 构建明确异常上下文
                error_context = build_api_exception_context(
                    error_code=ExceptionCode.ASSERT_ERROR,
                    message="断言执行异常",
                    reason=str(e),
                    yaml_file=yaml_file,
                    flow_file=flow_file,
                    api_id=api_id,
                    step_id=step_id,
                    profile_name=profile_name,
                    request=request_snapshot,
                    response=response,
                    hint="请检查 source/jsonpath/op 的组合是否可执行1"
                )
                raise AssertException(error_context) from e

        # 全部断言执行完成后, 筛选失败项
        failed_results = [item for item in results if not item.passed]

        # 若存在失败项, 统一抛出异常
        if failed_results:
            self._raise_assert_failed(
                failed_results=failed_results,
                response=response,
                yaml_file=yaml_file,
                flow_file=flow_file,
                api_id=api_id,
                step_id=step_id,
                profile_name=profile_name,
                request_snapshot=request_snapshot
            )

        # 若全部通过, 则返回完整结果列表
        return results

    def _raise_assert_failed(
        self,
        failed_results: List[AssertionResult],
        response: Response,
        *,
        api_id: Optional[str] = None,
        flow_file: Optional[str] = None,
        step_id: Optional[str] = None,
        profile_name: Optional[str] = None,
        yaml_file: Optional[str] = None,
        request_snapshot: Optional[Dict[str, Any]] = None
    ):
        """
        :param failed_results: 失败断言列表
        :param response: 响应对象
        :param api_id: 接口库的接口id
        :param flow_file: 业务流文件
        :param step_id: 业务流的步骤名称
        :param profile_name: 前置接口名称
        :param yaml_file: 当前错误应归属于哪个 yaml 文件
        :param request_snapshot: 请求数据快照
        """
        # 初始化断言失败输出摘要结果列表
        reason_lines: List[str] = []

        # 遍历失败结果
        for item in failed_results:
            reason_lines.append(f"[断言失败]")
            reason_lines.append(f"rule={item.rule}")
            reason_lines.append(f"actual={item.actual}")
            reason_lines.append(f"expected={item.expected}")
            reason_lines.append(f"message={item.message}")

        error_context = build_api_exception_context(
            error_code=ExceptionCode.ASSERT_ERROR,
            message=f"断言失败, 断言所属接口={api_id}, 供 {len(failed_results)} 条未通过",
            reason="\n".join(reason_lines),
            yaml_file=yaml_file,
            flow_file=flow_file,
            api_id=api_id,
            step_id=step_id,
            profile_name=profile_name,
            request=request_snapshot,
            response=response,
            extra={
                "failed_count": len(failed_results),
                "failed_result": [item.to_dict() for item in failed_results]
            }
        )
        raise AssertException(error_context)

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
            try:
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


