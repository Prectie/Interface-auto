from typing import Any, Literal, Optional

basic_type = Literal["text", "number", "bool"]


class AssertTool:
    def assert_basic(
        self,
        actual: Any,
        expected: Any,
        op: str = "==",
        *,
        value_type: basic_type = "text",
        message: Optional[str] = None
    ):
        comparators = {
            "==", lambda x, y: x == y,
            "!=", lambda x, y: x != y,
            ">=", lambda x, y: x >= y,
            "<=", lambda x, y: x <= y,
            ">", lambda x, y: x > y,
            "<", lambda x, y: x < y,
            "in", lambda x, y: y in x,
            "not in", lambda x, y: y not in x,
        }

        
