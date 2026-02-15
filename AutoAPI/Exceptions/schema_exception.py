from typing import Any


class YamlSchemaException(Exception):
    """
      作用:
        1. 校验 YAML 结构是否正确
        2. 提供 file/where/raw/hint 维度的上下文信息, 报错直接定位到 YAML 具体位置
    """
    def __init__(
        self,
        message: str,
        *,
        file_path: str = None,
        where: str = None,
        raw: Any = None,
        hint: str = None
    ):
        self.message = message
        self.file_path = file_path
        self.where = where
        self.raw = raw
        self.hint = hint

        super().__init__(self._format())

    def _format(self) -> str:
        """
          作用：
            1. 将报错信息进行组合并统一格式
        :return: 格式化后的错误文本
        """
        lines = [f"YAML 结构错误: {self.message}"]

        if self.file_path is not None:
            lines.append(f"文件: {self.file_path}")

        if self.where is not None:
            lines.append(f"位置: {self.where}")

        if self.raw is not None:
            lines.append(f"传入的原始数据: {self.raw}")

        if self.hint is not None:
            lines.append(f"建议: {self.hint}")

        return "\n".join(lines)

    @classmethod
    def at(
        cls,
        message: str,
        *,
        file_path: str = None,
        where: str = None,
        raw: Any = None,
        hint: str = None
    ):
        return cls(message, file_path=file_path, where=where, raw=raw, hint=hint)
