# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 05-08 12:30
#  @FileName: update_request.py
#  @FileType: 应用更新检查相关的网络请求构建
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 未来负责此应用与服务端专门请求的构建头，留着暂时不删了
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

from urllib.parse import urlparse
from urllib.request import Request

from config import cfg


DEFAULT_FIRMWARE_BASE_URL = "https://update.hepi.ng"


def build_request(url: str, *, headers: dict[str, str] | None = None, data: bytes | None = None) -> Request:
    merged_headers = dict(headers or {})
    session_token = str(getattr(cfg, "githubSessionToken").value or "").strip()
    target = urlparse(url)
    firmware_base = urlparse(str(cfg.firmwareBaseUrl.value or DEFAULT_FIRMWARE_BASE_URL).strip().rstrip("/"))
    lower_headers = {str(key).lower() for key in merged_headers}
    if (
        session_token
        and target.scheme in {"http", "https"}
        and target.netloc.lower() == firmware_base.netloc.lower()
        and "x-f4cp-session-token" not in lower_headers
    ):
        merged_headers["X-F4CP-Session-Token"] = session_token
    return Request(url, data=data, headers=merged_headers)
