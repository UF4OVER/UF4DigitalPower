# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 02-12 21:49
#  @FileName: scan_connect_device.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------

from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtSerialPort import QSerialPortInfo

from app.Core.Session import SerialSession, SerialConfig
from Config import logger




class DeviceScanner(QObject):
    """
    设备扫描器：
    - 周期扫描串口
    - 检测指定 VID/PID 的设备插入与拔出
    - 自动管理 SerialSession 生命周期
    """

    device_connected = pyqtSignal(SerialSession)
    device_disconnected = pyqtSignal()

    def __init__(
        self,
        vid: int,
        pid: int,
        parent: Optional[QObject] = None,
        interval_ms: int = 1000,
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

    # ========= 对外接口 =========

    def start(self):
        logger.info("DeviceScanner started")
        self._timer.start()

    def stop(self):
        logger.info("DeviceScanner stopped")
        self._timer.stop()
        self._disconnect_device()

    def session(self) -> Optional[SerialSession]:
        return self._session

    # ========= 核心扫描逻辑 =========

    def _scan(self):
        port = self._find_matching_port()

        if port and self._current_port_name is None:
            self._connect_device(port)

        elif port is None and self._current_port_name is not None:
            self._disconnect_device()

    def _find_matching_port(self) -> Optional[QSerialPortInfo]:
        if self._vid == -1 or self._pid == -1:
            logger.warning("DeviceScanner: VID/PID 未配置，跳过扫描")
            self.stop()  # 当未配置 VID 和 PID 的时候不进行扫描
            return None

        for port in QSerialPortInfo.availablePorts():
            if (
                port.vendorIdentifier() == self._vid
                and port.productIdentifier() == self._pid
            ):
                return port

        return None

    # ========= 设备连接 / 断开 =========

    def _connect_device(self, port: QSerialPortInfo):
        port_name = port.portName()
        logger.info(
            f"DeviceScanner: 设备插入 {port_name} "
            f"(VID={port.vendorIdentifier()}, PID={port.productIdentifier()})"
        )

        self._current_port_name = port_name
        cfg = SerialConfig(port=port_name)

        try:
            self._session = SerialSession(cfg)
            self._session.open()

            logger.info(f"DeviceScanner: 串口已打开 {port_name}")
            self.device_connected.emit(self._session)

        except Exception as e:
            logger.exception(f"DeviceScanner: 串口打开失败 {port_name}")
            self._current_port_name = None
            self._session = None

    def _disconnect_device(self):
        logger.warning(
            f"DeviceScanner: 设备拔出 {self._current_port_name}"
        )

        if self._session:
            try:
                self._session.close()
            except Exception as e:
                logger.exception(f"DeviceScanner: 关闭串口时异常 {e}")

        self._session = None
        self._current_port_name = None

        self.device_disconnected.emit()

