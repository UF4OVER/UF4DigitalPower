# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: device_base.py
#  @FileType: 核心基础设施文件，提供设备、数据和通用工具能力
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from abc import ABC, abstractmethod

from .data_hub import DataHub


class DeviceBase(ABC):
    """
    设备适配基类。
    设备适配器负责将具体设备的数据转换成 DataHub 能理解的格式。
     - setup_channels() 注册该设备需要的数据通道，通常在 connect() 之后调用。
     - on_frame(frame_data) 收到一帧解析后的数据后调用，frame_data 是一个 dict，包含该帧的所有数据。
     - connect() 连接设备，建立通信。
     - disconnect() 断开设备连接，释放资源。
     - is_connected() 返回设备是否已连接。
     - 设备适配器不负责数据存储，所有数据都通过 DataHub 存储和访问。
    """

    def __init__(self, name: str, data_hub: DataHub):
        self.name = name
        self.data_hub = data_hub
        self.connected = False

    @abstractmethod
    def setup_channels(self) -> None:
        """
        注册该设备需要的数据通道。
        """
        raise NotImplementedError

    @abstractmethod
    def on_frame(self, frame_data: dict) -> None:
        """
        收到一帧解析后的数据后调用。
        """
        raise NotImplementedError

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected