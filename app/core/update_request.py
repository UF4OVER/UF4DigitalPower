# -*- coding: utf-8 -*-
"""Request builder for update checks."""
from __future__ import annotations

from urllib.request import Request



def build_request(url: str, *, headers: dict[str, str] | None = None, data: bytes | None = None) -> Request:
    return Request(url, data=data, headers=headers or {})
