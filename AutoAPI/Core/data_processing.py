# -*- coding: utf-8 -*-
import re
from typing import Any, Mapping, Dict, List
import copy

from Exceptions.AutoApiException import VarResolveException, build_api_exception_context, ExceptionPhase, ExceptionCode
from Utils.print_pretty import print_rich


def deep_merge(base, override):
    """
      深度合并数据

      使用场景:
        - 如 config.yaml 里的 auth_profiles 或 multiple.yaml 里的 ref 进行引用 api 模板时, 需要合并/覆盖模板数据时则使用

      注意事项:
        - dict 类型是合并, 若需要覆盖则 key 要和原数据里的 key 重名
        - 非dict 则是直接覆盖
    :param base: 原数据
    :param override: 覆盖数据
    """
    # 仅当两者都是 dict 才递归合并
    if isinstance(base, dict) and isinstance(override, dict):
        # 深拷贝 base 作为输出，避免修改原对象
        merged = copy.deepcopy(base)
        # 遍历 override 的每个键值对
        for k, v in override.items():
            # 若 base 已存在该键
            if k in merged:
                # 递归合并更深层结构
                merged[k] = deep_merge(merged[k], v)

            # 若 base 不存在该键
            else:
                # 直接写入并深拷贝，避免引用共享
                merged[k] = copy.deepcopy(v)
        # 返回合并结果
        return merged
    # 非 dict：直接返回 override 的深拷贝（覆盖语义）
    return copy.deepcopy(override)


# 编译正则：匹配 ${xxx}，xxx 不允许包含 }
_var_pattern = re.compile(r"\$\{([^}]+)\}")


def render_any(data, ctx: Mapping[str, Any], path: str = "$"):
    """
      递归渲染任意结构，把其中的 ${var} 替换为 ctx 中的真实值(用于发请求/断言/提取前的变量展开)

      规则：
        - 若遇到占位符变量缺失，直接抛出中文异常(不提供开关)

    :param data: 待渲染的数据结构；可以是 dict/list/str/int/bool/None 等任意类型
    :param ctx: 上下文变量容器 (通常传 ctx.snapshot() 得到的 dict 或 Mapping)
    :param path: 定位路径 (用于报错时指出出问题的字段位置); 默认 "$"
    :return: 渲染后的新结构 (输入是 dict/list 会返回新对象；非字符串基础类型原样返回)
    :raises VarResolveError: 当占位符变量缺失时抛出
    """
    # 若当前节点是字符串
    if isinstance(data, str):
        # 渲染字符串并返回
        return render_str(text=data, ctx=ctx, path=path)

    # 若当前节点是字典
    if isinstance(data, dict):
        # 初始化输出字典，保存渲染后的 key/value
        out: Dict[str, Any] = {}
        # 遍历字典键值对
        for k, v in data.items():
            # 拼接子路径，便于报错定位到具体字段
            child_path = f"{path}.{k}"
            # 递归渲染 value
            out[k] = render_any(data=v, ctx=ctx, path=child_path)
        # 返回渲染后的新字典, 不污染原数据
        return out

    # 若当前节点是列表（一般是 steps/assert/extract）
    if isinstance(data, list):
        # 初始化输出列表，用于保存渲染后的元素
        out_list: List[Any] = []
        # 遍历列表元素并拿到索引
        for i, item in enumerate(data):
            # 拼接子路径，便于定位到具体下标
            child_path = f"{path}[{i}]"
            # 递归渲染元素
            out_list.append(render_any(data=item, ctx=ctx, path=child_path))
        # 返回渲染后的新列表, 不污染原数据
        return out_list

    # 其他类型（int/bool/None/float 等）无需渲染，直接返回
    return data


