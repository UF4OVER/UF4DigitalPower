# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/5/24
#  @FileName: test_power_device.py.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------


# tests/test_power_device.py

from app.core.data_hub import DataHub
from app.devices.device_power import PowerDevice


def main():
    hub = DataHub(default_max_points=1000)

    dev = PowerDevice(hub, name="UF4 Digital Power")
    dev.setup_channels()
    dev.connect()

    dev.on_frame({
        "vin": 16.8,
        "vout": 12.05,
        "iin": 2.8,
        "iout": 3.5,
        "temp": 38.6,
        "state": 3,
        "fault": 0,
    })

    print("connected:", dev.is_connected())
    print("latest:", hub.latest_values())

    for channel in hub.channels():
        latest = channel.latest()
        if latest is None:
            continue

        print(
            channel.config.key,
            channel.config.name,
            channel.config.format_value(latest.value),
            "visible:",
            channel.config.visible,
            "points:",
            len(channel),
        )


if __name__ == "__main__":
    main()