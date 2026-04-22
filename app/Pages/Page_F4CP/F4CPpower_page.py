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

from Config import logger, SettingMangerInstance
from ...Core import DeviceScanner, SerialSession

try:
    PORT_VID = int(SettingMangerInstance.get("port", "vid"))
    PORT_PID = int(SettingMangerInstance.get("port", "pid"))

    if (PORT_VID and PORT_PID) is not None:
        pass
    else:
        PORT_VID = -1
        PORT_PID = -1

    logger.info(f"Loaded from settings: VID={PORT_VID}, PID={PORT_PID}")
except Exception as e:
    logger.error(f"Failed to load VID/PID from settings:{e}")
    PORT_VID = -1
    PORT_PID = -1


class F4CPowerPage(QWidget, Ui_Frame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.__init_controlName()

        self.scanner = DeviceScanner(
            vid=PORT_VID,
            pid=PORT_PID,
        )

        self.scanner.device_connected.connect(self.on_device_connected)
        self.scanner.device_disconnected.connect(self.on_device_disconnected)

        self.scanner.start()

    def __init_controlName(self):
        self.hostNumber = self.lineEdit_2
        self.softStartTime = self.lineEdit
        self.textOutput = self.textEdit

    def on_device_connected(self, session: SerialSession):
        logger.info("UI: 设备已连接")
        session.set_event_receiver(self)

    def on_device_disconnected(self):  # NOQA
        logger.info("UI: 设备已断开")

    def closeEvent(self, event):
        self.scanner.stop()
        super().closeEvent(event)

    def exportDataJson(self):
        """ 导出数据为 JSON 格式 """
        data = {
            "hostNumber": self.hostNumber.text(),
            "softStartTime": self.softStartTime.text(),
        }
        return data

    def importDataJson(self, data):
        """ 从 JSON 数据导入 """
        self.hostNumber.setText(data.get("hostNumber", ""))
        self.softStartTime.setText(data.get("softStartTime", ""))