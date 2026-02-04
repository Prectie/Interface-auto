from rich import print as rprint  # 导入 rich 的彩色打印
from rich.pretty import Pretty  # 导入 pretty 渲染器


def print_rich(data):  # 定义函数：rich 风格输出
    """功能说明：使用 rich 美化打印 python 对象，适合调试复杂嵌套结构。"""  # 函数用途说明
    rprint(Pretty(data, expand_all=True))  # 展开所有层级并打印（更直观）
