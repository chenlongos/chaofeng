from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ServiceCallError(RuntimeError):
    """表示调用其他 HTTP 服务失败时抛出的统一异常。"""

    pass


def post_json(url: str, payload: dict[str, Any], timeout_s: float = 120.0) -> dict[str, Any]:
    """向指定服务发送 JSON POST 请求，并把 JSON 响应解析成字典。"""
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ServiceCallError(f"POST {url} failed: HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ServiceCallError(f"POST {url} failed: {exc.reason}") from exc


def get_json(url: str, timeout_s: float = 10.0) -> dict[str, Any]:
    """向指定服务发送 JSON GET 请求，并把 JSON 响应解析成字典。"""
    req = Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ServiceCallError(f"GET {url} failed: HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ServiceCallError(f"GET {url} failed: {exc.reason}") from exc
