# -*- coding: utf-8 -*-  # 声明源码编码
import re
from typing import Any, Mapping, Dict, List  # 导入 any，用于支持合并任意类型
import copy  # 导入 copy，用于深拷贝避免引用共享


from Utils.print_pretty import print_rich
from Utils.yaml_io import load_yaml_file


def deep_merge(base, override):  # 深度合并函数
    # 目的/作用：递归合并 dict（用于 ref + override），非 dict 类型直接以 override 覆盖并深拷贝返回  # 方法目的说明
    if isinstance(base, dict) and isinstance(override, dict):  # 仅当两者都是 dict 才递归合并
        merged = copy.deepcopy(base)  # 深拷贝 base 作为输出，避免修改原对象
        for k, v in override.items():  # 遍历 override 的每个键值对
            if k in merged:  # 若 base 已存在该键
                merged[k] = deep_merge(merged[k], v)  # 递归合并更深层结构
            else:  # 若 base 不存在该键
                merged[k] = copy.deepcopy(v)  # 直接写入并深拷贝，避免引用共享
        return merged  # 返回合并结果
    return copy.deepcopy(override)  # 非 dict：直接返回 override 的深拷贝（覆盖语义）


def resolve_step_request(single_data: dict[str, any], step: dict[str, any]) -> dict[str, any]:  # 解析单步最终 request
    # 目的/作用：通过 step.ref 从 single.apis 找到 base_request，再用 step.override.request 覆盖生成最终 request  # 方法目的说明

    apis = single_data.get("apis", {})  # 获取接口库 apis 映射，找不到则给空 dict
    ref = str(step.get("ref", "")).strip()  # 读取 step.ref 并做 strip，避免空格导致查不到

    base_api = apis[ref]  # 获取接口库中的 api_def
    base_request = base_api.get("request", {})  # 获取 api_def.request，找不到则空 dict

    override = step.get("override", {}) or {}  # 获取 override，若为 None 则转为空 dict

    override_request = override.get("request", {}) or {}  # 获取 override.request，若无则空 dict

    final_request = deep_merge(base_request, override_request)  # 关键：在 request 层级做覆盖合并
    return final_request  # 返回该 step 的最终 request（已覆盖）


class var_resolve_error(Exception):  # 定义变量解析异常（用于输出中文错误）
    """
    变量解析异常

    用途：
        当 ${var} 无法从 ctx 中解析到真实值时抛出该异常，便于统一捕获与定位问题。  # 异常用途说明
    """  # 类 docstring 结束
    pass  # 该异常类无需额外逻辑，仅作为语义化异常类型


_var_pattern = re.compile(r"\$\{([^}]+)\}")  # 编译正则：匹配 ${xxx}，xxx 不允许包含 }  # 正则说明


def render_any(data: Any, ctx: Mapping[str, Any], path: str = "$") -> Any:  # 渲染任意结构入口
    """
    递归渲染任意结构，把其中的 ${var} 替换为 ctx 中的真实值（用于发请求/断言/提取前的变量展开）。

    规则：
        - 若遇到占位符变量缺失，直接抛出中文异常（不提供开关）。  # 规则说明

    :param data: 待渲染的数据结构；可以是 dict/list/str/int/bool/None 等任意类型。  # 参数说明
    :param ctx: 上下文变量容器（通常传 ctx.snapshot() 得到的 dict 或 Mapping）。  # 参数说明
    :param path: 定位路径（用于报错时指出出问题的字段位置）；默认 "$"。  # 参数说明
    :return: 渲染后的新结构（输入是 dict/list 会返回新对象；非字符串基础类型原样返回）。  # 返回值说明
    :raises var_resolve_error: 当占位符变量缺失时抛出。  # 异常说明
    """  # docstring 结束

    if isinstance(data, str):  # 若当前节点是字符串  # 分支说明
        return render_str(text=data, ctx=ctx, path=path)  # 渲染字符串并返回  # 调用说明

    if isinstance(data, dict):  # 若当前节点是字典（yaml 常见结构）  # 分支说明
        out: Dict[str, Any] = {}  # 初始化输出字典，保存渲染后的 key/value  # 变量说明
        for k, v in data.items():  # 遍历字典键值对  # 循环说明
            child_path = f"{path}.{k}"  # 拼接子路径，便于报错定位到具体字段  # 路径说明
            out[k] = render_any(data=v, ctx=ctx, path=child_path)  # 递归渲染 value  # 递归说明
        return out  # 返回渲染后的新字典（不污染原数据）  # 返回说明

    if isinstance(data, list):  # 若当前节点是列表（steps/assert/extract 常见）  # 分支说明
        out_list: List[Any] = []  # 初始化输出列表，用于保存渲染后的元素  # 变量说明
        for i, item in enumerate(data):  # 遍历列表元素并拿到索引  # 循环说明
            child_path = f"{path}[{i}]"  # 拼接子路径，便于定位到具体下标  # 路径说明
            out_list.append(render_any(data=item, ctx=ctx, path=child_path))  # 递归渲染元素  # 递归说明
        return out_list  # 返回渲染后的新列表（不污染原数据）  # 返回说明

    return data  # 其他类型（int/bool/None/float 等）无需渲染，直接返回  # 返回说明


