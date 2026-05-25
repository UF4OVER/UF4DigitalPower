# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/5/24
#  @FileName: test_chart_model.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------
# tests/test_chart_model.py

import time

from app.core.data_hub import DataHub
from app.devices.dummy_power_device import DummyPowerDevice
from app.widgets.chart.chart_model import ChartModel


def main():
    hub = DataHub(default_max_points=1000)

    dev = DummyPowerDevice(hub)
    dev.setup_channels()
    dev.connect()

    for _ in range(100):
        dev.tick()
        time.sleep(0.01)

    model = ChartModel(hub)
    model.set_time_window(2.0)

    snapshot = model.build_snapshot()

    print("x_range:", snapshot.x_range)
    print("y_range:", snapshot.y_range)
    print("curve count:", len(snapshot.curves))

    for curve in snapshot.curves:
        print(
            curve.key,
            curve.name,
            "points:",
            len(curve.points),
        )

        if curve.points:
            first = curve.points[0]
            last = curve.points[-1]

            print(
                "  first:",
                f"raw=({first.raw_x:.3f}, {first.raw_y:.3f})",
                f"gl=({first.gl_x:.3f}, {first.gl_y:.3f})",
            )

            print(
                "  last :",
                f"raw=({last.raw_x:.3f}, {last.raw_y:.3f})",
                f"gl=({last.gl_x:.3f}, {last.gl_y:.3f})",
            )


if __name__ == "__main__":
    main()