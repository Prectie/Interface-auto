# -*- coding: utf-8 -*-  # 声明源码编码，避免中文注释乱码  #

from __future__ import annotations  # 允许前向引用类型注解  #

import re  # 导入正则，用于 regex 断言  #
from typing import Any, Dict, List, Optional  # 导入类型注解  #

from jsonpath_ng.ext import parse  # 导入 jsonpath_ng 解析器  #
from requests import Response  # 导入 Response 类型  #

from Base.context import RuntimeContext  # 导入运行时上下文  #
from Base.data_processing import render_any, var_resolve_error  # 导入渲染与变量异常  #

from Runtime.results import AssertionResult  # 导入断言结果对象  #
from Runtime.runtime_exception import AssertionFailed, RuntimeErrorDetail, ResponseProcessError  # 导入断言失败异常  #


class AssertionEngine:  # 断言引擎  #
    """assertion_engine 类实现  # 类说明
    assertion_engine 负责执行 assertions：source/jsonpath/op/expected。  # 类职责说明
    """  # 类说明结束  #

    def __init__(self):  # 初始化  #
        self._jp_cache: Dict[str, Any] = {}  # jsonpath 编译缓存  #

    def assert_all(  # 执行全部断言  #
        self,  # self 说明  #
        assertions: Optional[List[Dict[str, Any]]],  # 断言规则列表  #
        response: Response,  # 响应对象  #
        ctx: RuntimeContext,  # 上下文（用于 expected 渲染）  #
        where: str,  # 定位字符串  #
        fail_fast: bool = False,  # 是否遇到失败立即抛异常  #
    ) -> List[AssertionResult]:  # 返回断言结果列表  #
        """assert_all 方法  # 方法说明
        功能说明：逐条执行断言并返回结果列表；fail_fast=True 时遇到失败立即抛 AssertionFailed。  # 功能说明
        参数说明：assertions/response/ctx/where/fail_fast。  # 参数说明
        返回值说明：List[AssertionResult]。  # 返回值说明
        在系统中的作用：完成接口自动化闭环（提取 + 断言）。  # 系统作用
        调用关系：被 executor 在每次响应后调用。  # 调用关系
        """  # 方法说明结束  #
        if not assertions:  # 若无断言  #
            return []  # 返回空结果  #

        results: List[AssertionResult] = []  # 初始化结果列表  #

        for i, rule in enumerate(assertions, start=1):  # 遍历每条断言  #
            rule_where = f"{where}.assertions[{i}]"  # 构造规则定位  #
            try:  # 捕获单条断言异常  #
                source = str(rule.get("source", "")).strip()  # 读取 source  #
                expr = str(rule.get("jsonpath", "")).strip()  # 读取 jsonpath  #
                op = str(rule.get("op", "")).strip()  # 读取 op  #
                expected_raw = rule.get("expected")  # 读取 expected（允许 None，但必须有键）  #

                expected = render_any(data=expected_raw, ctx=ctx.snapshot(), path=f"{rule_where}.expected")  # 渲染 expected（允许 ${var}）  #

                payload = self._read_source(source=source, response=response, where=rule_where)  # 读取 source 载体  #
                actual, matches = self._extract_by_jsonpath(payload=payload, expr=expr, where=rule_where)  # jsonpath 提取  #

                passed, msg = self._eval_op(op=op, actual=actual, expected=expected, matches=matches)  # 计算断言结果  #

                results.append(AssertionResult(passed=passed, rule=rule, actual=actual, expected=expected, message=msg))  # 记录结果  #

                if fail_fast and not passed:  # 若 fail_fast 且失败  #
                    detail = RuntimeErrorDetail(where=rule_where, message="断言失败", extra={"rule": rule, "actual": actual, "expected": expected, "message": msg})  # 构造 detail  #
                    raise AssertionFailed(detail)  # 立即抛错  #
            except var_resolve_error as e:  # expected 渲染失败  #
                detail = RuntimeErrorDetail(where=rule_where, message="断言 expected 渲染失败（变量未解析）", extra=str(e))  # 构造 detail  #
                raise ResponseProcessError(detail) from e  # 抛出响应处理异常  #
            except AssertionFailed:  # 若已经是 AssertionFailed  #
                raise  # 直接向上抛  #
            except Exception as e:  # 其他异常  #
                detail = RuntimeErrorDetail(where=rule_where, message="断言执行异常", extra=str(e))  # 构造 detail  #
                raise ResponseProcessError(detail) from e  # 抛出响应处理异常  #

        return results  # 返回断言结果列表  #

    def _read_source(self, source: str, response: Response, where: str) -> Any:  # 读取 source 载体  #
        """_read_source 方法  # 方法说明
        功能说明：将 source 路由到 response_json/text/headers/status。  # 功能说明
        参数说明：source/response/where。  # 参数说明
        返回值说明：载体对象。  # 返回值说明
        在系统中的作用：与 extractor 的 source 语义保持一致。  # 系统作用
        调用关系：被 assert_all 调用。  # 调用关系
        """  # 方法说明结束  #
        if source == "response_json":  # json 载体  #
            try:  # 捕获 json 解析异常  #
                return response.json()  # 返回 json 对象  #
            except Exception as e:  # json 解析失败  #
                raise Exception(f"{where} response_json 解析失败：{e}")  # 抛出异常  #
        if source == "response_text":  # text 载体  #
            return response.text  # 返回文本  #
        if source == "response_headers":  # headers 载体  #
            return dict(response.headers)  # 返回 headers dict  #
        if source == "response_status":  # status 载体  #
            return response.status_code  # 返回状态码  #
        raise Exception(f"{where} 不支持的 source：{source}")  # 不支持直接报错  #

    def _jp_parse(self, expr: str) -> Any:  # 编译/复用 jsonpath  #
        expr2 = expr.strip()  # 去空格  #
        if expr2 in self._jp_cache:  # 若已缓存  #
            return self._jp_cache[expr2]  # 返回缓存对象  #
        compiled = parse(expr2)  # 编译 jsonpath  #
        self._jp_cache[expr2] = compiled  # 写入缓存  #
        return compiled  # 返回编译对象  #

    def _extract_by_jsonpath(self, payload: Any, expr: str, where: str) -> tuple[Any, List[Any]]:  # 执行 jsonpath  #
        """_extract_by_jsonpath 方法  # 方法说明
        功能说明：对 payload 执行 jsonpath；默认 actual 取第一个匹配值。  # 功能说明
        参数说明：payload/expr/where。  # 参数说明
        返回值说明：(actual, matches)。  # 返回值说明
        在系统中的作用：统一断言提取逻辑，和 extractor 保持一致“first match”。  # 系统作用
        调用关系：被 assert_all 调用。  # 调用关系
        """  # 方法说明结束  #
        expr2 = expr.strip()  # 去空格  #
        if isinstance(payload, (dict, list)):  # 若 payload 可被 jsonpath 处理  #
            jp = self._jp_parse(expr2)  # 编译 jsonpath  #
            matches = [m.value for m in jp.find(payload)]  # 执行 find  #
            actual = matches[0] if matches else None  # 取第一个匹配  #
            return actual, matches  # 返回  #

        if expr2 in ("$", "$."):  # 若 expr 表示“取整体”  #
            return payload, [payload]  # 把整体作为一个 match 返回  #

        raise Exception(f"{where} payload 非 dict/list，jsonpath 仅支持 '$' 取整体，当前 expr={expr2}")  # 抛出异常  #

    def _eval_op(self, op: str, actual: Any, expected: Any, matches: List[Any]) -> tuple[bool, str]:  # 执行 op 比较  #
        """_eval_op 方法  # 方法说明
        功能说明：执行 op 映射（==/!=/contains/regex/exists/gt...）。  # 功能说明
        参数说明：op/actual/expected/matches。  # 参数说明
        返回值说明：(passed, message)。  # 返回值说明
        在系统中的作用：把断言语义收口在 assertion_engine。  # 系统作用
        调用关系：被 assert_all 调用。  # 调用关系
        """  # 方法说明结束  #
        op2 = op.strip()  # 去空格  #

        if op2 == "exists":  # exists：至少一个 match  #
            ok = bool(matches)  # 是否存在匹配  #
            return ok, "exists 判断"  # 返回  #

        if op2 == "==":  # 等于  #
            return actual == expected, "=="  # 返回  #
        if op2 == "!=":  # 不等于  #
            return actual != expected, "!="  # 返回  #
        if op2 == ">":  # 大于  #
            return actual > expected, ">"  # 返回  #
        if op2 == ">=":  # 大于等于  #
            return actual >= expected, ">="  # 返回  #
        if op2 == "<":  # 小于  #
            return actual < expected, "<"  # 返回  #
        if op2 == "<=":  # 小于等于  #
            return actual <= expected, "<="  # 返回  #

        if op2 == "contains":  # contains：容器包含  #
            try:  # 捕获类型错误  #
                return expected in actual, "contains"  # 返回  #
            except Exception:  # 类型不支持  #
                return False, "contains 类型不支持"  # 返回失败  #

        if op2 == "regex":  # regex：正则匹配（expected 必须是 pattern）  #
            pat = str(expected)  # 转字符串  #
            s = "" if actual is None else str(actual)  # 转字符串  #
            ok = re.search(pat, s) is not None  # 判断匹配  #
            return ok, "regex"  # 返回  #

        return False, f"不支持的 op：{op2}"  # 不支持直接失败（不吞掉）  #
