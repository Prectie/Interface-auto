import base64
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, Union

from requests import Response


class ExceptionCode(str, Enum):
    """
      错误码枚举
    """
    # 校验 YAML 错误
    VALIDATION_ERROR = "VALIDATION_ERROR"
    # 读取 YAML 错误
    YAML_IO_ERROR = "YAML_IO_ERROR"
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
        - error_code: 错误码, 便于后续统计
        - message: 对错误原因的摘要
        - reason: 原始失败原因
        - request_snapshot/response_snapshot: 失败时的请求/响应快照
        - actual/expected: 实际值和预期值
        - hint: 修复建议
        - extra: 扩展上下文, 不属于上述所有字段的附加信息就可以放在该字段中
    """
    error_code: ExceptionCode
    message: str
    reason: str = ""
    # yaml 文件名(标识错误来自哪个文件)
    yaml_file: Optional[str] = None
    # 业务流来源文档(业务流错误时标识来源)
    flow_file: Optional[str] = None
    # 校验异常时的精确路径
    yaml_location: Optional[str] = None
    api_id: Optional[str] = None
    flow_id: Optional[str] = None
    step_name: Optional[str] = None
    profile_name: Optional[str] = None
    request_snapshot: Optional[Dict[str, Any]] = None
    response_snapshot: Optional[Dict[str, Any]] = None
    # 提取/断言规则
    extract_rule: Optional[Dict[str, Any]] = None
    assertion_rule: Optional[Dict[str, Any]] = None
    actual: Any = None
    expected: Any = None
    hint: Optional[str] = None
    extra: Optional[Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
          将上下文转换为结构化的字典, 供后续日志/报告使用
        """
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "reason": self.reason,
            "yaml_file": self.yaml_file,
            "flow_file": self.flow_file,
            "yaml_location": self.yaml_location,
            "api_id": self.api_id,
            "flow_id": self.flow_id,
            "step_name": self.step_name,
            "profile_name": self.profile_name,
            "request_snapshot": self.request_snapshot,
            "response_snapshot": self.response_snapshot,
            "extract_rule": self.extract_rule,
            "assertion_rule": self.assertion_rule,
            "actual": self.actual,
            "expected": self.expected,
            "hint": self.hint,
            "extra": self.extra,
        }

    def format_json(self) -> str:
        """
          将上下文生成为可读性较好的文本
        """
        payload = self.to_dict()
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    def format_text(self) -> str:
        """
          将上下文生成为可读性较好的文本
        """
        d = self.to_dict()
        # 初始化输出列表
        lines = []
        lines.append(f'\nerror_code: {d.get("error_code")}')
        lines.append(f'message: {d.get("message")}')

        # 若为校验异常, 则展示精确 yaml_location
        if d.get("error_code") == ExceptionCode.VALIDATION_ERROR.value:
            if d.get("yaml_location") is not None:
                lines.append(f'yaml_location: {d.get("yaml_location")}')
        else:
            if d.get("yaml_file") is not None:
                lines.append(f'yaml_file: {d.get("yaml_file")}')
            if d.get("flow_file") is not None:
                lines.append(f'flow_file: {d.get("flow_file")}')
            if d.get("api_id") is not None:
                lines.append(f'api_id: {d.get("api_id")}')
            if d.get("flow_id") is not None:
                lines.append(f'flow_id: {d.get("flow_id")}')
            if d.get("step_name") is not None:
                lines.append(f'step_name: {d.get("step_name")}')
            if d.get("profile_name") is not None:
                lines.append(f'profile_name: {d.get("profile_name")}')

        lines.append("reason: ")
        reason_text = d.get("reason") or ""
        if reason_text.strip():
            # 按行拆开, 原样输出每行
            for one in reason_text.splitlines():
                lines.append(f"    {one}")
        else:
            lines.append(f"    <empty>")

        if d.get("hint") is not None:
            lines.append(f'hint: {d.get("hint")}')

        if d.get("request_snapshot") is not None:
            lines.append("request_snapshot: ")
            lines.append(json.dumps(d.get("request_snapshot"), ensure_ascii=False, indent=2, default=str))

        if d.get("response_snapshot") is not None:
            lines.append("response_snapshot: ")
            lines.append(json.dumps(d.get("response_snapshot"), ensure_ascii=False, indent=2, default=str))

        if d.get("extract_rule") is not None:
            lines.append("extract_rule: ")
            lines.append(json.dumps(d.get("extract_rule"), ensure_ascii=False, indent=2, default=str))

        if d.get("assertion_rule") is not None:
            lines.append("assertion_rule: ")
            lines.append(json.dumps(d.get("assertion_rule"), ensure_ascii=False, indent=2, default=str))

        if d.get("actual") is not None or d.get("expected") is not None:
            lines.append(f'actual: {d.get("actual")}')
            lines.append(f'expected: {d.get("expected")}')

        if d.get("extra") is not None:
            lines.append("extra: ")
            lines.append(json.dumps(d.get("extra"), ensure_ascii=False, indent=2, default=str))

        return "\n".join(lines)


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


