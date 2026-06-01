# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/5/14
#  @FileName: session_bluetooth.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------
from types import SimpleNamespace

from PyQt5.QtBluetooth import QBluetoothSocket, QBluetoothAddress, QBluetoothServiceInfo, QBluetoothUuid
from PyQt5.QtCore import QObject, QIODevice, QCoreApplication

from config import logger
from .session_serial import SerialState, StateEvent,TxEvent, SerialEventType, ErrorEvent, RxEvent


class PowerBluetoothSession(QObject):
    def __init__(self, name: str, address: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.address = address
        self.cfg = SimpleNamespace(port=name)
        self._eventReceiver = None
        self._socket = None

    def set_event_receiver(self, receiver) -> None:
        self._eventReceiver = receiver

    @property
    def is_open(self) -> bool:
        return bool(self._socket) and self._socket.isOpen()

    def open(self) -> None:
        if self.is_open:
            return
        if (
            QBluetoothSocket is None
            or QBluetoothAddress is None
            or QBluetoothUuid is None
            or QBluetoothServiceInfo is None
        ):
            message = "当前环境不支持 Qt Bluetooth"
            logger.error(f"{self.__class__.__name__}: {message}")
            raise RuntimeError(message)

        self._postEvent(StateEvent(SerialState.OPENING))
        self._socket = QBluetoothSocket(QBluetoothServiceInfo.RfcommProtocol)
        self._socket.readyRead.connect(self._onReadyRead)
        self._socket.error.connect(self._onError)
        self._socket.connected.connect(lambda: self._postEvent(StateEvent(SerialState.OPEN)))
        self._socket.disconnected.connect(lambda: self._postEvent(StateEvent(SerialState.CLOSED)))
        self._socket.connectToService(
            QBluetoothAddress(self.address),
            QBluetoothUuid(QBluetoothUuid.SerialPort),
            QIODevice.OpenModeFlag.ReadWrite,
        )

    def close(self) -> None:
        if self._socket:
            self._socket.close()
            self._socket.deleteLater()
            self._socket = None
        self._postEvent(StateEvent(SerialState.CLOSED))

    def write(self, data: bytes) -> int:
        if not self.is_open:
            message = "蓝牙设备未连接"
            logger.error(f"{self.__class__.__name__}: {message}")
            raise RuntimeError(message)
        written = int(self._socket.write(data))
        self._postEvent(TxEvent(data))
        return written

    def event(self, event) -> bool:
        if event.type() == int(SerialEventType.SEND):
            payload = getattr(event, "payload", None)
            data = getattr(payload, "data", b"") if payload is not None else b""
            if data:
                try:
                    self.write(data)
                except Exception as exc:
                    self._postEvent(ErrorEvent(code=-1, message=str(exc), fatal=False))
            return True
        return super().event(event)

    def _postEvent(self, event) -> None:
        if self._eventReceiver is not None:
            QCoreApplication.postEvent(self._eventReceiver, event)

    def _onReadyRead(self) -> None:
        if not self._socket:
            return
        raw = self._socket.readAll()
        data = raw.data() if hasattr(raw, "data") else bytes(raw)
        if data:
            self._postEvent(RxEvent(data))

    def _onError(self, error) -> None:
        message = self._socket.errorString() if self._socket else str(error)
        self._postEvent(ErrorEvent(code=int(error), message=message, fatal=True))
        self._postEvent(StateEvent(SerialState.ERROR, info=message))