def render_str(text: str, ctx: Mapping[str, Any], path: str = "$"):
    """
      渲染字符串中的 ${var} 占位符。

      规则：
        1) 若字符串整体就是一个占位符（例如 "${user_id}"），则返回 ctx 中变量的“原类型值”（int/bool/dict...）
        2) 若占位符嵌在字符串中（例如 "bearer ${token}"），则把变量值转换为 str 后替换进去，返回最终字符串
        3) 若变量缺失，直接抛中文异常（不提供开关）

    :param text: 原始字符串（可能包含 ${var}）
    :param ctx: 上下文变量容器（Mapping）
    :param path: 字段定位路径，用于异常提示
    :return: 若为整值引用返回变量原类型；否则返回替换后的字符串
    :raises var_resolve_error: 当占位符变量缺失时抛出
    """
    # 去掉首尾空白用于整值匹配（不改变原 text 用于替换）
    stripped = text.strip()

    # 判断是否为“整值引用”（字符串完全等于 ${var}）
    m = _var_pattern.fullmatch(stripped)
    # 若是整值引用
    if m:
        # 提取变量名并去掉空白
        var_name = m.group(1).strip()
        # 返回原类型值
        return _get_var_value(var_name=var_name, ctx=ctx, path=path, template=text)

    def _replace(match: re.Match) -> str:
        """
          替换回调：用于把每个 ${var} 替换成字符串形式的真实值。

        :param match: 正则匹配对象，match.group(1) 为变量名
        :return: 替换后的字符串片段（必须是 str）
        :raises VarResolveError: 当占位符变量缺失时抛出
        """
        # 提取变量名
        var_name = match.group(1).strip()
        # 获取变量真实值
        value = _get_var_value(var_name=var_name, ctx=ctx, path=path, template=text)
        # 内嵌替换时统一转为字符串进行拼接
        return str(value)

    # 替换字符串中所有 ${var}，得到渲染后的文本
    rendered = _var_pattern.sub(_replace, text)
    # 返回渲染后的字符串
    return rendered


def _get_var_value(var_name: str, ctx: Mapping[str, Any], path: str, template: str):
    """
      从 ctx 中获取真实变量值，支持简单 key 与点号路径（如 a.b.c）。

    :param var_name: 变量名（${...} 内部内容），例如 "token" 或 "a.b.c"
    :param ctx: 上下文变量容器
    :param path: 当前字段定位路径，用于异常信息定位
    :param template: 原始模板字符串，用于异常中回显，便于排查
    :return: 解析到的变量值（可能是 str/int/bool/dict/list 等任意类型）
    :raises VarResolveError: 当变量缺失时抛出中文异常
    """
    # 若 ctx 顶层直接存在该 key
    if var_name in ctx:
        # 直接返回对应值（保留原类型）
        return ctx[var_name]

    ctx_preview_keys = list(ctx.keys())

    # 若变量名包含点号路径
    if "." in var_name:
        # 从 ctx 开始逐层向下取值
        cur = ctx
        # 按点号拆分路径片段
        for part in var_name.split("."):
            # 当前层是映射且包含该 key
            if isinstance(cur, Mapping) and part in cur:
                # 下钻到下一层
                cur = cur[part]
            # 中间某一层不存在
            else:
                error_context = build_api_exception_context(
                    phase=ExceptionPhase.RENDER,
                    error_code=ExceptionCode.VAR_RENDER_ERROR,
                    message="变量渲染失败",
                    reason=f"变量子路径不存在: {var_name}, 缺失: {part}",
                    yaml_location=path,
                    hint="请检查是否遗漏 extract 写入、static 注入, 或 jsonpath 路径错误等",
                    extra={
                        "原始接口模板": template,
                        "变量名称": var_name,
                        "context 现有的 key": ctx_preview_keys
                    }
                )
                raise VarResolveException(error_context)
        # 路径解析成功, 返回最终值
        return cur

    error_context = build_api_exception_context(
        phase=ExceptionPhase.RENDER,
        error_code=ExceptionCode.VAR_RENDER_ERROR,
        message="变量渲染失败",
        reason=f"变量不存在: {var_name}",
        hint="请检查是否遗漏 extract 写入、static 注入, 或 jsonpath 路径错误等",
        extra={
            "需要找的 key": template,
            "变量名称": var_name,
            "context 现有的 key": ctx_preview_keys
        }
    )
    raise VarResolveException(error_context)


if __name__ == "__main__":
    ctx = {
        "token": "t123",
        "user_id": 1001
    }

    data_str_full = "${token.pp}"
    out_str_full = render_any(data_str_full, ctx)
    print(out_str_full)

    # data_lists = [
    #     "${token}",
    #     "token=${token}",
    #     {"k": "Bearer ${token}"},
    #     1,
    #     None,
    #     ["${user_id}", {"inner": "${token}"}]
    # ]
    # print_rich(data_lists)
    # out_list = render_any(data_lists, ctx)
    # print_rich(out_list)

    data_dict = {
        "request": {
            "headers": {
                "authorization": "Bearer ${token}",
                "x-user-id": "${user_id}"
            },
            "params": {
                "q": "${token}",
                "page": 1
            },
            "data": [
                {"user_id": "${user_id}"},
                {"meme": "uid=${user_id}, token=${token}"}
            ]
        }
    }
    print_rich(data_dict)
    out_list = render_any(data_dict, ctx)
    print_rich(out_list)




