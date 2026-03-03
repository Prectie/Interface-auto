from rich import print as rprint
from rich.pretty import Pretty


def print_rich(data):
    """
      功能说明：使用 rich 美化打印 python 对象，适合调试复杂嵌套结构
    """
    rprint(Pretty(data, expand_all=True))
