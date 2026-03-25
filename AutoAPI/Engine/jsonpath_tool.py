from typing import Dict, Any
import json

from requests import Response
from jsonpath_ng.ext import parse


class JsonPathTool:
    """
      jsonpath工具, 负责 source 读取 + jsonpath 表达式与编译结果缓存 + jsonpath 提取
    """
    def __init__(self):
        """
          作用:
            初始化 jsonpath 编译缓存, 避免同一个表达式在多条用例中, 多次重复执行 parse 编译
            key=expr字符串, value=编译后的 jsonpath 对象
        """
        self._jp_cache: Dict[str, Any] = {}

    def read_source(self, source: str, response: Response):
        """
          作用：
            根据 YAML 中的 source 从实际 响应数据 中指定载体进行提取数据
        :param source: source 字符串
        :param response: 响应对象
        :return: 被提取的载体对象/数据
        """
        # 从响应 json 提取
        if source == "response_json":
            # 返回响应数据里的 json 对象
            return response.json()

        # 从响应文本提取
        if source == "response_text":
            # 返回 response.text 缺省空串
            return response.text

        # 从响应头提取
        if source == "response_headers":
            # 返回 headers dict
            return dict(response.headers)

        # 从响应状态码提取
        if source == "response_status":
            # 返回 status_code
            return response.status_code

        raise ValueError(f"不支持的 source：{source}")

    def extract_jsonpath(self, response_payload, expr: str, where: str):
        """
          作用：
            使用 jsonpath_ng 从 payload 中提取字段，默认取第一个匹配值。
        :param response_payload: jsonpath 输入对象（通常为 dict/list）。  # 参数说明
        :param expr: jsonpath 表达式字符串。  # 参数说明
        :param where: 报错定位。  # 参数说明
        :return: 提取到的值（默认第一个匹配）。  # 返回值说明
        """
        # 确保 payload 是 dict/list
        payload2 = self._ensure_json_container(payload=response_payload, where=where)
        # parse(jsonpath) 得到表达式对象
        jp = self._jp_parse(expr)
        # 执行 find 找到匹配结果, 并取 value 列表
        matches = [m.value for m in jp.find(payload2)]
        # 若无匹配结果
        if not matches:
            # TODO 构建完整的报错信息
            # error_context =
            raise ValueError(f"{where} jsonpath 无匹配：{expr}")
        # 返回第一个匹配值, 以及完整的匹配数据
        return matches[0], matches

    def _ensure_json_container(self, payload: Any, where: str) -> Any:
        """
          作用：
            确保 payload 可被 jsonpath 处理
            jsonpath_ng 需要 dict/list; 若 payload 是可解析为 JSON 的字符串, 则尝试 json.loads 解析成 dict/list

        :param payload: 输入载体
        :param where: 报错定位
        :return: dict/list
        """
        # 若已是 dict/list, 则直接返回
        if isinstance(payload, (dict, list)):
            return payload
        # 若是字符串
        if isinstance(payload, str):
            # 去首尾空格
            s = payload.strip()
            # 简单判断是否像 JSON
            if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
                try:
                    # 尝试解析 JSON, 解析为 python 对象
                    obj = json.loads(s)
                    if isinstance(obj, (dict, list)):
                        return obj
                except Exception as e:
                    # JSON 解析失败
                    raise ValueError(f"{where} payload 看似 JSON 但解析失败：{e}")
        raise ValueError(f"{where} jsonpath 输入必须是 dict/list（或可解析 JSON 的字符串），当前类型：{type(payload)}")

    def _jp_parse(self, expr: str):
        """
          编译 jsonpath 表达式, 并使用 _jp_cache 进行缓存
        :param expr: jsonpath 表达式字符串
        :return: jsonpath 对象
        """
        # 禁止首尾空格的情况
        if expr != expr.strip():
            raise ValueError("jsonpath 含首尾空格")

        # 若 缓存中已存在该 表达式, 直接返回对应的 jsonpath 对象
        if expr in self._jp_cache:
            return self._jp_cache[expr]

        # 编译表达式, 获得 jsonpath 对象
        compiled = parse(expr)
        # 编译成功后存入缓存中
        self._jp_cache[expr] = compiled
        return compiled
