# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_dummy_power_device.py
#  @FileType: 自动化测试文件，用来守住关键功能行为
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

import time

from app.core.data_hub import DataHub
from app.devices.dummy_power_device import DummyPowerDevice


def main():
    hub = DataHub(default_max_points=1000)

    dev = DummyPowerDevice(hub)
    dev.setup_channels()
    dev.connect()

    for _ in range(50):
        dev.tick()
        time.sleep(0.02)

    print("connected:", dev.is_connected())
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