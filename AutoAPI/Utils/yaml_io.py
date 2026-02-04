import itertools
import json
import os.path
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Any, Iterable, Union

import yaml

from Exceptions.schema_exception import YamlSchemaException
from Utils.log_utils import LoggerManager
from Utils.path_utils import PathTool
from Utils.print_pretty import print_rich

logger = LoggerManager.get_logger()

PathLike = Union[str, Path]


def _resolve_yaml_path(file_path: PathLike) -> Path:  # 解析 yaml 路径（内部工具函数）
    # 目的/作用：把传入的 file_path（可相对/可绝对）统一转换为“稳定绝对路径”，避免依赖 cwd  # 方法目的说明
    p = Path(file_path)  # 将入参统一转换为 Path 对象，便于后续判断/拼接
    if p.is_absolute():  # 若传入的是绝对路径
        return p.resolve()  # 直接 resolve 规范化路径（消除 .. 等片段）并返回
    project_root = PathTool.project_root(__file__)  # 使用本模块 __file__ 向上查找 markers，定位项目根目录
    return (project_root / p).resolve()  # 以项目根为基准拼接相对路径并 resolve 成绝对路径返回


def load_yaml_file(file_path: PathLike) -> Dict[str, Any]:  # 读取单文档 yaml（顶层强制 dict）
    # 目的/作用：读取单个 YAML 文档（不支持 `---` 多文档），并强制顶层为 dict；空文件返回 {}  # 方法目的说明
    p = _resolve_yaml_path(file_path)  # 先将路径解析为稳定绝对路径，避免 cwd 不同导致找不到文件
    if not p.exists():  # 若文件不存在
        raise FileNotFoundError(f"未找到 YAML 文件：{p}")
    with p.open("r", encoding="utf-8") as f:  # 以 utf-8 编码打开 yaml 文件
        try:
            data = yaml.safe_load(f)  # 读取单文档 YAML（若出现 `---` 多文档会报错）
        except yaml.YAMLError as e:  # 捕获 PyYAML 的解析错误
            raise YamlSchemaException(f"YAML 解析失败（单文档模式），文件：{p}，错误：{e}") from e
    if data is None:  # 若文件为空或内容为 null
        return {}  # 返回空 dict，保证调用侧可安全 .get()
    if not isinstance(data, dict):  # 若顶层不是 dict（比如 list/str/int）
        raise YamlSchemaException(f"YAML 顶层结构必须是 dict（键值对映射），实际是 {type(data).__name__}，文件：{p}")  # 抛中文结构异常
    return data  # 返回解析后的 dict 数据


def load_yaml_documents(file_path: PathLike) -> List[Dict[str, Any]]:  # 读取多文档 yaml（支持 `---`）
    # 目的/作用：读取包含 `---` 的多文档 YAML，并强制“每个文档顶层为 dict”；空文档块会被跳过  # 方法目的说明
    p = _resolve_yaml_path(file_path)  # 先将路径解析为稳定绝对路径，避免 cwd 不同导致找不到文件
    if not p.exists():  # 若文件不存在
        raise FileNotFoundError(f"未找到 YAML 文件：{p}")  # 抛出中文错误信息，提示文件缺失
    with p.open("r", encoding="utf-8") as f:  # 以 utf-8 编码打开 yaml 文件
        try:  # 捕获 yaml 解析异常，输出更友好的中文提示
            docs = list(yaml.safe_load_all(f))  # 使用 safe_load_all 读取所有文档（支持 `---`）
        except yaml.YAMLError as e:  # 捕获 PyYAML 的解析错误
            raise YamlSchemaException(f"YAML 解析失败（多文档模式），文件：{p}，错误：{e}") from e  # 抛出中文结构异常并保留原异常链
    out: List[Dict[str, Any]] = []  # 初始化输出列表，用于收集合法的 dict 文档
    for i, d in enumerate(docs, start=1):  # 遍历每个文档并从 1 开始编号，便于报错定位
        if d is None:  # 若某个文档为空（例如 `---` 后面没有内容）
            continue  # 跳过空文档块，不纳入结果
        if not isinstance(d, dict):  # 若该文档顶层不是 dict
            raise YamlSchemaException(f"YAML 第 {i} 个文档顶层结构必须是 dict（键值对映射），实际是 {type(d).__name__}，文件：{p}")  # 抛中文结构异常
        out.append(d)  # 将该文档 dict 追加到输出列表
    return out  # 返回多文档 dict 列表


if __name__ == "__main__":
    # print_rich(load_yaml_file("Data/single.yaml"))
    print_rich(load_yaml_documents("Data/multiple.yaml"))
