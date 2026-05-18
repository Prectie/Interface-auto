import copy
from typing import Optional, Any


class RuntimeContext:
    """
      本类用于保存公共数据(env/static) 与动态数据(token/提取变量等)
    """
    def __init__(self, initial: Optional[dict[str, Any]] = None):
        """
          初始化上下文对象, 存储所有数据

        :param initial: 已解析好的数据
        """
        self._data = initial or {}

    def set(self, key: str, value):
        """
          把 token/中间变量/运行数据写入上下文, 供后续渲染/断言/提取使用

        :param key: 键
        :param value: 值
        """
        self._data[key] = value

    def update(self, mapping: dict[str, Any]):
        """
          批量注入公共数据 或 合并一批提取结果, 减少多次 set 调用

        :param mapping: 批量 dict 数据
        """
        self._data.update(mapping)

    def get(self, key: str, default: Any = None):
        """
          读取上下文变量, 若不存在则返回 default

        :param key: 需要读取的 key
        :param default: key 不存在则返回该值
        :return: 返回 key 对应的 value; key 不存在返回 default
        """
        return self._data.get(key, default)

    def pop(self, key: str, default: Any = None):
        """
          删除临时变量并返回其值

        :param key: 需要删除的 key
        :param default: key 不存在则返回该值
        :return: 返回 key 对应的 value; key 不存在返回 default
        """
        return self._data.pop(key, default)

    def snapshot(self):
        """
          返回运行 context 的深拷贝, 防止外部直接修改
        :return: 返回运行时数据
        """
        return copy.deepcopy(self._data)

    def fork(self) -> "RuntimeContext":
        """
          复制当前上下文生成子上下文, 可以看作是一个事务, 在子上下文完成事件后, 再合并到原上下文
        :return: 返回一个 RuntimeContext 对象
        """
        return RuntimeContext(self.snapshot())

    