def render_str(text: str, ctx: Mapping[str, Any], path: str = "$") -> Any:  # 渲染字符串
    """
    渲染字符串中的 ${var} 占位符。

    规则：
        1) 若字符串整体就是一个占位符（例如 "${user_id}"），则返回 ctx 中变量的“原类型值”（int/bool/dict...）。  # 规则说明
        2) 若占位符嵌在字符串中（例如 "bearer ${token}"），则把变量值转换为 str 后替换进去，返回最终字符串。  # 规则说明
        3) 若变量缺失，直接抛中文异常（不提供开关）。  # 规则说明

    :param text: 原始字符串（可能包含 ${var}）。  # 参数说明
    :param ctx: 上下文变量容器（Mapping）。  # 参数说明
    :param path: 字段定位路径，用于异常提示。  # 参数说明
    :return: 若为整值引用返回变量原类型；否则返回替换后的字符串。  # 返回值说明
    :raises var_resolve_error: 当占位符变量缺失时抛出。  # 异常说明
    """  # docstring 结束

    stripped = text.strip()  # 去掉首尾空白用于整值匹配（不改变原 text 用于替换）  # 变量说明
    m = _var_pattern.fullmatch(stripped)  # 判断是否为“整值引用”（字符串完全等于 ${var}）  # 匹配说明
    if m:  # 若是整值引用  # 分支说明
        var_name = m.group(1).strip()  # 提取变量名并去掉空白  # 变量说明
        return _get_var_value(var_name=var_name, ctx=ctx, path=path, template=text)  # 返回原类型值  # 调用说明

    def _replace(match: re.Match) -> str:  # 定义替换函数：逐个处理 ${var}  # 内部函数说明
        """
        替换回调：用于把每个 ${var} 替换成字符串形式的真实值。

        :param match: 正则匹配对象，match.group(1) 为变量名。  # 参数说明
        :return: 替换后的字符串片段（必须是 str）。  # 返回值说明
        :raises var_resolve_error: 当占位符变量缺失时抛出。  # 异常说明
        """  # docstring 结束
        var_name = match.group(1).strip()  # 提取变量名  # 变量说明
        value = _get_var_value(var_name=var_name, ctx=ctx, path=path, template=text)  # 获取变量真实值  # 调用说明
        return str(value)  # 内嵌替换时统一转为字符串进行拼接  # 返回说明

    rendered = _var_pattern.sub(_replace, text)  # 替换字符串中所有 ${var}，得到渲染后的文本  # 替换说明
    return rendered  # 返回渲染后的字符串  # 返回说明


def _get_var_value(var_name: str, ctx: Mapping[str, Any], path: str, template: str) -> Any:  # 获取变量值
    """
    从 ctx 中获取变量值，支持简单 key 与点号路径（如 a.b.c）。

    :param var_name: 变量名（${...} 内部内容），例如 "token" 或 "a.b.c"。  # 参数说明
    :param ctx: 上下文变量容器（Mapping）。  # 参数说明
    :param path: 当前字段定位路径，用于异常信息定位。  # 参数说明
    :param template: 原始模板字符串，用于异常中回显，便于排查。  # 参数说明
    :return: 解析到的变量值（可能是 str/int/bool/dict/list 等任意类型）。  # 返回值说明
    :raises var_resolve_error: 当变量缺失时抛出中文异常。  # 异常说明
    """  # docstring 结束

    if var_name in ctx:  # 若 ctx 顶层直接存在该 key（你当前 yaml 大多是这种）  # 分支说明
        return ctx[var_name]  # 直接返回对应值（保留原类型）  # 返回说明

    if "." in var_name:  # 若变量名包含点号路径（可选增强）  # 分支说明
        cur: Any = ctx  # 从 ctx 开始逐层向下取值  # 变量说明
        for part in var_name.split("."):  # 按点号拆分路径片段  # 循环说明
            if isinstance(cur, Mapping) and part in cur:  # 当前层是映射且包含该 key  # 条件说明
                cur = cur[part]  # 下钻到下一层  # 赋值说明
            else:  # 中间某一层不存在  # 分支说明
                raise var_resolve_error(  # 变量缺失直接报错（中文）  # 异常说明
                    f"变量解析失败：未找到变量 `${{{var_name}}}`（字段路径：{path}），"  # 提示缺失变量与字段路径  # 文本说明
                    f"模板值：{template}；缺失片段：{part}"  # 提示原模板与缺失片段  # 文本说明
                )  # 异常构造结束  # 结束说明
        return cur  # 路径解析成功：返回最终值（保留原类型）  # 返回说明

    raise var_resolve_error(  # 变量不存在且不是点号路径：直接报错  # 异常说明
        f"变量解析失败：未找到变量 `${{{var_name}}}`（字段路径：{path}），模板值：{template}"  # 异常文本  # 文本说明
    )  # 异常构造结束  # 结束说明


if __name__ == "__main__":  # 主入口，仅用于本地最小验证
    # single_data = load_yaml_file("Data/single.yaml")  # 真实读取 single.yaml（接口库）
    # multiple_data = load_yaml_file("Data/multiple.yaml")  # 真实读取 multiple.yaml（业务流）
    #
    # steps = multiple_data.get("steps", [])  # 获取 steps 列表
    #
    # first_step = steps[0]  # 取第一步用于最小验证
    #
    # req = resolve_step_request(single_data=single_data, step=first_step)  # 解析第一步最终 request
    # print_rich(req)  # 打印结果：你会看到 override 的字段已经覆盖到 request 里
    ctx = {
        "token": "t123",
        "user_id": 1001
    }

    data_str_full = "${token}"
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




