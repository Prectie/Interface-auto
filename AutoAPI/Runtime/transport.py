from typing import Optional

import requests
from requests import Response, Session

from Runtime.results import PreparedRequest
from Runtime.runtime_exception import RuntimeErrorDetail, TransportError


class TransportBase:
    name: str = "base"

    def send(self, req: PreparedRequest) -> Response:
        raise NotImplementedError("由子类实现")


class RequestsTransport(TransportBase):
    name: str = "requests"

    def send(self, req: PreparedRequest) -> Response:
        try:
            return requests.request(method=req.method, url=req.url, **req.kwargs)
        except Exception as e:
            detail = RuntimeErrorDetail(
                where=str(req.meta.get("where", "transport")),
                api_id=req.meta.get("api_id"),
                step_name=req.meta.get("step_name"),
                message=f"请求发送失败 ({self.name})", extra=str(e)
            )
            raise TransportError(detail) from e


class SessionTransport(TransportBase):
    name: str = "session"

    def __init__(self, session: Optional[Session] = None):
        self.session = session or requests.Session()

    def send(self, req: PreparedRequest) -> Response:
        try:
            return requests.request(method=req.method, url=req.url, **req.kwargs)
        except Exception as e:
            detail = RuntimeErrorDetail(
                where=str(req.meta.get("where", "transport")),
                api_id=req.meta.get("api_id"),
                step_name=req.meta.get("step_name"),
                message=f"请求发送失败 ({self.name})", extra=str(e)
            )
            raise TransportError(detail) from e

    def close(self):
        self.session.close()

