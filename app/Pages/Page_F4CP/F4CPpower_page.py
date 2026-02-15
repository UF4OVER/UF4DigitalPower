# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : dark
#  @Time    : 2026 - 02-10 18:39
#  @FileName: F4CPpower_page.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------

from PyQt5.QtWidgets import QWidget

from .F4CPui import Ui_Frame
from ...Config import logger
from ...Core import DeviceScanner
from ...Core import SerialSession


class F4CPowerPage(QWidget, Ui_Frame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        # 创建扫描器（不需要手动管理定时器）
        self._scanner = DeviceScanner(self, scan_interval=1000)  # 1秒扫描一次

        # 连接信号
        self._scanner.deviceConnected.connect(self._on_device_connected)
        self._scanner.deviceDisconnected.connect(self._on_device_disconnected)
        self._scanner.connectionError.connect(self._on_connection_error)

        # 启动扫描
        self._scanner.start_scanning()

        self.__init_controlName()

    def __init_controlName(self):
        self.hostNumber = self.lineEdit_2
        self.softStartTime = self.lineEdit
        self.textOutput = self.textEdit

    def _on_device_connected(self, session: SerialSession):
        """设备已连接"""
        logger.info(f"{self.__class__.__name__}: 设备已连接")
        self.textOutput.append("✅ 设备已连接")

        # 设置事件接收器
        session.set_event_receiver(self)
        session.on_tx = lambda b: self.textOutput.append(b)

        # 更新UI状态
        # self.status_label.setText("已连接")
        # self.connect_btn.setEnabled(False)

    def _on_device_disconnected(self):
        """设备已断开"""
        logger.warning(f"{self.__class__.__name__}: 设备已断开")
        self.textOutput.append("❌ 设备已断开，正在重新扫描...")

        # 更新UI状态
        # self.status_label.setText("未连接 - 扫描中...")

    def _on_connection_error(self, error_msg: str):
        """连接错误"""
        self.textOutput.append(f"⚠️ 连接错误: {error_msg}")

    def closeEvent(self, event):
        """页面关闭时清理"""
        # 停止扫描器（会自动断开设备）
        self._scanner.stop_scanning()
        self._scanner.disconnect_device()
        event.accept()