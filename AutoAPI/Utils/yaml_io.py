from pathlib import Path
from typing import Dict, List, Any, Union

import yaml

from Exceptions.AutoApiException import ValidationException, build_api_exception_context, ExceptionPhase, ExceptionCode
from Utils.log_utils import LoggerManager
from Utils.path_utils import PathTool
from Utils.print_pretty import print_rich

logger = LoggerManager.get_logger()

PathLike = Union[str, Path]


def _resolve_yaml_path(file_path: PathLike) -> Path:
    """
      解析 yaml 路径, 把传入的 file_path（可相对/可绝对）统一转换为 绝对路径, 避免依赖 cwd
    :param file_path: 文件路径
    :return: file_path 所在的绝对路径
    """
    # 将入参统一转换为 Path 对象，便于后续判断/拼接
    p = Path(file_path)

    # 若传入的是绝对路径, 直接规范化路径并返回
    if p.is_absolute():
        return p.resolve()

    # 使用本模块 __file__ 向上查找 markers，定位项目根目录
    project_root = PathTool.project_root(__file__)

    # 以项目根为基准拼接相对路径并 resolve 成绝对路径返回
    return (project_root / p).resolve()


def load_yaml_file(file_path: PathLike) -> Dict[str, Any]:
    """
      读取单文档 yaml, 不支持 `---` 多文档, 并强制顶层为 dict, 空文件返回 {}
    :param file_path: 文件路径
    :return: 返回解析后的 dict 数据
    """
    # 先将路径解析为稳定绝对路径，避免 cwd 不同导致找不到文件
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
                phase=ExceptionPhase.VALIDATION,
                error_code=ExceptionCode.VALIDATION_ERROR,
                message="YAML 单文档解析失败",
                reason=e,
                yaml_file=str(p),
                hint="请检查 YAML 语法、缩进、冒号、引号是否正确, 文档中是否出现 '---' 等问题"
            )
            raise ValidationException(error_context) from e

    # 若文件为空或内容为 null, 返回空 dict
    if data is None:
        return {}

    # 若顶层不是 dict（比如 list/str/int）
    if not isinstance(data, dict):
        # 构建明确异常上下文
        error_context = build_api_exception_context(
            phase=ExceptionPhase.VALIDATION,
            error_code=ExceptionCode.VALIDATION_ERROR,
            message="YAML 顶层结构非法",
            reason=f"期望为 dict 类型, 实际为 {type(data).__name__}",
            yaml_file=str(p),
            hint="请把 YAML 顶层结构改为 dict (键值对映射结构)"
        )
        raise ValidationException(error_context)

    return data


def load_yaml_documents(file_path: PathLike) -> List[Dict[str, Any]]:
    """
      读取多文档 yaml, 支持 `---`, 并强制每个文档顶层为 dict；空文档块会被跳过
    :param file_path: 文件路径
    :return: 返回解析后的 dict 数据
    """
    # 先将路径解析为稳定绝对路径，避免 cwd 不同导致找不到文件
    p = _resolve_yaml_path(file_path)

    # 文件不存在的情况
    if not p.exists():
        raise FileNotFoundError(f"未找到 YAML 文件：{p}")

    # utf-8 打开 yaml 文件
    with p.open("r", encoding="utf-8") as f:
        try:
            # 使用 safe_load_all 读取所有文档（支持 `---`）
            docs = list(yaml.safe_load_all(f))
        except yaml.YAMLError as e:
            # 构建明确异常上下文
            error_context = build_api_exception_context(
                phase=ExceptionPhase.VALIDATION,
                error_code=ExceptionCode.VALIDATION_ERROR,
                message="YAML 多文档解析失败",
                reason=str(e),
                yaml_file=str(p),
                hint="请检查每个文档块的 YAML 语法以及 '---' 分隔格式"
            )
            raise ValidationException(error_context) from e

    # 初始化输出列表, 用于收集 dict 文档
    out: List[Dict[str, Any]] = []

    # 遍历每个文档并从 1 开始编号，便于报错定位
    for i, d in enumerate(docs, start=1):
        # 若某个文档为空 (例如 `---` 后面没有内容), 则跳过空文档块，不纳入结果
        if d is None:
            continue
        # 若该文档顶层不是 dict, 则报错
        if not isinstance(d, dict):
            # 构建明确异常上下文
            error_context = build_api_exception_context(
                phase=ExceptionPhase.VALIDATION,
                error_code=ExceptionCode.VALIDATION_ERROR,
                message="YAML 顶层结构非法",
                reason=f"YAML 第 {i} 个文档顶层结构期望为 dict(键值对映射), 实际是 {type(d).__name__}",
                yaml_file=str(p),
                hint="请检查每个文档块的 YAML 语法以及 '---' 分隔格式"
            )
            raise ValidationException(error_context)
        out.append(d)

    return out


if __name__ == "__main__":
    # print_rich(load_yaml_file("Data/multiple.yaml"))
    print_rich(load_yaml_file("Data/single.yaml"))
    # print_rich(load_yaml_documents("Data/multiple.yaml"))
    # print_rich(load_yaml_documents("Data/multiple.yaml"))
