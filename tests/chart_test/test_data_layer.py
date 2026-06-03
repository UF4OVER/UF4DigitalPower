# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_data_layer.py
#  @FileType: 自动化测试文件，用来守住关键功能行为
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

import time

from app.core.channel import ChannelConfig
from app.core.data_hub import DataHub


def main():
    hub = DataHub(default_max_points=1000)

    hub.register_channels([
        ChannelConfig("vin", "输入电压", "V", 0, 50),
        ChannelConfig("vout", "输出电压", "V", 0, 50),
        ChannelConfig("iout", "输出电流", "A", 0, 10),
        ChannelConfig("temp", "温度", "℃", 0, 100),
        ChannelConfig("power", "输出功率", "W", 0, 300),
    ])

    for i in range(10):
        vout = 12.0 + i * 0.1
        iout = 1.0 + i * 0.05

        hub.push_many({
            "vin": 16.8,
            "vout": vout,
            "iout": iout,
            "temp": 35.0 + i * 0.2,
            "power": vout * iout,
        })

        time.sleep(0.02)

    print("latest:", hub.latest_values())

    for channel in hub.visible_channels():
        latest = channel.latest()
        if latest is None:
            continue

        print(
            channel.config.key,
            channel.config.name,
            channel.config.format_value(latest.value),
            "points:",
            len(channel),
        )


if __name__ == "__main__":
    main()