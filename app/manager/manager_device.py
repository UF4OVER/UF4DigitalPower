# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: manager_device.py
#  @FileType: 设备管理文件，负责设备实例的注册和查询
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from typing import Optional

from app.core.device_base import DeviceBase


class DeviceManager:
    """
    设备管理器。

    负责：
    - 注册设备
    - 获取设备
    - 连接/断开设备
    - 统一清理设备
    """

    def __init__(self):
        self._devices: dict[str, DeviceBase] = {}

    def register(self, key: str, device: DeviceBase, replace: bool = False) -> None:
        """
        注册设备。

        key 建议使用：
        - "power"
        - "dummy_power"
        - "bms"
        - "load"
        """

        if key in self._devices and not replace:
            return

        self._devices[key] = device
        device.setup_channels()

    def unregister(self, key: str) -> None:
        device = self._devices.pop(key, None)

        if device is not None and device.is_connected():
            device.disconnect()

    def get(self, key: str) -> Optional[DeviceBase]:
        return self._devices.get(key)

    def has(self, key: str) -> bool:
        return key in self._devices

    def keys(self) -> list[str]:
        return list(self._devices.keys())

    def devices(self) -> list[DeviceBase]:
        return list(self._devices.values())

    def connect(self, key: str) -> bool:
        device = self.get(key)

        if device is None:
            return False

        device.connect()
        return True

    def disconnect(self, key: str) -> bool:
        device = self.get(key)

        if device is None:
            return False

        device.disconnect()
        return True

    def disconnect_all(self) -> None:
        for device in self._devices.values():
            if device.is_connected():
                device.disconnect()

    def connected_devices(self) -> list[DeviceBase]:
        return [
            device
            for device in self._devices.values()
            if device.is_connected()
        ]

    def clear(self) -> None:
        self.disconnect_all()
        self._devices.clear()