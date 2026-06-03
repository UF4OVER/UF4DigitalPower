# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_pyqtgraph_chart_widget.py
#  @FileType: 自动化测试文件，用来守住关键功能行为
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from app.core.channel import ChannelConfig
from app.core.data_hub import DataHub
from app.widgets.chart.chart_model import ChartModel
from app.widgets.chart.pyqtgraph_chart_widget import PyQtGraphChartWidget
from app.widgets.chart.realtime_chart_widget import RealtimeChartWidget


class PyQtGraphChartWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _build_chart(self) -> RealtimeChartWidget:
        hub = DataHub(default_max_points=100)
        hub.register_channels(
            [
                ChannelConfig("vin", "输入电压", "V", precision=3, group="voltage", color=(47, 128, 237)),
                ChannelConfig("iout", "输出电流", "A", precision=3, group="current", color=(235, 87, 87)),
            ]
        )
        now = time.time()
        for index in range(20):
            hub.push_many(
                {"vin": 12.0 + index * 0.1, "iout": 1.0 + index * 0.01},
                t=now + index * 0.05,
            )

        model = ChartModel(hub)
        model.set_time_window(5.0)
        chart = RealtimeChartWidget(model)
        chart.resize(800, 420)
        chart.mark_data_dirty()
        chart.update_chart()
        return chart

    def test_realtime_chart_uses_pyqtgraph_backend(self):
        chart = self._build_chart()

        try:
            self.assertIsInstance(chart.chart_widget, PyQtGraphChartWidget)
            self.assertIsNotNone(chart.chart_widget.latest_snapshot)
            self.assertEqual(set(chart.chart_widget._curves), {"vin", "iout"})
        finally:
            chart.deleteLater()

    def test_group_filter_and_interactions_are_preserved(self):
        chart = self._build_chart()

        try:
            chart.control_panel.groupChanged.emit({"voltage"})
            chart.update_chart()
            self.assertEqual(set(chart.chart_widget._curves), {"vin"})

            old_window = chart.chart_model.time_window_sec
            chart.chart_widget._zoomTime(120)
            self.assertLess(chart.chart_model.time_window_sec, old_window)

            chart.chart_widget._beginDrag(100)
            chart.chart_widget._dragTo(180)
            chart.chart_widget._endDrag()
            self.assertLess(chart.chart_model.time_offset_sec, 0.0)

            chart.chart_widget._resetTimeOffset()
            self.assertEqual(chart.chart_model.time_offset_sec, 0.0)
        finally:
            chart.deleteLater()


if __name__ == "__main__":
    unittest.main()
