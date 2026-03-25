import base64
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List

from requests import Response


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
class ResponseSnapshot:
    """
      承载所返回的响应信息
    """
    status_code: Optional[int] = None
    headers: Dict[str, Any] = field(default_factory=dict)
    cookies: Dict[str, Any] = field(default_factory=dict)
    elapsed_ms: Optional[float] = None  # 记录响应耗时, 单位毫秒
    encoding: Optional[str] = None  # 记录响应编码
    content_length: Optional[int] = None  # 记录响应体字节长度
    body_kind: str = "empty"  # 响应体数据类型
    body: Any = None  # 响应体数据
    body_truncated: bool = False  # 响应体数据是否被截断
    binary_summary: Optional[Dict[str, Any]] = None  # 记录二进制响应的摘要信息

    @classmethod
    def format_response(
        cls,
        response: Response,
        *,
        text_limit: int = 50000,
        json_limit: int = 50000,
        binary_limit: int = 128
    ) -> "ResponseSnapshot":
        """
          将 requests.Response 生成统一的响应快照结构对象
        :param response: 原始响应对象
        :param text_limit: 文本响应最大保留字符
        :param json_limit: JSON 响应最大保留字符
        :param binary_limit: 二进制预览最大字节数
        """
        status_code = getattr(response, "status_code", None)
        encoding = getattr(response, "encoding", None)

        # 记录响应头
        try:
            headers = dict(getattr(response, "headers", {}) or {})
        except Exception:
            headers = {"_error": "<headers 不可用>"}

        # 记录 cookies
        try:
            cookies = response.cookies.get_dict()
        except Exception:
            cookies = {"_error": "<cookies 不可用>"}

        # 记录耗时, 转为毫秒
        try:
            elapsed_ms = response.elapsed.total_seconds() * 1000
        except Exception:
            elapsed_ms = None

        # 获取 content bytes长度
        try:
            # response.content 属于 bytes 类型, 因此缺省值也用 bytes 类型, 为 None 时也转为空串
            content = getattr(response, "content", b"") or b""
            content_length = len(content)
        except Exception:
            content = b""
            content_length = None

        # 记录 json 数据
        try:
            body_kind = "json"
            json_data = response.json()
            json_text = json.dumps(json_data, ensure_ascii=False, indent=2, default=str)
            if len(json_text) > json_limit:
                # 超过限制则截断
                body = json_text[:json_limit]
                body_truncated = True
            else:
                # 没超过则保留原文
                body = json_data
                body_truncated = False

            return cls(
                status_code=status_code,
                headers=headers,
                cookies=cookies,
                elapsed_ms=elapsed_ms,
                encoding=encoding,
                content_length=content_length,
                body_kind=body_kind,
                body=body,
                body_truncated=body_truncated,
                binary_summary=None
            )
        except Exception:
            pass

        # 记录响应文本并截断
        try:
            body_kind = "text"
            text_data = getattr(response, "text", None)
            if text_data is not None:
                if len(text_data) > text_limit:
                    # 截断
                    body = text_data[:text_limit]
                    body_truncated = True
                else:
                    body = text_data
                    body_truncated = False

                return cls(
                    status_code=status_code,
                    headers=headers,
                    cookies=cookies,
                    elapsed_ms=elapsed_ms,
                    encoding=encoding,
                    content_length=content_length,
                    body_kind=body_kind,
                    body=body,
                    body_truncated=body_truncated,
                    binary_summary=None
                )
        except Exception:
            pass

        # 记录二进制摘要
        body_kind = "binary"
        # 若响应原始字节流非空, 则生成二进制摘要
        if content:
            preview = content[:binary_limit]
            binary_summary = {
                # 记录完整响应体的 sha256
                "sha256": hashlib.sha256(content).hexdigest(),
                # 记录若干自己的 base64 预览
                "preview_base64": base64.b64encode(preview).decode("ascii")
            }
            return cls(
                status_code=status_code,
                headers=headers,
                cookies=cookies,
                elapsed_ms=elapsed_ms,
                encoding=encoding,
                content_length=content_length,
                body_kind=body_kind,
                body=None,
                body_truncated=True,
                binary_summary=binary_summary
            )

        return cls(
            status_code=status_code,
            headers=headers,
            cookies=cookies,
            elapsed_ms=elapsed_ms,
            encoding=encoding,
            content_length=content_length,
            body_kind="empty",
            body=None,
            body_truncated=False,
            binary_summary=None
        )

    def to_dict(self) -> Dict[str, Any]:
        """
          用于日志/报告的打印
        """
        return {
            "status_code": self.status_code,
            "headers": self.headers,
            "cookies": self.cookies,
            "elapsed_ms": self.elapsed_ms,
            "encoding": self.encoding,
            "content_length": self.content_length,
            "body_kind": self.body_kind,
            "body": self.body,
            "body_truncated": self.body_truncated,
            "binary_summary": self.binary_summary,
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
    response: Optional[ResponseSnapshot] = None
    extract: Dict[str, Any] = field(default_factory=dict)
    assertions: List[AssertionResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """
          用于日志/报告的打印
        """
        return {
            "request": self.request.to_dict() if self.request else None,
            "response": self.response.to_dict() if self.response else None,
            "extract": self.extract,
            "assertions": [item.to_dict() for item in self.assertions],
        }


@dataclass
class CaseResult:
    """
      single.yaml 单接口用例的执行结果
    """
    api_id: str
    is_run: bool
    request: Optional[PreparedRequest] = None
    response: Optional[ResponseSnapshot] = None
    extract_out: Dict[str, Any] = field(default_factory=dict)
    assertions: List[AssertionResult] = field(default_factory=list)
    error: Optional[BaseException] = None
    cleanup_errors: List[Dict[str, Any]] = field(default_factory=list)  # 记录 cleanup 执行失败信息
    executed_auth_profiles: List[str] = field(default_factory=list)  # 记录当前生命周期实际执行过的公共前置
    executed_depends_keys: List[str] = field(default_factory=list)  # 记录当前生命周期实际执行过的 depends_on 去重键列表

    def to_dict(self) -> Dict[str, Any]:
        """
          用于日志/报告的打印
        """
        return {
            "api_id": self.api_id,
            "is_run": self.is_run,
            "request": self.request.to_dict() if self.request else None,
            "response": self.response.to_dict() if self.response else None,
            "extract_out": self.extract_out,
            "assertions": [a.to_dict() for a in self.assertions],
            "error": str(self.error) if self.error else None,
            "cleanup_error": self.cleanup_errors,
            "executed_auth_profiles": self.executed_auth_profiles,
            "executed_depends_keys": self.executed_depends_keys,
        }


@dataclass
class StepResult:
    """
      flow 业务流单个 step 的完整执行结果
    """
    step_id: str
    ref_api_id: str
    is_run: bool
    delay_run: Optional[float] = None
    request: Optional[PreparedRequest] = None
    response: Optional[ResponseSnapshot] = None
    extract_out: Dict[str, Any] = field(default_factory=dict)
    assertions: List[AssertionResult] = field(default_factory=list)
    error: Optional[BaseException] = None

    def to_dict(self) -> Dict[str, Any]:
        """
          用于日志/报告的打印
        """
        return {
            "step_id": self.step_id,
            "api_id": self.ref_api_id,
            "is_run": self.is_run,
            "delay_run": self.delay_run,
            "request": self.request.to_dict() if self.request else None,
            "response": self.response.to_dict() if self.response else None,
            "extract_out": self.extract_out,
            "assertions": [a.to_dict() for a in self.assertions],
            "error": str(self.error) if self.error else None,
        }


@dataclass
class FlowResult:
    """
      flow 业务流总执行结果, 包含多个 steps 的执行结果
    """
    flow_id: str
    is_run: bool
    steps: List[StepResult] = field(default_factory=list)
    error: Optional[BaseException] = None
    cleanup_errors: List[Dict[str, Any]] = field(default_factory=list)  # 记录 cleanup 执行失败信息
    executed_auth_profiles: List[str] = field(default_factory=list)  # 记录当前生命周期实际执行过的公共前置
    executed_depends_keys: List[str] = field(default_factory=list)  # 记录当前生命周期实际执行过的 depends_on 去重键列表

    def to_dict(self) -> Dict[str, Any]:
        """
          用于日志/报告的打印
        """
        return {
            "flow_id": self.flow_id,
            "is_run": self.is_run,
            "steps": [s.to_dict() for s in self.steps],
            "error": str(self.error) if self.error else None,
            "cleanup_error": self.cleanup_errors,
            "executed_auth_profiles": self.executed_auth_profiles,
            "executed_depends_keys": self.executed_depends_keys,
        }


