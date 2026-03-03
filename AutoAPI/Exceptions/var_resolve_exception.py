import difflib
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Sequence, Iterable


@dataclass
class VarResolveErrorDetail:
    """
      负责承载一次变量解析失败的上下文信息, 便于日志/报告结构化展示

    类变量说明:
      - var_name: 变量名 (${...} 内部内容, 例如 "token" 或 "a.b.c")
      - path: 字段路径 (例如 "$.request.headers.auth"), 用于定位 yaml 的哪个字段出错
      - template: 原始模板字符串 (包含 ${...} 的原文)
      - reason: 失败原因
      - missing_part: 点号路径缺失片段 (例如 "a.b.c" 中缺 "b"), 可选
      - ctx_keys: ctx 顶层可用 key 预览 (截断预览, 从 _get_var_value 里的 ctx 获取得到), 可选
      - level_keys: 点号路径某一层可用 key 预览 (截断预览), 可选
          例如: ctx = {"user": {"name": "tom", "age": 18}}
          实际写的是 ${user.profile.age} 缺 profile 时, cur 已经是 ctx["user"], level_keys = ["name, "age"] (此处需要结合代码理解)
          就能提示想写的是 ${user.age} 或者缺少了 profile
      - suggestions: 相似变量名建议 (截断预览), 可选
    """
    var_name: str
    path: str
    template: str
    reason: str
    missing_part: Optional[str] = None
    ctx_keys: Optional[List[str]] = None
    level_keys: Optional[List[str]] = None
    suggestions: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """
          把 detail 转为 dict, 方便上层统一打印/写入报告
        :return: 返回包含全部字段的 dict
        """
        return {
            "var_name": self.var_name,
            "path": self.path,
            "template": self.template,
            "reason": self.reason,
            "missing_part": self.missing_part,
            "ctx_keys": self.ctx_keys,
            "level_keys": self.level_keys,
            "suggestions": self.suggestions,
        }


class VarResolveError(Exception):
    """
      当 ${var} 无法从 ctx 中解析到真实值时抛出该异常，便于统一捕获与定位问题
    """
    def __init__(self, detail: VarResolveErrorDetail):
        """
          保存 detail 并生成更友好的异常文本
        :param detail: 结构化异常信息
        """
        self.detail = detail
        super()

    def __str__(self) -> str:
        """
          将 detail 格式化为更友好的错误信息
        """
        head = f"变量解析失败, 原因: {self.detail.reason}"
        core = f"变量=${{{self.detail.var_name}}}; 字段路径={self.detail.path}; 原模板={self.detail.template!r}"

        # 初始化补充信息列表
        parts = []
        # 若存在缺失片段
        if self.detail.missing_part:
            parts.append(f"缺失片段={self.detail.missing_part!r}")
        # 若存在 ctx 顶层 key
        if self.detail.ctx_keys:
            parts.append(f"可用变量(ctx顶层)={self.detail.ctx_keys}")
        # 若存在当前层 key
        if self.detail.level_keys:
            parts.append(f"当层可用key={self.detail.level_keys}")
        # 若存在相似建议
        if self.detail.suggestions:
            parts.append(f"相似建议={self.detail.suggestions}")

        # 拼接补充信息尾部(若无 parts 则为空)
        tail = ("; " + "; ".join(parts)) if parts else ""

        # 返回最终异常信息字符串
        return f"{head}; {core}{tail}"


def preview_keys(keys: Iterable[Any], limit: int = 20) -> List[str]:
    """
      生成 key 列表概览, 把 keys 截断为可展示的预览列表, 避免 key 过多
    :param keys: 任意可迭代 key 对象
    :param limit: 最多展示多少个
    :return: 返回截断后的 key 字符串列表
    """
    # 初始化输出列表
    out = []
    key_list = list(keys)
    # 只取前 limit 个key
    for k in key_list[:limit]:
        out.append(str(k))
    # 若 key 数量超过 limit, 加省略标记
    if len(key_list) > limit:
        out.append("...")
    return out


def suggest_names(name: str, candidates: Sequence[str], limit: int = 5) -> List[str]:
    """
      当变量名拼错时, 给出相似候选建议, 提升排错效率
    :param name: 待匹配名称
    :param candidates: 候选集合
    :param limit: 最多返回多少条建议
    :return: 返回建议列表(可能为空)
    """
    # 捕获 difflib 异常
    try:
        # 返回相似列表
        return difflib.get_close_matches(name, list(candidates), n=limit, cutoff=0.6)
    # 若 difflib 计算异常, 返回空列表
    except Exception:
        return []


