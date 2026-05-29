# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/5/24
#  @FileName: test_chart_dashboard.py.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------
# tests/test_chart_dashboard.py

import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout

from app.core.data_hub import DataHub
from app.devices.dummy_power_device import DummyPowerDevice
from app.widgets.chart.chart_dashboard_widget import ChartDashboardWidget


class DemoWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Power Device Multi Chart Dashboard")
        self.resize(1200, 800)

        self.hub = DataHub(default_max_points=5000)

        self.device = DummyPowerDevice(self.hub)
        self.device.setup_channels()
        self.device.connect()

        self.dashboard = ChartDashboardWidget(self.hub, self)

        layout = QVBoxLayout(self)
        layout.addWidget(self.dashboard)

        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.on_data_timer)
        self.data_timer.start(20)

    def on_data_timer(self):
        self.device.tick()


def main():
    app = QApplication(sys.argv)

    window = DemoWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
