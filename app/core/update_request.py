# -*- coding: utf-8 -*-
"""Signed request builder for update.hepi.ng."""
from __future__ import annotations

import base64
import hashlib
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request

from config import CTX, logger

TRUSTED_HOST = "update.hepi.ng"
TRUSTED_CLIENT_ID = "f4cp-desktop"
SIGNATURE_VERSION = "v1"


def build_request(url: str, *, headers: dict[str, str] | None = None, data: bytes | None = None) -> Request:
    request = Request(url, data=data, headers=headers or {})
    if _should_sign(url):
        _sign_request(request)
    return request


def _should_sign(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.hostname == TRUSTED_HOST


def _sign_request(request: Request) -> None:
    private_key = CTX.dirs.ClientPrivateKeyPath
    if not private_key.exists():
        logger.warning("Update request signing skipped because private key file is missing: %s", private_key)
        return

    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    body = request.data or b""
    if not isinstance(body, (bytes, bytearray)):
        body = bytes(body)
    payload = "\n".join(
        [
            TRUSTED_CLIENT_ID,
            request.get_method().upper(),
            urlparse(request.full_url).path,
            urlparse(request.full_url).query or "",
            hashlib.sha256(bytes(body)).hexdigest(),
            timestamp,
            nonce,
        ]
    ).encode("utf-8")

    try:
        signature = _openssl_sign(private_key, payload)
    except Exception as exc:
        logger.warning("Update request signing failed, falling back to anonymous request: %s", exc)
        return

    request.add_header("X-F4CP-Client-Id", TRUSTED_CLIENT_ID)
    request.add_header("X-F4CP-Timestamp", timestamp)
    request.add_header("X-F4CP-Nonce", nonce)
    request.add_header("X-F4CP-Signature-Version", SIGNATURE_VERSION)
    request.add_header("X-F4CP-Signature", signature)


def _openssl_sign(private_key: Path, payload: bytes) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as payload_file:
        payload_file.write(payload)
        payload_path = Path(payload_file.name)

    with tempfile.NamedTemporaryFile(delete=False) as signature_file:
        signature_path = Path(signature_file.name)

    try:
        subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-sign",
                "-rawin",
                "-inkey",
                str(private_key),
                "-in",
                str(payload_path),
                "-out",
                str(signature_path),
            ],
            check=True,
            capture_output=True,
        )
        signature_bytes = signature_path.read_bytes()
        return base64.urlsafe_b64encode(signature_bytes).decode("ascii").rstrip("=")
    finally:
        payload_path.unlink(missing_ok=True)
        signature_path.unlink(missing_ok=True)
