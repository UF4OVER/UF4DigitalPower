# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/5/24
#  @FileName: test_dummy_power_device.py.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
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