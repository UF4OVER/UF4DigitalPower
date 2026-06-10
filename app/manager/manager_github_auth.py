# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @FileName: manager_github_auth.py
#  @FileType: GitHub 登录与会话管理
# -------------------------------

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from socket import socket
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PyQt5.QtCore import QThread, pyqtSignal
from qfluentwidgets import qconfig

from app.core.update_request import build_request
from config import CTX, get_logger

logger = get_logger("GithubAuth")
DEFAULT_FIRMWARE_BASE_URL = "https://update.hepi.ng"
AUTH_REQUEST_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36 F4CP/0.6"
    ),
}
LOOPBACK_CALLBACK_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>档案收录完成</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700;800&family=Noto+Sans+SC:wght@400;500;700&family=Noto+Serif+SC:wght@500;700&display=swap');
    :root {
      --gold: #c9a84c;
      --gold-dark: #8b6914;
      --crimson: #8b1a2b;
      --dark-bg: #0a0815;
      --dark-card: rgba(16, 14, 29, 0.92);
      --dark-border: #2a2040;
      --text-main: #f3ead0;
      --text-subtle: #8e879f;
    }
    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      min-height: 100%;
      background:
        radial-gradient(circle at top, rgba(139, 26, 43, 0.16), transparent 30%),
        linear-gradient(180deg, #100e1d 0%, #0a0815 52%, #0a0815 100%);
      color: var(--text-main);
      font-family: 'Noto Sans SC', 'Noto Serif SC', serif;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      background-image:
        linear-gradient(rgba(201, 168, 76, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(201, 168, 76, 0.03) 1px, transparent 1px);
      background-size: 56px 56px;
      opacity: 0.4;
      pointer-events: none;
    }
    .ticker {
      display: flex;
      gap: 28px;
      padding: 12px 32px;
      border-bottom: 1px solid var(--dark-border);
      background: rgba(10, 8, 21, 0.95);
      color: #b7b0c8;
      font-size: 12px;
      letter-spacing: 0.28em;
      white-space: nowrap;
      overflow: hidden;
    }
    .ticker strong { color: var(--crimson); }
    .shell {
      min-height: calc(100vh - 46px);
      display: grid;
      place-items: center;
      padding: 32px 20px 56px;
    }
    .panel {
      width: min(760px, 100%);
      position: relative;
      overflow: hidden;
      border: 1px solid rgba(201, 168, 76, 0.24);
      background: var(--dark-card);
      box-shadow:
        0 0 0 1px rgba(42, 32, 64, 0.95) inset,
        0 0 36px rgba(201, 168, 76, 0.08),
        0 24px 80px rgba(0, 0, 0, 0.45);
    }
    .panel::before {
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      background:
        linear-gradient(var(--gold-dark), var(--gold-dark)) left top / 30px 1px no-repeat,
        linear-gradient(var(--gold-dark), var(--gold-dark)) left top / 1px 30px no-repeat,
        linear-gradient(var(--gold-dark), var(--gold-dark)) right top / 30px 1px no-repeat,
        linear-gradient(var(--gold-dark), var(--gold-dark)) right top / 1px 30px no-repeat,
        linear-gradient(var(--gold-dark), var(--gold-dark)) left bottom / 30px 1px no-repeat,
        linear-gradient(var(--gold-dark), var(--gold-dark)) left bottom / 1px 30px no-repeat,
        linear-gradient(var(--gold-dark), var(--gold-dark)) right bottom / 30px 1px no-repeat,
        linear-gradient(var(--gold-dark), var(--gold-dark)) right bottom / 1px 30px no-repeat;
      opacity: 0.85;
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 18px;
      border-bottom: 1px solid rgba(201, 168, 76, 0.14);
      background: rgba(10, 8, 21, 0.82);
      font-size: 11px;
      letter-spacing: 0.26em;
      color: var(--text-subtle);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .sigil {
      width: 34px;
      height: 34px;
      border: 2px solid rgba(201, 168, 76, 0.44);
      transform: rotate(45deg);
      display: grid;
      place-items: center;
      background: rgba(16, 14, 29, 0.92);
      box-shadow: 0 0 18px rgba(201, 168, 76, 0.14);
    }
    .sigil span {
      transform: rotate(-45deg);
      color: var(--gold);
      font: 800 18px/1 'Cinzel', serif;
    }
    .status {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--crimson);
      box-shadow: 0 0 12px rgba(139, 26, 43, 0.55);
      animation: blink 1.6s infinite;
    }
    .content { padding: 58px 32px 36px; }
    .accent {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 18px;
      color: var(--crimson);
      font-size: 12px;
      letter-spacing: 0.32em;
    }
    .accent::before {
      content: "";
      width: 28px;
      height: 2px;
      background: var(--crimson);
    }
    h1 {
      margin: 0;
      color: var(--gold);
      font: 800 clamp(38px, 8vw, 72px)/0.95 'Cinzel', serif;
      letter-spacing: 0.05em;
    }
    h2 {
      margin: 12px 0 0;
      color: #ffffff;
      font: 700 clamp(24px, 4vw, 38px)/1.15 'Noto Serif SC', serif;
    }
    .divider {
      width: 100%;
      height: 1px;
      margin: 24px 0 22px;
      background: linear-gradient(90deg, rgba(201, 168, 76, 0.55), rgba(201, 168, 76, 0.16), transparent);
    }
    .body {
      max-width: 560px;
      color: #c9c1da;
      font-size: 15px;
      line-height: 1.9;
    }
    .badge-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 22px 0 26px;
    }
    .badge {
      padding: 9px 14px;
      border: 1px solid rgba(42, 32, 64, 1);
      background: rgba(10, 8, 21, 0.48);
      color: #b9b2cb;
      font-size: 12px;
      letter-spacing: 0.14em;
    }
    .footer-line {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      color: #6e6880;
      font-size: 11px;
      letter-spacing: 0.2em;
      margin-top: 30px;
    }
    @keyframes blink {
      0%, 50% { opacity: 1; }
      51%, 100% { opacity: 0.22; }
    }
    @media (max-width: 640px) {
      .ticker { padding-inline: 18px; gap: 18px; font-size: 11px; }
      .content { padding: 42px 20px 26px; }
      .topbar { flex-direction: column; align-items: flex-start; }
      .footer-line { flex-direction: column; }
    }
  </style>
