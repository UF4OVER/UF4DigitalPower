# -*- coding: utf-8 -*-

from __future__ import annotations

import time

from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, Optional

from PyQt5.QtCore import QIODevice, QEvent, QCoreApplication, QObject, QMutex, QMutexLocker
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo

from config import logger

class SerialEventType(IntEnum):
    RX = QEvent.registerEventType()
    TX = QEvent.registerEventType()
    ERROR = QEvent.registerEventType()
    SEND = QEvent.registerEventType()
    STATE = QEvent.registerEventType()


class SerialEvent(QEvent):
    def __init__(self, etype: SerialEventType):  # NOQA
        super().__init__(QEvent.Type(int(etype)))
        self.timestamp = time.monotonic()


@dataclass
class RxPayload:
    data: bytes


class RxEvent(SerialEvent):
    def __init__(self, data: bytes):
        super().__init__(SerialEventType.RX)
        self.payload = RxPayload(data=data)


@dataclass
class TxPayload:
    data: bytes


class TxEvent(SerialEvent):
    def __init__(self, data: bytes):
        super().__init__(SerialEventType.TX)
        self.payload = TxPayload(data=data)


@dataclass
class SendPayload:
    data: bytes


class SendEvent(SerialEvent):
    def __init__(self, data: bytes):
        super().__init__(SerialEventType.SEND)
        self.payload = SendPayload(data=data)


@dataclass
class ErrorPayload:
    code: int
    message: str
    fatal: bool = False


class ErrorEvent(SerialEvent):
    def __init__(self, code: int, message: str, fatal: bool = False):
        super().__init__(SerialEventType.ERROR)
        self.payload = ErrorPayload(
            code=code,
            message=message,
            fatal=fatal,
        )


class SerialState(IntEnum):
    CLOSED = 0
    OPENING = 1
    OPEN = 2
    ERROR = 3


@dataclass
class StatePayload:
    state: SerialState
    info: Optional[str] = None


class StateEvent(SerialEvent):
    def __init__(self, state: SerialState, info: str | None = None):
        super().__init__(SerialEventType.STATE)
        self.payload = StatePayload(state=state, info=info)


def listSerialPorts() -> list[str]:
    """
    返回串口列表字符串
    :return: str(portName)
    """

    return [p.portName() for p in QSerialPortInfo.availablePorts()]

def listSerialPortInfos() -> list[QSerialPortInfo]:
    """
    返回串口列表对象
    :return: QSerialPortInfo
    """
    return QSerialPortInfo.availablePorts()

@dataclass
class SerialConfig:
    # 默认配置
    port: str | None
    baudrate: int | QSerialPort.BaudRate = 921600
    bytesize: QSerialPort.DataBits = QSerialPort.DataBits.Data8  # 8位数据位
    parity: QSerialPort.Parity = QSerialPort.Parity.NoParity  # 无校验位
    stopbits: QSerialPort.StopBits = QSerialPort.StopBits.OneStop  # NOQA 停止位
    read_timeout_s: float = 0.1  # 超时时间


