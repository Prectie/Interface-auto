from dataclasses import dataclass
from typing import Optional, Any, Dict


@dataclass
class RuntimeErrorDetail:
    where: str
    api_id: Optional[str] = None
    step_name: Optional[str] = None
    message: str = ""
    extra: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "where": self.where,
            "api_id": self.api_id,
            "step_name": self.step_name,
            "message": self.message,
            "extra": self.extra,
        }

    def format(self) -> str:
        head = f"where={self.where}"
        if self.api_id:
            head += f", api_id={self.api_id}"
        if self.step_name:
            head += f", step_name={self.step_name}"

        msg = self.message or "runtime error"
        return f"{msg} {head}"


class ApiRuntimeError(Exception):
    def __init__(self, detail: RuntimeErrorDetail):
        self.detail = detail
        super().__init__(detail.format())

    def __str__(self) -> str:
        return self.detail.format()


class RequestBuildError(ApiRuntimeError):
    """"""


class TransportError(ApiRuntimeError):
    """"""


class AssertionFailed(ApiRuntimeError):
    """"""


class AuthProfileError(ApiRuntimeError):
    """"""


class ResponseProcessError(ApiRuntimeError):
    """"""

