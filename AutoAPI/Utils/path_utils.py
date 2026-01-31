import os
import sys
from pathlib import Path
from typing import Union, Iterable

PathLike = Union[str, Path]


class PathTool:
    """ 路径工具: 最好依赖调用方传入的 __file__ """
    # 项目根目录判定用的 "标记文件/目录"
    DEFAULT_MARKERS = ("pyproject.toml", "run.py")

    def is_frozen(self) -> bool:
        return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")

    @staticmethod
    def script_path(file_path: PathLike) -> Path:
        """ 返回脚本文件的绝对路径

        :param file_path: 模块所属文件路径
        :return: Path 对象以便后续操作
        """
        return Path(file_path).resolve()

    @staticmethod
    def script_dir(file_path: PathLike) -> Path:
        """ 返回脚本所在目录的绝对路径

        :param file_path: 模块所属文件路径
        :return: Path 对象以便后续操作
        """
        return Path(file_path).resolve().parent

    @staticmethod
    def project_root(file_path: PathLike, markers: Union[Iterable[str], None] = None) -> Path:
        """ 返回脚本所在的项目根目录(从脚本所在目录向上查找)

        :param file_path: 模块所属文件路径
        :param markers: 项目根目录标记文件
        :return: Path 对象以便后续操作
        """
        start = PathTool.script_dir(file_path)
        ms = tuple(markers) if markers else PathTool.DEFAULT_MARKERS
        cur = start
        while True:
            # 如果当前目录下存在 标记文件, 返回该目录
            if any((cur / m).exists() for m in ms):
                return cur.resolve()
            # 若当前目录的父目录就是其本身, 则说明未找到
            if cur.parent == cur:
                raise FileNotFoundError(f"未在 {start} 的父层级找到项目根目录, 请在任一上层目录放置标记: {ms}")
            cur = cur.parent


if __name__ == "__main__":
    # 调试
    print(PathTool.project_root(__file__))
    print(Path(__file__).parent)
    print(os.path.abspath(__file__))
    print(os.path.dirname(os.path.abspath(__file__)))

