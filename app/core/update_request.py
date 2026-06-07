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

from urllib.request import Request



def build_request(url: str, *, headers: dict[str, str] | None = None, data: bytes | None = None) -> Request:
    # todo 应用与服务端专门请求的构建头
    return Request(url, data=data, headers=headers or {})
