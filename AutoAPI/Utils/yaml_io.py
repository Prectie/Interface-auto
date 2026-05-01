from pathlib import Path
from typing import Dict, Any, Union

import yaml

from Exceptions.AutoApiException import build_api_exception_context, ExceptionCode, YamlIOException
from Utils.log_utils import LoggerManager
from Utils.path_utils import PathTool

logger = LoggerManager.get_logger()

PathLike = Union[str, Path]


def _resolve_yaml_path(file_path: PathLike) -> Path:
    """
      解析 yaml 路径, 把传入的 file_path（可相对/可绝对）统一转换为 绝对路径, 避免依赖 cwd
    :param file_path: 文件路径
    :return: file_path 所在的绝对路径
    """
    # 将入参统一转换为 Path 对象,便于后续判断/拼接
    p = Path(file_path)

    # 若传入的是绝对路径, 直接规范化路径并返回
    if p.is_absolute():
        return p.resolve()

    # 使用本模块 __file__ 向上查找 markers,定位项目根目录
    project_root = PathTool.project_root(__file__)

    # 以项目根为基准拼接相对路径并 resolve 成绝对路径返回
    return (project_root / p).resolve()


def load_yaml_file(file_path: PathLike) -> Dict[str, Any]:
    """
      读取单文档 yaml, 不支持 `---` 多文档, 并强制顶层为 dict, 空文件返回 {}
    :param file_path: 文件路径
    :return: 返回解析后的 dict 数据
    """
    # 先将路径解析为稳定绝对路径,避免 cwd 不同导致找不到文件
    p = _resolve_yaml_path(file_path)

    # 文件不存在的情况
    if not p.exists():
        raise FileNotFoundError(f"未找到 YAML 文件：{p}")

    # utf-8 打开 yaml 文件
    with p.open("r", encoding="utf-8") as f:
        try:
            # 读取单文档 YAML（若出现 `---` 多文档会报错）
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            # 构建明确异常上下文
            error_context = build_api_exception_context(
                error_code=ExceptionCode.YAML_IO_ERROR,
                message="YAML 单文档解析失败",
                reason=e,
                yaml_file=p.name,
                hint="请检查 YAML 语法、缩进、冒号、引号是否正确, 文档中是否出现 '---' 等问题"
            )
            raise YamlIOException(error_context) from e

    # 若文件为空或内容为 null, 返回空 dict
    if data is None:
        return {}

    # 若顶层不是 dict（比如 list/str/int）
    if not isinstance(data, dict):
        # 构建明确异常上下文
        error_context = build_api_exception_context(
            error_code=ExceptionCode.YAML_IO_ERROR,
            message="YAML 顶层结构非法",
            reason=f"期望为 dict 类型, 实际为 {type(data).__name__}",
            yaml_file=p.name,
            hint="请把 YAML 顶层结构改为 dict (键值对映射结构)"
        )
        raise YamlIOException(error_context)

    return data
