# -*- coding: utf-8 -*-  # 声明源码编码，避免中文注释乱码

from __future__ import annotations  # 允许前向引用类型注解  # 语法说明

from typing import Any, Dict, List, Optional  # 导入类型注解用于增强可读性与IDE提示  # 导入说明
import json  # 导入 json 用于必要时把字符串解析成对象（仅作为兜底）  # 导入说明

from requests import Response
from jsonpath_ng.ext import parse
from Exceptions.schema_exception import YamlSchemaException


class extract_error(Exception):  # 提取失败异常（执行期错误，不是结构错误）  # 类说明
    """目的/作用：当 jsonpath 无匹配、source 不支持、响应对象不符合预期等情况发生时抛出。"""  # 类说明结束
    pass  # 无额外实现  # 说明


class Extractor:  # 提取器：把响应内容按 extract 规则写入 ctx  # 类说明
    """
    目的/作用：
        执行 extract 规则列表：
          - 从 response 的指定 source 读取载体（例如 response_json）；  # 读数据
          - 用 jsonpath 提取值；  # 提取
          - 写入 ctx（key=as）；  # 存入上下文
        注意：本模块只负责“提取”，不负责请求发送、不负责断言执行。  # 职责边界
    """
    def __init__(self):
        self._jp_cache: Dict[str, Any] = {}

    def apply(self, rules: List[Dict[str, Any]], response: Any, ctx: Any, where: str = "") -> Dict[str, Any]:  # 执行提取规则  # 方法签名说明
        """
        目的/作用：
            逐条执行 extract 规则，并把提取结果写入 ctx。
        :param rules: extract 规则列表（每条必须包含 source/jsonpath/as）。  # 参数说明
        :param response: 响应对象（未来通常是 requests.Response）。  # 参数说明
        :param ctx: 运行时上下文对象（要求提供 set(key,value) 方法）。  # 参数说明
        :param where: 规则来源定位（用于中文报错，例如 single.apis.xxx.extract）。  # 参数说明
        :return: 本次提取出的变量字典 {as: value}。  # 返回值说明
        """  # 文档说明结束
        if not isinstance(rules, list):  # rules 必须是 list  # 条件说明
            raise YamlSchemaException(f"{where} extract 规则必须是 list")  # 抛中文异常  # 异常说明

        out: Dict[str, Any] = {}  # 初始化输出结果  # 变量说明
        for i, rule in enumerate(rules, start=1):  # 遍历每条规则  # 循环说明
            if not isinstance(rule, dict):  # 每条规则必须是 dict  # 条件说明
                raise YamlSchemaException(f"{where} extract[{i}] 必须是 dict")  # 抛中文异常  # 异常说明

            source = rule.get("source", None)  # 读取 source  # 取值说明
            if not isinstance(source, str) or not source.strip():  # source 必须是非空字符串  # 条件说明
                raise YamlSchemaException(f"{where} extract[{i}].source 必须是非空字符串")  # 抛中文异常  # 异常说明
            source = source.strip()  # 去空格  # 处理说明

            expr = rule.get("jsonpath", None)  # 读取 jsonpath  # 取值说明
            if not isinstance(expr, str) or not expr.strip():  # jsonpath 必须是非空字符串  # 条件说明
                raise YamlSchemaException(f"{where} extract[{i}].jsonpath 必须是非空字符串")  # 抛中文异常  # 异常说明
            expr = expr.strip()  # 去空格  # 处理说明

            as_name = rule.get("as", None)  # 读取 as  # 取值说明
            if not isinstance(as_name, str) or not as_name.strip():  # as 必须是非空字符串  # 条件说明
                raise YamlSchemaException(f"{where} extract[{i}].as 必须是非空字符串")  # 抛中文异常  # 异常说明
            as_name = as_name.strip()  # 去空格  # 处理说明

            response_payload = self._read_source(source=source, response=response)  # 按 source 取载体  # 调用说明
            value = self._extract_jsonpath(response_payload=response_payload, expr=expr, where=f"{where} extract[{i}]")  # 执行 jsonpath 提取  # 调用说明

            ctx.set(as_name, value)  # 写入上下文（供后续 ${as_name} 渲染/断言使用）  # 调用说明
            out[as_name] = value  # 写入输出结果（便于日志/Allure 附件）  # 赋值说明

        return out  # 返回提取结果  # 返回说明

    def _read_source(self, source: str, response: Response):  # 读取 source 对应载体  # 方法签名说明
        """
        目的/作用：
            将 YAML 中的 source 路由到具体数据载体，保证“从哪里取数据”一致可控。
        约束：只允许固定枚举值，不做兼容。  # 严格约束
        :param source: source 字符串。  # 参数说明
        :param response: 响应对象。  # 参数说明
        :return: 被提取的载体对象（dict/list/str/int...）。  # 返回值说明
        """  # 文档说明结束
        if source == "response_json":  # 从响应 json 提取  # 条件说明
            if hasattr(response, "json"):  # 要求 response.json() 可调用  # 条件说明
                return response.json()  # 返回 json 对象（通常是 dict/list）  # 返回说明
            raise extract_error("source=response_json 但 response 不支持 json() 方法")  # 抛中文提取异常  # 异常说明

        if source == "response_text":  # 从响应文本提取  # 条件说明
            return response.text  # 返回 response.text（缺省空串）  # 返回说明

        if source == "response_headers":  # 从响应头提取  # 条件说明
            return dict(response.headers)  # 返回 headers dict  # 返回说明

        if source == "response_status":  # 从响应状态码提取  # 条件说明
            return response.status_code  # 返回 status_code  # 返回说明

        raise extract_error(f"不支持的 source：{source}")  # 不支持的 source 直接报错  # 异常说明

    def _extract_jsonpath(self, response_payload: Any, expr: str, where: str) -> Any:  # 执行 jsonpath 提取  # 方法签名说明
        """
        目的/作用：
            使用 jsonpath_ng 从 payload 中提取字段，默认取第一个匹配值。
        :param response_payload: jsonpath 输入对象（通常为 dict/list）。  # 参数说明
        :param expr: jsonpath 表达式字符串。  # 参数说明
        :param where: 报错定位。  # 参数说明
        :return: 提取到的值（默认第一个匹配）。  # 返回值说明
        """  # 文档说明结束
        payload2 = self._ensure_json_container(payload=response_payload, where=where)  # 确保 payload 是 dict/list  # 调用说明
        jp = self._jp_parse(expr)  # parse(jsonpath) 得到表达式对象  # 调用说明
        matches = [m.value for m in jp.find(payload2)]  # 执行 find 并取 value 列表  # 调用说明
        if not matches:  # 若无匹配结果  # 条件说明
            raise extract_error(f"{where} jsonpath 无匹配：{expr}")  # 抛中文提取异常  # 异常说明
        return matches[0]  # 默认取第一个匹配值（你目前规则未定义 want/index，所以固定 first）  # 返回说明

    def _ensure_json_container(self, payload: Any, where: str) -> Any:  # 确保 payload 可被 jsonpath 处理  # 方法签名说明
        """
        目的/作用：
            jsonpath_ng 需要 dict/list；若 payload 是可解析为 JSON 的字符串，则尝试 json.loads 解析成 dict/list。
        :param payload: 输入载体。  # 参数说明
        :param where: 报错定位。  # 参数说明
        :return: dict/list。  # 返回值说明
        """  # 文档说明结束
        if isinstance(payload, (dict, list)):  # 若已是 dict/list  # 条件说明
            return payload  # 直接返回  # 返回说明
        if isinstance(payload, str):  # 若是字符串  # 条件说明
            s = payload.strip()  # 去空格  # 处理说明
            if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):  # 简单判断是否像 JSON  # 条件说明
                try:  # 尝试解析 JSON  # 说明
                    obj = json.loads(s)  # 解析为 python 对象  # 调用说明
                    if isinstance(obj, (dict, list)):  # 必须是 dict/list  # 条件说明
                        return obj  # 返回可用容器  # 返回说明
                except Exception as e:  # JSON 解析失败  # 异常说明
                    raise extract_error(f"{where} payload 看似 JSON 但解析失败：{e}")  # 抛中文提取异常  # 异常说明
        raise extract_error(f"{where} jsonpath 输入必须是 dict/list（或可解析 JSON 的字符串），当前类型：{type(payload)}")  # 抛中文异常  # 异常说明

    def _jp_parse(self, expr: str):
        if not isinstance(expr, str) or not expr.strip():
            raise extract_error("")

        expr2 = expr.strip()
        if expr2 in self._jp_cache:
            return self._jp_cache[expr2]

        compiled = parse(expr2)
        self._jp_cache[expr2] = compiled
        return compiled
