from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List


@dataclass
class PreparedRequest:
    """
      承载 "已解析完成, 可直接发送" 的请求信息
    """
    method: str
    url: str
    kwargs: Dict[str, Any]
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
          用于日志/报告的打印
        """
        return {
            "method": self.method,
            "url": self.url,
            "kwargs": self.kwargs,
            "meta": self.meta
        }


@dataclass
class AssertionResult:
    """
      承载单条断言的判定结果
    """
    passed: bool
    rule: Dict[str, Any]
    actual: Any = None
    expected: Any = None
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """
          用于日志/报告的打印
        """
        return {
            "passed": self.passed,
            "rule": self.rule,
            "actual": self.actual,
            "expected": self.expected,
            "message": self.message
        }


@dataclass
class StepResult:
    """
      flow 业务流单个 step 的完整执行结果
    """
    step_name: str
    api_id: str
    is_run: bool
    request: Optional[PreparedRequest] = None
    status_code: Optional[int] = None
    response_text: Optional[str] = None
    extract_out: Dict[str, Any] = field(default_factory=dict)
    assertions: List[AssertionResult] = field(default_factory=list)
    error: Optional[Dict[str, Any]] = None
    elapsed_ms: Optional[float] = None  # 耗时, 有疑问：allure报告已经内涵了耗时统计，这里还需要吗？

    def to_dict(self) -> Dict[str, Any]:
        """
          用于日志/报告的打印
        """
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
    """
      single.yaml 单接口用例的执行结果
    """
    api_id: str
    is_run: bool
    request: Optional[PreparedRequest] = None
    status_code: Optional[int] = None
    response_text: Optional[str] = None
    extract_out: Dict[str, Any] = field(default_factory=dict)
    assertions: List[AssertionResult] = field(default_factory=list)
    error: Optional[Dict[str, Any]] = None
    elapsed_ms: Optional[float] = None  # 耗时, 有疑问：allure报告已经内涵了耗时统计，这里还需要吗？

    def to_dict(self) -> Dict[str, Any]:
        """
          用于日志/报告的打印
        """
        return {
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
class FlowResult:
    """
      flow 业务流总执行结果, 包含多个 steps 的执行结果
    """
    flow_id: str
    is_run: bool
    steps: List[StepResult] = field(default_factory=list)
    error: Optional[Dict[str, Any]] = None
    elapsed_ms: Optional[float] = None  # 耗时, 有疑问：allure报告已经内涵了耗时统计，这里还需要吗？

    def to_dict(self) -> Dict[str, Any]:
        """
          用于日志/报告的打印
        """
        return {
            "flow_id": self.flow_id,
            "is_run": self.is_run,
            "steps": [s.to_dict() for s in self.steps],
            "error": self.error,
            "elapsed_ms": self.elapsed_ms,
        }