class YamlIOException(AutoApiException):
    """
      YAML IO 读取错误
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


def to_response_snapshot(
    response,
    *,
    text_limit: int = 5000,
    json_limit: int = 5000,
    binary_limit: int = 128

) -> Dict[str, Any]:
    """
      生成统一的响应快照结构
    :param response: 响应对象
    :param text_limit: 文本响应最大保留字符
    :param json_limit: JSON 响应最大保留字符
    :param binary_limit: 二进制预览最大字节数
    """
    # 初始化输出结果
    snapshot: Dict[str, Any] = {"status_code": getattr(response, "status_code", None)}

    # 记录响应头
    try:
        snapshot["headers"] = dict(getattr(response, "headers", {}) or {})
    except Exception:
        snapshot["headers"] = "<headers 不可用>"

    # 获取 content bytes长度
    try:
        # response.content 属于 bytes 类型, 因此缺省值也用 bytes 类型, 为 None 时也转为空串
        content = getattr(response, "content", b"") or b""
        snapshot["content_length"] = len(content)
    except Exception:
        content = b""
        snapshot["content_length"] = None

    # 记录 cookies
    try:
        snapshot["cookies"] = response.cookies.get_dict()
    except Exception:
        snapshot["cookies"] = "<cookies 不可用>"

    # 记录耗时
    try:
        snapshot["elapsed_ms"] = response.elapsed.total_seconds() * 1000
    except Exception:
        snapshot["elapsed_ms"] = None

    # 记录编码格式
    snapshot["encoding"] = getattr(response, "encoding", None)

    # 记录 json 数据
    try:
        snapshot["body_kind"] = "json"
        json_data = response.json()
        json_text = json.dumps(json_data, ensure_ascii=False, indent=2, default=str)
        if len(json_text) > json_limit:
            # 超过限制则截断
            snapshot["body"] = json_text[:json_limit]
            snapshot["body_truncated"] = True
        else:
            # 没超过则保留原文
            snapshot["body"] = json_data
        return snapshot
    except Exception:
        pass

    # 记录响应文本并截断
    try:
        snapshot["body_kind"] = "text"
        text_data = getattr(response, "text", None)
        if text_data is not None:
            if len(text_data) > text_limit:
                # 截断
                snapshot["body"] = text_data[:text_limit]
                snapshot["body_truncated"] = True
            else:
                snapshot["body"] = text_data
        return snapshot
    except Exception:
        pass

    # 记录二进制摘要
    try:
        snapshot["body_kind"] = "binary"
        # 若响应原始字节流非空, 则生成二进制摘要
        if content:
            preview = content[:binary_limit]
            snapshot["binary_summary"] = {
                # 记录完整响应体的 sha256
                "sha256": hashlib.sha256(content).hexdigest(),
                # 记录若干自己的 base64 预览
                "preview_base64": base64.b64encode(preview).decode("ascii")
            }
    except Exception:
        pass

    snapshot["body_kind"] = "empty"
    snapshot["body"] = None
    return snapshot


def _format_reason(reason):
    """
      把 reason 变成可读字符串
    """
    if reason is None:
        return ""
    try:
        return str(reason)
    except Exception:
        return repr(reason)


def _derive_yaml_file_from_location(yaml_location: str):
    """
      从精确定位路径中获取 yaml 文件名, 用于校验异常
    """
    # 若定位路径为空, 则直接返回 None
    if not yaml_location:
        return None

    # 若路径以 config.yaml 开头, 则返回 config.yaml
    if yaml_location.startswith("config.yaml"):
        return "config.yaml"

    # single.yaml 同理
    if yaml_location.startswith("single.yaml"):
        return "single.yaml"


def _derive_yaml_file_from_flow_source(flow_source: str):
    """
      从 FlowBundle 的 source 中提取 yaml 文件
    :param flow_source:
    :return:
    """
    if not flow_source:
        return None

    return flow_source.split('#', 1)[0]


def build_api_exception_context(
    *,
    error_code: ExceptionCode,
    message: str,
    reason: Optional[Any] = None,
    yaml_file: Optional[str] = None,
    flow_file: Optional[str] = None,
    yaml_location: Optional[str] = None,
    api_id: Optional[str] = None,
    flow_id: Optional[str] = None,
    step_name: Optional[str] = None,
    profile_name: Optional[str] = None,
    request: Optional[Dict[str, Any]] = None,
    response: Union[Response, Dict[str, Any]] = None,
    extract_rule: Optional[Dict[str, Any]] = None,
    assertion_rule: Optional[Dict[str, Any]] = None,
    actual: Any = None,
    expected: Any = None,
    hint: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
):
    """
      统一工厂, 生成标准 ApiExceptionContext
    """
    # 获取 yaml 文件
    final_yaml_file = yaml_file or _derive_yaml_file_from_flow_source(flow_file)
    # 若不是业务流, 则从 yaml location 中获取
    final_yaml_file = final_yaml_file or _derive_yaml_file_from_location(yaml_location)

    if response is None:
        snap = None
    elif isinstance(response, dict):
        snap = response
    else:
        snap = to_response_snapshot(response)

    return ApiExceptionContext(
        error_code=error_code,
        message=message,
        reason=_format_reason(reason),
        yaml_file=final_yaml_file,
        flow_file=flow_file,
        yaml_location=yaml_location,
        api_id=api_id,
        flow_id=flow_id,
        step_name=step_name,
        profile_name=profile_name,
        request_snapshot=request,
        response_snapshot=snap,
        extract_rule=extract_rule,
        assertion_rule=assertion_rule,
        actual=actual,
        expected=expected,
        hint=hint,
        extra=extra,
    )


if __name__ == "__main__":
    error = ApiExceptionContext(
        error_code=ExceptionCode.VALIDATION_ERROR,
        message="请求失败",
        reason="reason",
        api_id="uuuu",
        request_snapshot={"dadada":"dadadada"},
        yaml_location="multiple.yaml"
    )
    # print_rich(error.to_dict())
    # print(error.format_text())
    raise AutoApiException(error)

