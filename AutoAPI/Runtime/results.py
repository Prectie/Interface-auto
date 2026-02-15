from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List


@dataclass
class PreparedRequest:
    method: str
    url: str
    kwargs: Dict[str, Any]
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "url": self.url,
            "kwargs": self.kwargs,
            "meta": self.meta
        }


@dataclass
class AssertionResult:
    passed: bool
    rule: Dict[str, Any]
    actual: Any = None
    expected: Any = None
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "rule": self.rule,
            "actual": self.actual,
            "expected": self.expected,
            "message": self.message
        }


@dataclass
class StepResult:
    step_name: str
    api_id: str
    is_run: bool
    request: Optional[PreparedRequest] = None
    status_code: Optional[int] = None
    response_text: Optional[str] = None
    extract_out: Dict[str, Any] = field(default_factory=dict)
    assertions: List[AssertionResult] = field(default_factory=list)
    error: Optional[str] = None
    elapsed_ms: Optional[float] = None  # 耗时, 有疑问：allure报告已经内涵了耗时统计，这里还需要吗？

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_name": self.step_name,
            "api_id": self.api_id,
            "is_run": self.is_run,
            "request": self.request.to_dict() if self.request else None,
            "status_code": self.status_code,
            "response_text": self.response_text,
            "extract_out": self.extract_out,
            "assertions": [a.to_dict() for a in self.assertions],
            "error": self.error,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass
class CaseResult:
    api_id: str
    case_id: str
    is_run: bool
    request: Optional[PreparedRequest] = None
    status_code: Optional[int] = None
    response_text: Optional[str] = None
    extract_out: Dict[str, Any] = field(default_factory=dict)
    assertions: List[AssertionResult] = field(default_factory=list)
    error: Optional[str] = None
    elapsed_ms: Optional[float] = None  # 耗时, 有疑问：allure报告已经内涵了耗时统计，这里还需要吗？

    def to_dict(self) -> Dict[str, Any]:
        return {
            "api_id": self.api_id,
            "case_id": self.case_id,
            "is_run": self.is_run,
            "request": self.request.to_dict() if self.request else None,
            "status_code": self.status_code,
            "response_text": self.response_text,
            "extract_out": self.extract_out,
            "assertions": [a.to_dict() for a in self.assertions],
            "error": self.error,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass
class FlowResult:
    flow_id: str
    is_run: bool
    steps: List[StepResult] = field(default_factory=list)
    error: Optional[str] = None
    elapsed_ms: Optional[float] = None  # 耗时, 有疑问：allure报告已经内涵了耗时统计，这里还需要吗？

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "is_run": self.is_run,
            "steps": [s.to_dict() for s in self.steps],
            "error": self.error,
            "elapsed_ms": self.elapsed_ms,
        }


