import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any

from Utils.print_pretty import print_rich


class ExceptionPhase(str, Enum):
    """
      统一错误阶段枚举
    """
    # 读取/校验 YAML 阶段
    VALIDATION = "validation"
    # 变量渲染阶段
    RENDER = "render"
    # 构建请求阶段
    REQUEST_BUILD = "request_build"
    # 发送请求阶段
    REQUEST_SEND = "request_send"
    # 响应数据提取阶段
    RESPONSE_EXTRACT = "response_extract"
    # 断言执行阶段
    ASSERT = "assert"
    # 流程编排阶段
    PIPELINE = "pipeline"


class ExceptionCode(str, Enum):
    """
      错误码枚举
    """
    # TODO 可以更具体, 比如 YAML 字段没有找到, 现阶段先设置以下几个
    # 读取/校验 YAML 错误
    VALIDATION_ERROR = "VALIDATION_ERROR"
    # 变量渲染错误
    VAR_RENDER_ERROR = "VAR_RENDER_ERROR"
    # 断言错误
    ASSERT_ERROR = "ASSERT_ERROR"
    # 构建请求错误
    REQUEST_BUILD_ERROR = "REQUEST_BUILD_ERROR"
    # 发送请求错误
    REQUEST_SEND_ERROR = "REQUEST_SEND_ERROR"
    # 响应提取错误
    RESPONSE_EXTRACT_ERROR = "RESPONSE_EXTRACT_ERROR"
    # 业务编排错误
    PIPELINE_ERROR = "PIPELINE_ERROR"


@dataclass
class ApiExceptionContext:
    """
      作用:
        - 统一异常上下文

      类变量说明:
        - phase: 错误阶段(读取yaml/校验yaml/构建请求/发送请求/提取响应数据/断言/流程)
        - error_code: 错误码, 便于后续统计
        - message: 对错误原因的摘要
        - reason: 原始失败原因
        - yaml_file/yaml_where: 直接定位到 YAML 文件和字段路径
        - request_snapshot/response_snapshot: 失败时的请求/响应快照
        - rule: 提取响应数据/断言 的规则
        - actual/expected: 实际值和预期值(断言使用)
        - hint: 修复建议
        - extra: 扩展上下文, 不属于上述所有字段的附加信息就可以放在该字段中
    """
    phase: ExceptionPhase
    error_code: ExceptionCode
    message: str
    reason: str = ""
    yaml_file: Optional[str] = None
    yaml_where: Optional[str] = None
    api_id: Optional[str] = None
    flow_id: Optional[str] = None
    step_name: Optional[str] = None
    request_snapshot: Optional[Dict[str, Any]] = None
    response_snapshot: Optional[Dict[str, Any]] = None
    rule: Optional[Dict[str, Any]] = None
    actual: Any = None
    expected: Any = None
    hint: Optional[str] = None
    extra: Optional[Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
          将上下文转换为结构化的字典, 供后续日志/报告使用
        """
        return {
            "phase": self.phase.value,
            "error_code": self.error_code.value,
            "message": self.message,
            "reason": self.reason,
            "yaml_file": self.yaml_file,
            "yaml_where": self.yaml_where,
            "api_id": self.api_id,
            "flow_id": self.flow_id,
            "step_name": self.step_name,
            "request_snapshot": self.request_snapshot,
            "response_snapshot": self.response_snapshot,
            "rule": self.rule,
            "actual": self.actual,
            "expected": self.expected,
            "hint": self.hint,
            "extra": self.extra,
        }

    def format_text(self) -> str:
        """
          将上下文生成为可读性较好的文本
        """
        payload = self.to_dict()
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


class AutoApiException(Exception):
    """
      AutoApi 所有异常的唯一根异常
    """
    def __init__(self, error_context: ApiExceptionContext):
        # 保存错误信息的上下文, 供调用方写入 result 或 allure
        self.error_context = error_context
        # 用统一格式化文本初始化异常信息
        super().__init__(self.error_context.format_text())

    def __str__(self) -> str:
        return self.error_context.format_text()


class ValidationException(AutoApiException):
    """
      YAML校验错误
    """


class RequestBuildException(AutoApiException):
    """
      请求构建错误
    """


class RequestSendException(AutoApiException):
    """
      请求发送错误
    """


class ExtractException(AutoApiException):
    """
      响应数据提取错误
    """


class AssertException(AutoApiException):
    """
      断言失败 或 断言执行错误
    """


class PipelineException(AutoApiException):
    """
      流程级错误
    """


class VarResolveException(AutoApiException):
    """
      变量解析/渲染错误
    """


def response_snapshot(response, limit: int = 4000) -> Dict[str, Any]:
    """
      生成统一的响应快照结构
    :param response: 响应对象
    :param limit: 最大输出多少响应数据
    """
    # TODO response 还有其它例如 json, 不一定只有下面几个字段, 现在先这样, 后续再想一想如何组织
    # 默认空快照
    snapshot: Dict[str, Any] = {}

    # 记录状态码
    snapshot["status_code"] = getattr(response, "status_code", None)
    # 记录响应头
    try:
        snapshot["headers"] = dict(getattr(response, "headers", {}) or {})
    except Exception:
        snapshot["headers"] = "<headers 不可用>"
    # 记录响应文本并截断
    try:
        text = getattr(response, "text", "") or ""
        snapshot["response_text"] = text[:limit]
    except Exception:
        snapshot["response_text"] = "<response_text 不可用>"

    return snapshot


def build_api_exception_context(
    *,
    phase: str,
    error_code: str,
    message: str,
    reason: Optional[Any] = None,
    yaml_file: Optional[str] = None,
    yaml_where: Optional[str] = None,
    api_id: Optional[str] = None,
    flow_id: Optional[str] = None,
    step_name: Optional[str] = None,
    request_snapshot: Optional[Dict[str, Any]] = None,
    response_data: Optional[Dict[str, Any]] = None,
    rule: Optional[Dict[str, Any]] = None,
    actual: Any = None,
    expected: Any = None,
    hint: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
):
    """
      统一工厂, 生成标准 ApiExceptionContext
    """
    snap = response_snapshot(response_data) if response_data is not None else None
    return ApiExceptionContext(
        phase=phase,
        error_code=error_code,
        message=message,
        reason=reason,
        yaml_file=yaml_file,
        yaml_where=yaml_where,
        api_id=api_id,
        flow_id=flow_id,
        step_name=step_name,
        request_snapshot=request_snapshot,
        response_snapshot=snap,
        rule=rule,
        actual=actual,
        expected=expected,
        hint=hint,
        extra=extra,
    )


if __name__ == "__main__":
    error = ApiExceptionContext(
        phase="请求阶段",
        error_code="request",
        message="请求失败",
        reason="reason",
        api_id="uuuu"
    )
    print_rich(error.to_dict())
    print(error.format_text())
    raise AutoApiException(error)

