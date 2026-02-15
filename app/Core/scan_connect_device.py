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

from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtSerialPort import QSerialPortInfo

from .serial_session import SerialSession, SerialConfig
from ..Config import SettingMangerInstance, logger

try:
    PORT_VID = int(SettingMangerInstance.get("port", "vid"))
    PORT_PID = int(SettingMangerInstance.get("port", "pid"))

    if (PORT_VID and PORT_PID) is not None :
        pass
    else:
        PORT_VID = -1
        PORT_PID = -1

    logger.info(f"Loaded from settings: VID={PORT_VID}, PID={PORT_PID}")
except Exception as e:
    logger.error(f"Failed to load VID/PID from settings:{e}")
    PORT_VID = -1
    PORT_PID = -1


class DeviceScanner(QObject):
    # 信号定义
    deviceConnected = pyqtSignal(object)  # 设备已连接 (SerialSession)
    deviceDisconnected = pyqtSignal()  # 设备已断开
    connectionError = pyqtSignal(str)  # 连接错误信息
    scanStatusChanged = pyqtSignal(bool)  # 扫描状态变化 (True=正在扫描)

    def __init__(self, parent=None, scan_interval=1000):
        """
        :param scan_interval: 扫描间隔（毫秒），默认1秒
        """
        super().__init__(parent)

        self._scan_interval = scan_interval
        self._serial_session = None  # 当前连接的设备
        self._target_port_name = None  # 目标端口名（用于断线后重连）
        self._is_scanning = False

        # 使用 QTimer 进行定时扫描（比 QObject.startTimer 更灵活）
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._scan_task)

    def start_scanning(self):
        """开始定时扫描"""
        if not self._is_scanning:
            self._is_scanning = True
            self._timer.start(self._scan_interval)
            self.scanStatusChanged.emit(True)
            logger.info("DeviceScanner: 开始扫描设备...")
            # 立即执行一次，不用等待定时器首次触发
            self._scan_task()

    def stop_scanning(self):
        """停止扫描"""
        if self._is_scanning:
            self._is_scanning = False
            self._timer.stop()
            self.scanStatusChanged.emit(False)
            logger.info("DeviceScanner: 停止扫描")

    def is_scanning(self) -> bool:
        """是否正在扫描"""
        return self._is_scanning

    def is_connected(self) -> bool:
        """当前是否已连接设备"""
        return (self._serial_session is not None and
                self._serial_session.isOpen())

    def get_session(self) -> SerialSession | None:
        """获取当前连接的设备会话"""
        return self._serial_session

    def disconnect_device(self):
        """主动断开当前设备"""
        if self._serial_session:
            logger.info(f"DeviceScanner: 主动断开设备 {self._target_port_name}")
            self._serial_session.close()
            self._serial_session = None
            self._target_port_name = None
            self.deviceDisconnected.emit()

    def _scan_task(self):
        """定时扫描任务"""
        # 1. 检查当前连接是否仍然有效
        if self._serial_session is not None:
            if not self._check_connection():
                # 连接已断开，清理状态，继续扫描
                self._handle_disconnection()
            else:
                # 连接正常，无需操作
                return

        # 2. 未连接，扫描并尝试连接
        self._try_connect()

    def _check_connection(self) -> bool:
        """检查当前连接是否仍然有效"""
        try:
            # 方法1：检查串口是否仍然打开
            if not self._serial_session.isOpen():
                return False

            return True

        except Exception as e:
            logger.warning(f"DeviceScanner: 检查连接状态时出错: {e}")
            return False

    def _handle_disconnection(self):
        """处理设备断开"""
        logger.warning(f"DeviceScanner: 设备 {self._target_port_name} 已断开")
        self._serial_session = None
        self._target_port_name = None
        self.deviceDisconnected.emit()
        # 继续扫描（定时器仍在运行）

    def _try_connect(self):
        """尝试连接设备"""
        port = self._find_matching_port()

        if port is None:
            # 未找到设备，继续等待下次扫描
            return

        port_name = port.portName()
        logger.info(f"DeviceScanner: 发现目标设备 {port_name}，尝试连接...")

        try:
            # 创建配置并连接
            cfg = SerialConfig(port_name)
            session = SerialSession(cfg)

            # 验证连接是否成功打开
            session.open()
            if not session.is_open:
                raise Exception("串口打开失败")

            # 连接成功
            self._serial_session = session
            self._target_port_name = port_name
            logger.info(f"DeviceScanner: 成功连接到 {port_name}")
            self.deviceConnected.emit(session)

        except Exception as e:
            error_msg = f"连接设备 {port_name} 失败: {e}"
            logger.error(f"DeviceScanner: {error_msg}")
            self.connectionError.emit(error_msg)
            # 连接失败，继续扫描

    def _find_matching_port(self):
        """扫描并返回第一个匹配的端口"""
        if PORT_VID == -1 or PORT_PID == -1:
            logger.warning("DeviceScanner: VID/PID 未配置，跳过扫描")
            return None

        for port in QSerialPortInfo.availablePorts():
            vid = port.vendorIdentifier()
            pid = port.productIdentifier()
            port_name = port.portName()

            # 调试日志（可选，生产环境可注释掉）
            logger.debug(f"DeviceScanner: 检查端口 {port_name} (VID={vid}, PID={pid})")

            # 跳过没有 VID/PID 的端口
            if not port.hasVendorIdentifier() or not port.hasProductIdentifier():
                continue

            # 检查是否匹配（注意：没有 else return！）
            if vid == PORT_VID and pid == PORT_PID:
                logger.info(f"DeviceScanner: 匹配成功 {port_name} (VID={vid}, PID={pid})")
                return port

        # 循环结束都没找到才返回 None
        logger.debug(f"DeviceScanner: 未找到匹配 VID={PORT_VID}, PID={PORT_PID} 的设备")
        return None