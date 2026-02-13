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
from PyQt5.QtCore import QObject
from PyQt5.QtSerialPort import QSerialPortInfo, QSerialPort

from .serial_session import SerialEventType, SerialEvent, RxEvent, TxEvent, SendEvent, SerialSession
from .const import DeviceData


class DeviceScanner(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.serial = None
    def scanDevices(self):
        """
        扫描当前系统串口，返回匹配 VID/PID 的设备信息列表
        """
        devices = []

        for port in QSerialPortInfo.availablePorts():
            if not port.hasVendorIdentifier() or not port.hasProductIdentifier():
                continue

            if (port.vendorIdentifier() == DeviceData.VID and
                port.productIdentifier() == DeviceData.PID):

                device_info = {
                    "port": port.portName(),
                    "description": port.description(),
                    "manufacturer": port.manufacturer(),
                    "serial_number": port.serialNumber(),
                    "vid": port.vendorIdentifier(),
                    "pid": port.productIdentifier(),
                }
                devices.append(device_info)

        return devices



    def connectFirstDevice(self, baudrate=115200):
        """
        扫描设备，找到第一个匹配的 VID/PID 并打开串口
        """
        devices = self.scanDevices()
        if not devices:
            return None, "未找到匹配的设备"
