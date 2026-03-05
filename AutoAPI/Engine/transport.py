from typing import Optional

import requests
from requests import Response, Session

from Engine.results import PreparedRequest
from Exceptions.AutoApiException import build_api_exception_context, ExceptionPhase, ExceptionCode, RequestSendException


class TransportBase:
    """
      定义 传输层接口
    """
    name: str = "base"

    def send(self, req: PreparedRequest) -> Response:
        raise NotImplementedError("由子类实现")


class RequestsTransport(TransportBase):
    """
      requests 无状态传输, 每次使用 requests.request
    """
    # transport 名称, 用于报错信息标识
    name: str = "requests"

    def send(self, req: PreparedRequest) -> Response:
        try:
            return requests.request(method=req.method, url=req.url, **req.kwargs)
        except Exception as e:
            # 将已构建的请求, 转为快照
            request_snapshot = req.to_dict()
            error_context = build_api_exception_context(
                phase=ExceptionPhase.REQUEST_SEND,
                error_code=ExceptionCode.REQUEST_SEND_ERROR,
                message=f"请求发送失败: {self.name}",
                reason=str(e),
                yaml_location=str((req.meta.get("where", "transport"))),
                api_id=req.meta.get("api_id"),
                step_name=req.meta.get("step_name"),
                request_snapshot=request_snapshot,
                hint="请检查 host, 网络是否正常连通, 代理配置等"
            )
            raise RequestSendException(error_context) from e


class SessionTransport(TransportBase):
    """
      发送请求时使用 session, 共用状态
    """
    # transport 名称, 用于报错信息标识
    name: str = "session"

    def __init__(self, session: Optional[Session] = None):
        self.session = session or requests.Session()

    def send(self, req: PreparedRequest) -> Response:
        try:
            return self.session.request(method=req.method, url=req.url, **req.kwargs)
        except Exception as e:
            # 将已构建的请求, 转为快照
            request_snapshot = req.to_dict()
            error_context = build_api_exception_context(
                phase=ExceptionPhase.REQUEST_SEND,
                error_code=ExceptionCode.REQUEST_SEND_ERROR,
                message=f"请求发送失败: {self.name}",
                reason=str(e),
                yaml_location=str((req.meta.get("where", "transport"))),
                api_id=req.meta.get("api_id"),
                step_name=req.meta.get("step_name"),
                request_snapshot=request_snapshot,
                hint="请检查 host, 网络是否正常连通, 代理配置等"
            )
            raise RequestSendException(error_context) from e

    def close(self):
        """
          关闭 Session 释放资源
        """
        self.session.close()