class SerialSession(QObject):
    def __init__(self, cfg: SerialConfig,_event_receiver: Optional[QObject] = None):
        super().__init__()

        # 事件接收器
        self._event_receiver: Optional[QObject] = _event_receiver

        # 回调函数
        self.on_rx: Optional[Callable[[bytes], None]] = None
        self.on_tx: Optional[Callable[[bytes], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None

        self._write_lock = QMutex()
        # protect access to the event receiver when set from different threads
        self._event_lock = QMutex()

        self._ser = None
        self.cfg = cfg

    def set_event_receiver(self, receiver: Optional[QObject]) -> None:
        """设置将接收本次会话发布的Qt事件的QObject。

        如果设置为 None，事件将通过 Python 回调传递
        （on_rx/on_tx/on_error）作为备选方案。

        接收方必须是QObject（或无）的。该任务受保护
        通过互斥体实现，以便在不同线程调用时更安全。
        """
        if receiver is not None and not isinstance(receiver, QObject):
            raise TypeError("event receiver must be a QObject or None")

        with QMutexLocker(self._event_lock):
            self._event_receiver = receiver


    def open(self):
        if self.is_open:
            return
        self._post_event(StateEvent(SerialState.OPENING))
        self._ser = QSerialPort()  # 创建端口
        self._ser.setPortName(self.cfg.port)  # 端口名称
        self._ser.setBaudRate(self.cfg.baudrate)  # 波特率

        self._ser.setDataBits(self.cfg.bytesize)
        self._ser.setParity(self.cfg.parity)
        self._ser.setStopBits(self.cfg.stopbits)

        # 打开串口
        if not self._ser.open(QIODevice.OpenModeFlag.ReadWrite):
            # error() 返回 QSerialPort.SerialPortError 枚举
            error_code = self._ser.error()
            error_str = self._ser.errorString()
            message = (
                f"串口打开失败 {self.cfg.port}: "
                f"{error_str} (代码: {error_code})"
            )
            logger.error(f"{self.__class__.__name__}: {message}")
            raise RuntimeError(message)
        self._ser.readyRead.connect(self._on_ready_read)
        self._ser.errorOccurred.connect(self._on_error_occurred)
        self._post_event(StateEvent(SerialState.OPEN))

    @property
    def is_open(self) -> bool:
        return bool(self._ser) and self._ser.isOpen()

    def close(self):
        if not self._ser:
            self._post_event(StateEvent(SerialState.CLOSED))
            return

        if self._ser.isOpen():
            self._ser.readyRead.disconnect()
            self._ser.errorOccurred.disconnect()
            self._ser.close()

        self._ser = None
        self._post_event(StateEvent(SerialState.CLOSED))

    def write(self, data: bytes) -> int:
        if not self.is_open:
            message = "Serial port is not open"
            logger.error(f"{self.__class__.__name__}: {message}")
            raise RuntimeError(message)
        if not data:
            return 0

        with QMutexLocker(self._write_lock):  # PyQt 的 QMutex 并不完全兼容 Python 的 with 语法，需要用 QMutexLocker 来自动解锁
            written = self._ser.write(data)
            if written != len(data):
                message = f"串口写入不完整: 期望 {len(data)} 字节，实际 {written} 字节"
                logger.error(f"{self.__class__.__name__}: {message}")
                raise RuntimeError(message)
            timeout_ms = max(500, int(getattr(self.cfg, "read_timeout_s", 0.1) * 1000))
            if not self._ser.waitForBytesWritten(timeout_ms):
                message = f"串口写入超时: {self._ser.errorString()}"
                logger.error(f"{self.__class__.__name__}: {message}")
                raise RuntimeError(message)
            logger.info(f"{self.__class__.__name__} 写入数据: {data.hex()}")

        self._post_event(TxEvent(data))
        return len(data)

    def _post_event(self, evt: SerialEvent):
        if self._event_receiver is not None:
            QCoreApplication.postEvent(self._event_receiver, evt)
        else:
            # fallback to callbacks
            if isinstance(evt, RxEvent) and self.on_rx:
                self.on_rx(evt.payload.data)
            elif isinstance(evt, TxEvent) and self.on_tx:
                self.on_tx(evt.payload.data)
            elif isinstance(evt, ErrorEvent) and self.on_error:
                self.on_error(RuntimeError(evt.payload.message))

    def _on_ready_read(self):
        if not self._ser:
            return

        raw = self._ser.readAll()
        data = raw.data() if hasattr(raw, 'data') else bytes(raw)

        if data:
            self._post_event(RxEvent(data))

    def _on_error_occurred(self, err):
        if err == QSerialPort.SerialPortError.NoError:
            return
        msg = self._ser.errorString() if self._ser else str(err)
        self._post_event(ErrorEvent(code=int(err), message=msg, fatal=True))
        self._post_event(StateEvent(SerialState.ERROR, info=msg))

    def event(self, e: QEvent):
        # 处理 从 UI 发布的发送事件：在该对象的线程中执行写入
        try:
            if e.type() == int(SerialEventType.SEND):
                payload = getattr(e, 'payload', None)
                data = getattr(payload, 'data', None) if payload is not None else None
                if data:
                    # perform write; write() will post TxEvent on success
                    try:
                        # write() expects port to be open
                        self.write(data)
                    except Exception as exc:
                        # notify UI of error
                        logger.error(f"{self.__class__.__name__}: {exc}")
                        self._post_event(ErrorEvent(code=-1, message=str(exc), fatal=True))
                        self._post_event(StateEvent(SerialState.ERROR, info=str(exc)))
                return True
        except Exception as exc:
            logger.error(f"{self.__class__.__name__}: {e}")
            pass
        return super().event(e)