</head>
<body>
  <div class="ticker">
    <span><strong>通告</strong> 档案收录流程已完成</span>
    <span>// 馆藏检索权限已回传至终端</span>
    <span>ARCHIVE STATUS · CLOSED TODAY</span>
  </div>
  <main class="shell">
    <section class="panel">
      <div class="topbar">
        <div class="brand">
          <div class="sigil"><span>H</span></div>
          <div>HEPI.NG ARCHIVE</div>
        </div>
        <div class="status">
          <span class="status-dot"></span>
          <span>CLASSIFIED DOSSIER</span>
        </div>
      </div>
      <div class="content">
        <div class="accent">ARCHIVE COMPLETED</div>
        <h1>ARCHIVE</h1>
        <h2>档案收录完成，今日已闭馆。</h2>
        <div class="divider"></div>
        <div class="body">
          凭证已回传至 F4CP 终端，当前页面无需保留。
          归档已封卷，你可以关闭这个窗口，返回上位机继续操作。
        </div>
        <div class="badge-row">
          <div class="badge">馆藏状态 · 已封卷</div>
          <div class="badge">访客权限 · 已下发</div>
          <div class="badge">归档编号 · F4CP-GH</div>
        </div>
        <div class="footer-line">
          <span>HEPI.NG DOSSIER TERMINAL</span>
          <span>TODAY CLOSED</span>
        </div>
      </div>
    </section>
  </main>
