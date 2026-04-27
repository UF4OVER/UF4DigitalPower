# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : TVLCOMV1_FULL
#  @Time    : 2026 - 01-19 15:10
#  @FileName: rpc.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------

import struct
import time

from .const import *
from .tlv import tlv_encode

"""RPC support for TVLCOMV1_FULL.

MicroPython notes:
- Some ports don't provide built-in TimeoutError; we fall back to Exception.
- Prefer time.ticks_ms()/ticks_diff() + sleep_ms() when available.

Wire format (TLV payloads):
- TLV_RPC_REQ  (0x80): <cid:u16> + TLV_STRING(method) + (arg_tlv ...)
- TLV_RPC_RESP (0x81): <cid:u16> <status:u8> + (ret_tlv_bytes ...)

Status:
- 0: OK
- 1: method not found
- 3: method raised exception
"""


# MicroPython 下不一定提供 TimeoutError，这里做兼容处理
try:
    _TimeoutBase = TimeoutError  # type: ignore[name-defined]
except NameError:  # MicroPython
    _TimeoutBase = Exception


def _now_ms() -> int:
    """Monotonic-ish milliseconds clock.

    - MicroPython: use ticks_ms()
    - CPython: derive from time.time()
    """

    try:
        return time.ticks_ms()  # type: ignore[attr-defined]
    except Exception:
        return int(time.time() * 1000)


def _elapsed_ms(start_ms: int) -> int:
    """Elapsed ms since start_ms with wrap-safe behavior on MicroPython."""

    try:
        return time.ticks_diff(_now_ms(), start_ms)  # type: ignore[attr-defined]
    except Exception:
        return _now_ms() - start_ms


def _sleep_ms(ms: int) -> None:
    """Sleep helper that works on CPython and MicroPython."""

    try:
        time.sleep_ms(ms)  # type: ignore[attr-defined]
    except Exception:
        time.sleep(ms / 1000.0)


class RPCTimeoutError(_TimeoutBase):
    """RPC 调用超时。

    CPython 下继承 TimeoutError；MicroPython 下退化为 Exception。
    """

    def __init__(self, method, cid, timeout):
        super().__init__("RPC timeout: method=%r cid=%s timeout=%s" % (method, cid, timeout))
        self.method = method
        self.cid = cid
        self.timeout = timeout


class RPC:
    def __init__(self, protocol):
        """Create an RPC helper bound to a Protocol.

        Args:
            protocol: Protocol instance (must expose .send_payload and .dispatcher)
        """

        self.proto = protocol
        self.methods = {}
        self.pending = {}

        # 让不同端点默认拥有不同的 call_id 起点，避免双端同时作为 client 时 cid 冲突
        self.call_id = ((id(protocol) >> 4) ^ int(time.time() * 1000)) & 0xFFFF
        if self.call_id == 0:
            self.call_id = 1

        protocol.dispatcher.register(TLV_RPC_REQ, self._on_req)
        protocol.dispatcher.register(TLV_RPC_RESP, self._on_resp)

        # 额外保险：保持与旧版本兼容（当前实现无需额外 hook）
        self._wrap_frame_hook()

    def _wrap_frame_hook(self):
        # 不再覆盖 dispatcher.handle_frame（外部可能已经包了一层调试日志）
        # 这里通过注册一个“保险 handler”实现：
        # - 在 Dispatcher 正常 TLV 分发前，RPC TLV 一样会被分发到 _on_req/_on_resp
        # - 如果未来 payload 里出现非标准变体，也不影响现有行为
        return

    def register(self, name, func):
        self.methods[name] = func

    def call(self, name, args, timeout=1.0):
        """同步 RPC 调用。

        Args:
            name: method name (string)
            args: list of TLV-encoded bytes (e.g. tlv_int32(1))
            timeout: seconds

        Returns:
            (status:int, ret:bytes)

        Raises:
            RPCTimeoutError: 超时未收到响应
        """
        # 分配一个当前未在 pending 中使用的 cid
        cid = self.call_id
        while cid in self.pending:
            cid = (cid + 1) & 0xFFFF
            if cid == 0:
                cid = 1
        self.call_id = (cid + 1) & 0xFFFF
        if self.call_id == 0:
            self.call_id = 1

        payload = struct.pack("<H", cid)
        payload += tlv_encode(TLV_STRING, name.encode())
        for a in args:
            payload += a

        self.pending[cid] = None

        try:
            try:
                print("[RPC] call start method=%r cid=%s timeout=%s" % (name, cid, timeout))
            except Exception:
                pass

            self.proto.send_payload(tlv_encode(TLV_RPC_REQ, payload), ack=False)

            start_ms = _now_ms()
            timeout_ms = int(timeout * 1000)
            while _elapsed_ms(start_ms) < timeout_ms:
                v = self.pending.get(cid, None)
                if v is not None:
                    return self.pending.pop(cid)

                # 让出 CPU / 让出 GIL：避免主循环被占满（MicroPython/CPython 都有用）
                _sleep_ms(10)

            raise RPCTimeoutError(method=name, cid=cid, timeout=timeout)

        finally:
            # 无论成功/异常都清理，避免泄露（成功时 pending 已 pop，这里 pop(None) 不影响）
            self.pending.pop(cid, None)

    def _on_req(self, data, seq):
        cid = struct.unpack("<H", data[:2])[0]
        off = 2

        t = data[off]
        l = int.from_bytes(data[off+1:off+3], "little")
        method = data[off+3:off+3+l].decode()
        off += 3 + l

        args = []
        while off + 3 <= len(data):
            t = data[off]
            l = int.from_bytes(data[off+1:off+3], "little")
            v = data[off+3:off+3+l]
            args.append((t, v))
            off += 3 + l

        if method not in self.methods:
            resp = struct.pack("<HB", cid, 1)
            self.proto.send_payload(tlv_encode(TLV_RPC_RESP, resp), ack=False)
            return

        try:
            ret = self.methods[method](args) or []
            resp = struct.pack("<HB", cid, 0) + b"".join(ret)
        except Exception:
            resp = struct.pack("<HB", cid, 3)

        # RPC 响应同样不需要链路 ACK_REQ
        self.proto.send_payload(tlv_encode(TLV_RPC_RESP, resp), ack=False)

    def _on_resp(self, data, seq):
        cid, status = struct.unpack("<HB", data[:3])
        ret = data[3:]

        # 只接受当前 pending 的响应，避免另一端/旧请求的响应覆盖本次调用
        if cid not in self.pending:
            try:
                print(f"[RPC] drop resp cid={cid} status={status} (not pending) seq={seq}")
            except Exception:
                pass
            return

        self.pending[cid] = (status, ret)
