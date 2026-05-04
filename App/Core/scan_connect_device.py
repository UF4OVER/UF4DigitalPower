# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 02-12 21:49
#  @FileName: scan_connect_device.py
# -------------------------------

from typing import Optional

from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtSerialPort import QSerialPortInfo

from Config import logger
from App.Core.Session import SerialConfig, SerialSession


class DeviceScanner(QObject):
    device_connected = pyqtSignal(SerialSession)
    device_disconnected = pyqtSignal()

    def __init__(
        self,
        vid: int,
        pid: int,
        parent: Optional[QObject] = None,
        interval_ms: int = 1500,
    ):
        super().__init__(parent)

        self._vid = vid
        self._pid = pid
        self._current_port_name: Optional[str] = None
        self._session: Optional[SerialSession] = None

        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._scan)

        logger.info(
            f"DeviceScanner initialized (VID={vid}, PID={pid}, interval={interval_ms}ms)"
        )

    def start(self):
        logger.info("DeviceScanner started")
        self._timer.start()

    def stop(self):
        logger.info("DeviceScanner stopped")
        self._timer.stop()
        self._disconnect_device()

    def session(self) -> Optional[SerialSession]:
        return self._session

    def _scan(self):
        port = self._find_matching_port()

        if port and self._current_port_name is None:
            self._connect_device(port)
        elif port is None and self._current_port_name is not None:
            self._disconnect_device()

    def _find_matching_port(self) -> Optional[QSerialPortInfo]:
        if self._vid == -1 or self._pid == -1:
            logger.warning("DeviceScanner: VID/PID not configured, stop scanning")
            self.stop()
            return None

        for port in QSerialPortInfo.availablePorts():
            if port.vendorIdentifier() == self._vid and port.productIdentifier() == self._pid:
                return port

        return None

    def _connect_device(self, port: QSerialPortInfo):
        port_name = port.portName()
        logger.info(
            f"DeviceScanner: device inserted {port_name} "
            f"(VID={port.vendorIdentifier()}, PID={port.productIdentifier()})"
        )

        self._current_port_name = port_name
        cfg = SerialConfig(port=port_name)

        try:
            self._session = SerialSession(cfg)
            self._session.open()

            logger.info(f"DeviceScanner: serial port opened {port_name}")
            self.device_connected.emit(self._session)
        except Exception:
            logger.exception(f"DeviceScanner: failed to open serial port {port_name}")
            self._current_port_name = None
            self._session = None

    def _disconnect_device(self):
        if self._current_port_name is not None:
            logger.warning(f"DeviceScanner: device removed {self._current_port_name}")

        if self._session:
            try:
                self._session.close()
            except Exception as exc:
                logger.exception(f"DeviceScanner: failed to close serial port: {exc}")

        self._session = None
        self._current_port_name = None
        self.device_disconnected.emit()
