# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/5/24
#  @FileName: dummy_power_device.py.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 假设备模拟数据
#  @Python  : 
# -------------------------------
import math
import random
import time
from typing import Optional

from app.core.device_base import DeviceBase
from app.core.data_hub import DataHub
from app.core.channel import ChannelConfig


class DummyPowerDevice(DeviceBase):
    """
    模拟数字电源设备。

    用途：
    - 不接真实硬件时测试 DataHub
    - 后续测试实时曲线
    - 验证电压、电流、温度、功率通道
    """

    def __init__(self, data_hub: DataHub):
        super().__init__("Dummy Power Device", data_hub)
        self.start_time = time.time()

    def setup_channels(self) -> None:
        self.data_hub.register_channels([
            ChannelConfig("vin", "输入电压", "V", 0, 50, precision=2, group="voltage"),
            ChannelConfig("vout", "输出电压", "V", 0, 50, precision=2, group="voltage"),

            ChannelConfig("iin", "输入电流", "A", 0, 20, precision=3, group="current"),
            ChannelConfig("iout", "输出电流", "A", 0, 20, precision=3, group="current"),

            ChannelConfig("temp", "温度", "℃", 0, 120, precision=1, group="thermal"),

            ChannelConfig("pin", "输入功率", "W", 0, 600, precision=2, group="power"),
            ChannelConfig("pout", "输出功率", "W", 0, 600, precision=2, group="power"),

            ChannelConfig("efficiency", "效率", "%", 0, 100, precision=1, group="efficiency"),
        ])
    def on_frame(self, frame_data: dict) -> None:
        self.data_hub.push_many(frame_data)

    def tick(self, t: Optional[float] = None) -> None:
        now = time.time() if t is None else t
        elapsed = now - self.start_time

        vin = 16.8 + math.sin(elapsed * 0.5) * 0.15
        vout = 12.0 + math.sin(elapsed * 1.2) * 0.5

        iout = 2.0 + math.sin(elapsed * 0.8) * 1.2 + random.uniform(-0.05, 0.05)
        iout = max(iout, 0.0)

        efficiency = 88.0 + math.sin(elapsed * 0.3) * 3.0
        efficiency = max(1.0, min(efficiency, 99.0))

        pout = vout * iout
        pin = pout / (efficiency / 100.0)

        iin = pin / vin if vin > 0.1 else 0.0
        temp = 35.0 + math.sin(elapsed * 0.2) * 3.0 + pout * 0.02

        self.data_hub.push_many({
            "vin": vin,
            "vout": vout,
            "iin": iin,
            "iout": iout,
            "temp": temp,
            "pin": pin,
            "pout": pout,
            "efficiency": efficiency,
        }, t=now)