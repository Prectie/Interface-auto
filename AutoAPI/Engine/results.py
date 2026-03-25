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

    def to_dict(self) -> Dict[str, Any]:
        """
          用于日志/报告的打印
        """
        return {
            "method": self.method,
            "url": self.url,
            "kwargs": self.kwargs,
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
class ApiInvokeResult:
    """
      承载一次接口调用的公共执行结果

      注意:
         1.这属于内部返回的中间结果
         2.ApiStepRunner.run() 返回该结果
    """
    request: PreparedRequest
    response: Optional[Dict] = None
    extract: Dict[str, Any] = field(default_factory=dict)
    assertions: List[AssertionResult] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
          用于日志/报告的打印
        """
        return {
            "request": self.request,
            "response": self.response,
            "extract": self.extract,
            "assertions": self.assertions,
        }


@dataclass
class StepResult:
    """
      flow 业务流单个 step 的完整执行结果
    """
    step_name: str
    ref_api_id: str
    is_run: bool
    delay_run: Optional[float] = None
    request: Optional[PreparedRequest] = None
    response: Optional[Dict[str, Any]] = None
    extract_out: Dict[str, Any] = field(default_factory=dict)
    assertions: List[AssertionResult] = field(default_factory=list)
    error: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """
          用于日志/报告的打印
        """
        return {
            "step_name": self.step_name,
            "api_id": self.ref_api_id,
            "is_run": self.is_run,
            "delay_run": self.delay_run,
            "request": self.request.to_dict() if self.request else None,
            "response": self.response,
            "extract_out": self.extract_out,
            "assertions": [a.to_dict() for a in self.assertions],
            "error": self.error,
        }


@dataclass
class CaseResult:
    """
      single.yaml 单接口用例的执行结果
    """
    api_id: str
    is_run: bool
    request: Optional[PreparedRequest] = None
    response: Optional[Dict] = None
    extract_out: Dict[str, Any] = field(default_factory=dict)
    assertions: List[AssertionResult] = field(default_factory=list)
    error: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """
          用于日志/报告的打印
        """
        return {
            "api_id": self.api_id,
            "is_run": self.is_run,
            "request": self.request.to_dict() if self.request else None,
            "response": self.response,
            "extract_out": self.extract_out,
            "assertions": [a.to_dict() for a in self.assertions],
            "error": self.error,
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

    def to_dict(self) -> Dict[str, Any]:
        """
          用于日志/报告的打印
        """
        return {
            "flow_id": self.flow_id,
            "is_run": self.is_run,
            "steps": [s.to_dict() for s in self.steps],
            "error": self.error,
        }


