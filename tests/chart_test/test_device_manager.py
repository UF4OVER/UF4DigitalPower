# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_device_manager.py
#  @FileType: 自动化测试文件，用来守住关键功能行为
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

# tests/test_device_manager.py

import time

from app.core.data_hub import DataHub
from app.manager.manager_device import DeviceManager
from app.devices.dummy_power_device import DummyPowerDevice
from app.devices.device_power import PowerDevice


def main():
    hub = DataHub(default_max_points=1000)
    manager = DeviceManager()

    dummy_power = DummyPowerDevice(hub)
    real_power = PowerDevice(hub, name="UF4 Digital Power")

    manager.register("dummy_power", dummy_power)
    manager.register("power", real_power)

    manager.connect("dummy_power")
    manager.connect("power")

    print("devices:", manager.keys())
    print("connected:", [dev.name for dev in manager.connected_devices()])

    for _ in range(20):
        dummy_power.tick()
        time.sleep(0.02)

    real_power.on_frame({
        "vin": 16.8,
        "vout": 12.0,
        "iin": 2.5,
        "iout": 3.0,
        "temp": 39.2,
        "state": 3,
        "fault": 0,
    })

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

    manager.disconnect_all()
    print("connected after disconnect:", [dev.name for dev in manager.connected_devices()])


if __name__ == "__main__":
    main()