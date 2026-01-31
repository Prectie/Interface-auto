import itertools
import json
import os.path
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Any, Iterable, Union

import yaml
from Utils.log_utils import LoggerManager
from Utils.path_utils import PathTool

logger = LoggerManager.get_logger()

PathLike = Union[str, Path]  # 定义路径类型别名，统一入参类型（str 或 Path）


class YamlSchemaError(Exception):  # 定义 yaml 结构异常类型
    # 目的/作用：当 yaml 顶层不是 dict 或必填字段缺失时，用该异常统一抛错定位  # 异常用途说明
    pass  # 占位，无额外实现


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
        raise FileNotFoundError(f"未找到 YAML 文件：{p}")  # 抛出中文错误信息，提示文件缺失
    with p.open("r", encoding="utf-8") as f:  # 以 utf-8 编码打开 yaml 文件
        try:  # 捕获 yaml 解析异常，输出更友好的中文提示
            data = yaml.safe_load(f)  # 读取单文档 YAML（若出现 `---` 多文档会报错）
        except yaml.YAMLError as e:  # 捕获 PyYAML 的解析错误
            raise YamlSchemaError(f"YAML 解析失败（单文档模式），文件：{p}，错误：{e}") from e  # 抛出中文结构异常并保留原异常链
    if data is None:  # 若文件为空或内容为 null
        return {}  # 返回空 dict，保证调用侧可安全 .get()
    if not isinstance(data, dict):  # 若顶层不是 dict（比如 list/str/int）
        raise YamlSchemaError(f"YAML 顶层结构必须是 dict（键值对映射），实际是 {type(data).__name__}，文件：{p}")  # 抛中文结构异常
    return data  # 返回解析后的 dict 数据

if __name__ == "__main__":
    print(load_yaml_file("Data/single.yaml"))
