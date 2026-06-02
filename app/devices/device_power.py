# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: device_power.py
#  @FileType: 设备模型文件，封装具体设备的数据和操作入口
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

from app.core.device_base import DeviceBase
from app.core.data_hub import DataHub
from app.core.channel import ChannelConfig


class PowerDevice(DeviceBase):
    """
    真实数字电源设备适配层。

    它不负责串口通信，也不负责协议拆包。
    它只负责：
    1. 注册数字电源相关通道
    2. 接收解析后的 frame_data
    3. 计算派生量 pin / pout / efficiency
    4. 推送到 DataHub
    """

    def __init__(self, data_hub: DataHub, name: str = "Power Device"):
        super().__init__(name, data_hub)

    def setup_channels(self) -> None:
        self.data_hub.register_channels([
            ChannelConfig("vin", "输入电压", "V", 0, 50, precision=2, group="voltage"),
            ChannelConfig("vout", "输出电压", "V", 0, 50, precision=2, group="voltage"),

            ChannelConfig("iin", "输入电流", "A", -20, 20, precision=3, group="current"),
            ChannelConfig("iout", "输出电流", "A", -20, 20, precision=3, group="current"),

            ChannelConfig("temp", "温度", "℃", 0, 120, precision=1, group="thermal"),

            ChannelConfig("pin", "输入功率", "W", 0, 800, precision=2, group="power"),
            ChannelConfig("pout", "输出功率", "W", 0, 800, precision=2, group="power"),

            ChannelConfig("efficiency", "效率", "%", 0, 100, precision=1, group="efficiency"),

            ChannelConfig("state", "状态机", "", None, None, precision=0, visible=False, group="status"),
            ChannelConfig("fault", "故障码", "", None, None, precision=0, visible=False, group="status"),
        ])

    def on_frame(self, frame_data: dict) -> None:
        vin = self._get_float(frame_data, "vin")
        vout = self._get_float(frame_data, "vout")
        iin = self._get_float(frame_data, "iin")
        iout = self._get_float(frame_data, "iout")
        temp = self._get_float(frame_data, "temp")

        data: dict[str, float] = {}

        if vin is not None:
            data["vin"] = vin

        if vout is not None:
            data["vout"] = vout

        if iin is not None:
            data["iin"] = iin

        if iout is not None:
            data["iout"] = iout

        if temp is not None:
            data["temp"] = temp

        pin = None
        pout = None

        if vin is not None and iin is not None:
            pin = vin * iin
            data["pin"] = pin

        if vout is not None and iout is not None:
            pout = vout * iout
            data["pout"] = pout

        if pin is not None and pout is not None and abs(pin) > 0.001:
            efficiency = pout / pin * 100.0
            data["efficiency"] = max(0.0, min(efficiency, 100.0))

        state = self._get_float(frame_data, "state")
        fault = self._get_float(frame_data, "fault")

        if state is not None:
            data["state"] = state

        if fault is not None:
            data["fault"] = fault

        self.data_hub.push_many(data)

    @staticmethod
    def _get_float(data: dict, key: str) -> float | None:
        value = data.get(key)

        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None