</body>
</html>
"""


@dataclass(frozen=True)
class GithubSessionState:
    authenticated: bool
    session_token: str = ""
    github_login: str = ""
    github_name: str = ""
    avatar_url: str = ""
    profile_url: str = ""
    expires_at: int = 0

    @property
    def display_name(self) -> str:
        return self.github_name or self.github_login or "未登录"


@dataclass(frozen=True)
class GithubAuthResult:
    success: bool
    message: str
    session: GithubSessionState | None = None


def _truncate(text: str, limit: int = 1200) -> str:
    normalized = str(text or "").strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "...(truncated)"


def _format_headers(headers) -> str:
    try:
        items = list(headers.items())
    except Exception:
        return ""
    return "; ".join(f"{key}={value}" for key, value in items)


def _describe_request(request: Request) -> str:
    method = request.get_method() if hasattr(request, "get_method") else "GET"
    return f"{method} {request.full_url}"


def _user_facing_auth_error(message: str, fallback: str = "GitHub 登录失败，请稍后重试。") -> str:
    normalized = str(message or "").lower()
    if "http 403" in normalized or "forbidden" in normalized or "error code: 1010" in normalized:
        return "登录请求被拦截，请稍后再试。"
    if "http 429" in normalized or "too many requests" in normalized:
        return "请求过于频繁，请稍后再试。"
    if "timeout" in normalized or "timed out" in normalized:
        return "登录请求超时，请稍后重试。"
    if "failed to resolve" in normalized or "name or service not known" in normalized:
        return "无法连接登录服务器，请检查网络。"
    if "未收到登录回调" in normalized:
        return "未完成浏览器授权，请重新登录。"
    if "session" in normalized and ("invalid" in normalized or "401" in normalized or "失效" in normalized):
        return "登录已失效，请重新登录。"
    return fallback


def _http_error_message(exc: HTTPError, request: Request, *, context: str) -> str:
    try:
        body = exc.read().decode("utf-8-sig", errors="replace")
    except Exception:
        body = ""
    headers_text = _format_headers(exc.headers)
    body_text = _truncate(body)
    message = (
        f"{context}: HTTP {exc.code} {exc.reason}; "
        f"request={_describe_request(request)}"
    )
    logger.warning(message)
    if headers_text:
        logger.warning(f"{context} response headers: {headers_text}")
    if body_text:
        logger.warning(f"{context} response body: {body_text}")
    return f"{context}: HTTP {exc.code} {exc.reason}"


def _url_error_message(exc: URLError, request: Request, *, context: str) -> str:
    message = f"{context}: {exc.reason}; request={_describe_request(request)}"
    logger.warning(message)
    return f"{context}: {exc.reason}"


def _base_url() -> str:
    return str(CTX.cfg.firmwareBaseUrl.value or DEFAULT_FIRMWARE_BASE_URL).strip().rstrip("/")


def _auth_url(path: str, query: dict[str, str] | None = None) -> str:
    url = f"{_base_url()}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    return url


def cached_session_state() -> GithubSessionState:
    token = str(CTX.cfg.githubSessionToken.value or "").strip()
    expires_at = int(CTX.cfg.githubSessionExpiresAt.value or 0)
    authenticated = bool(token) and (expires_at <= 0 or expires_at > int(time.time()))
    return GithubSessionState(
        authenticated=authenticated,
        session_token=token,
        github_login=str(CTX.cfg.githubLogin.value or "").strip(),
        github_name=str(CTX.cfg.githubName.value or "").strip(),
        avatar_url=str(CTX.cfg.githubAvatarUrl.value or "").strip(),
        profile_url=str(CTX.cfg.githubProfileUrl.value or "").strip(),
        expires_at=expires_at,
    )


def save_session_state(session: GithubSessionState) -> None:
    qconfig.set(CTX.cfg.githubSessionToken, session.session_token)
    qconfig.set(CTX.cfg.githubLogin, session.github_login)
    qconfig.set(CTX.cfg.githubName, session.github_name)
    qconfig.set(CTX.cfg.githubAvatarUrl, session.avatar_url)
    qconfig.set(CTX.cfg.githubProfileUrl, session.profile_url)
    qconfig.set(CTX.cfg.githubSessionExpiresAt, int(session.expires_at or 0))


def clear_session_state() -> None:
    save_session_state(GithubSessionState(authenticated=False))


def session_token_for_url(url: str) -> str:
    token = str(CTX.cfg.githubSessionToken.value or "").strip()
    if not token:
        return ""
    target = urlparse(url)
    base = urlparse(_base_url())
    if target.scheme in {"http", "https"} and target.netloc.lower() == base.netloc.lower():
        return token
    return ""


def fetch_session_state(session_token: str) -> GithubSessionState:
    request = build_request(
        _auth_url("/auth/github/session", {"session_token": session_token}),
        headers=AUTH_REQUEST_HEADERS,
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8-sig"))
    except HTTPError as exc:
        raise RuntimeError(_http_error_message(exc, request, context="GitHub session check failed")) from exc
    except URLError as exc:
        raise RuntimeError(_url_error_message(exc, request, context="GitHub session check failed")) from exc
    if not isinstance(payload, dict) or not payload.get("authenticated"):
        raise RuntimeError("GitHub 登录会话无效。")
    return GithubSessionState(
        authenticated=True,
        session_token=session_token,
        github_login=str(payload.get("github_login") or "").strip(),
        github_name=str(payload.get("github_name") or "").strip(),
        avatar_url=str(payload.get("avatar_url") or "").strip(),
        profile_url=str(payload.get("profile_url") or "").strip(),
        expires_at=int(payload.get("expires_at") or 0),
    )


def revoke_remote_session(session_token: str) -> None:
    if not session_token:
        return
    request = build_request(
        _auth_url("/auth/github/logout", {"session_token": session_token}),
        headers=AUTH_REQUEST_HEADERS,
        data=b"",
    )
    try:
        urlopen(request, timeout=10).read()
    except HTTPError as exc:
        raise RuntimeError(_http_error_message(exc, request, context="GitHub logout failed")) from exc
    except URLError as exc:
        raise RuntimeError(_url_error_message(exc, request, context="GitHub logout failed")) from exc


def _find_free_loopback_port() -> int:
    with socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class GithubSessionRefreshThread(QThread):
    resultReady = pyqtSignal(object)

    def __init__(self, session_token: str, parent=None):
        super().__init__(parent)
        self.session_token = session_token

    def run(self) -> None:
        try:
            session = fetch_session_state(self.session_token)
            save_session_state(session)
            result = GithubAuthResult(True, "GitHub 登录状态已更新。", session)
        except Exception as exc:
            logger.warning(f"Failed to refresh GitHub session: {exc}")
            clear_session_state()
            result = GithubAuthResult(False, _user_facing_auth_error(str(exc), "无法校验 GitHub 登录状态。"))
        self.resultReady.emit(result)


class GithubLogoutThread(QThread):
    resultReady = pyqtSignal(object)

    def __init__(self, session_token: str, parent=None):
        super().__init__(parent)
        self.session_token = session_token

    def run(self) -> None:
        try:
            revoke_remote_session(self.session_token)
        except Exception as exc:
            logger.warning(f"Failed to revoke GitHub session: {exc}")
        clear_session_state()
        self.resultReady.emit(GithubAuthResult(True, "GitHub 登录已退出。"))


class GithubLoginThread(QThread):
    authorizeUrlReady = pyqtSignal(str)
    resultReady = pyqtSignal(object)

    def run(self) -> None:
        try:
            port = _find_free_loopback_port()
            redirect_uri = f"http://127.0.0.1:{port}/callback"
            start_request = build_request(
                _auth_url(
                    "/auth/github/start",
                    {
                        "redirect_uri": redirect_uri,
                        "client": "f4cp-desktop",
                    },
                ),
                headers=AUTH_REQUEST_HEADERS,
            )
            logger.info(f"Starting GitHub login: redirect_uri={redirect_uri}")
            logger.info(f"GitHub login start request: {_describe_request(start_request)}")
            try:
                with urlopen(start_request, timeout=15) as response:
                    start_payload = json.loads(response.read().decode("utf-8-sig"))
            except HTTPError as exc:
                raise RuntimeError(_http_error_message(exc, start_request, context="GitHub login start failed")) from exc
            except URLError as exc:
                raise RuntimeError(_url_error_message(exc, start_request, context="GitHub login start failed")) from exc
            if not isinstance(start_payload, dict):
                raise RuntimeError("登录初始化失败，服务器没有返回有效授权地址。")

            authorize_url = str(start_payload.get("authorize_url") or "").strip()
            if not authorize_url:
                raise RuntimeError("登录初始化失败，缺少 authorize_url。")
            logger.info(f"GitHub authorize URL received: {authorize_url}")

            result_box: dict[str, str] = {}

            class CallbackHandler(BaseHTTPRequestHandler):
                def do_GET(self):  # noqa: N802
                    parsed = urlparse(self.path)
                    query = parse_qs(parsed.query)
                    result_box["session_token"] = str(query.get("session_token", [""])[0] or "").strip()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(LOOPBACK_CALLBACK_HTML.encode("utf-8"))

                def log_message(self, format, *args):  # noqa: A003
                    return

            server = HTTPServer(("127.0.0.1", port), CallbackHandler)
            server.timeout = 300
            self.authorizeUrlReady.emit(authorize_url)
            logger.info(f"Waiting for GitHub callback on http://127.0.0.1:{port}/callback")
            server.handle_request()
            server.server_close()

            session_token = str(result_box.get("session_token") or "").strip()
            if not session_token:
                raise RuntimeError("未收到登录回调，请确认浏览器已完成授权。")

            logger.info("GitHub callback received, validating session token with update server")
            session = fetch_session_state(session_token)
            save_session_state(session)
            self.resultReady.emit(GithubAuthResult(True, "GitHub 登录成功。", session))
        except Exception as exc:
            logger.exception(f"GitHub login failed: {exc}")
            self.resultReady.emit(
                GithubAuthResult(False, _user_facing_auth_error(str(exc), "GitHub 登录失败，请稍后重试。"))
            )
