# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_opengl_chart.py
#  @FileType: 自动化测试文件，用来守住关键功能行为
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

# tests/test_opengl_chart.py

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout

from app.core.data_hub import DataHub
from app.devices.dummy_power_device import DummyPowerDevice
from app.widgets.chart.chart_model import ChartModel
from app.widgets.chart.realtime_chart_widget import RealtimeChartWidget


class DemoWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("F4CP / Power Device Chart Test")
        self.resize(1000, 600)

        self.hub = DataHub(default_max_points=3000)

        self.device = DummyPowerDevice(self.hub)
        self.device.setup_channels()
        self.device.connect()

        self.chart_model = ChartModel(self.hub)
        self.chart_model.set_time_window(10.0)
        self.chart_model.show_group("voltage")
        self.chart_model.show_group("power")

        self.chart = RealtimeChartWidget(self.chart_model, self)

        layout = QVBoxLayout(self)
        layout.addWidget(self.chart)

        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.on_data_timer)
        self.data_timer.start(20)  # 50Hz 模拟采样

    def on_data_timer(self):
        self.device.tick()


def main():
    app = QApplication(sys.argv)

    window = DemoWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
