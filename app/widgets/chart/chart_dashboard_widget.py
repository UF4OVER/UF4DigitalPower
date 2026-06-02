# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: chart_dashboard_widget.py
#  @FileType: 图表组件文件，负责实时曲线、图表模型和数据展示
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

from PyQt5.QtWidgets import QWidget, QGridLayout

from app.core.data_hub import DataHub
from app.widgets.chart.chart_model import ChartModel
from app.widgets.chart.realtime_chart_widget import RealtimeChartWidget


class ChartDashboardWidget(QWidget):
    """
    多图表仪表盘。

    一个 DataHub 对应多个 ChartModel。
    每个 ChartModel 对应一个 RealtimeChartWidget。
    """

    def __init__(self, data_hub: DataHub, parent=None):
        super().__init__(parent)

        self.data_hub = data_hub
        self.charts: list[RealtimeChartWidget] = []

        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(8)

        self._init_default_charts()

    def _init_default_charts(self) -> None:
        self.add_chart(
            row=0,
            column=0,
            title="电压曲线",
            channels=["vin", "vout"],
            time_window=10.0,
        )

        self.add_chart(
            row=0,
            column=1,
            title="电流曲线",
            channels=["iin", "iout"],
            time_window=10.0,
        )

        self.add_chart(
            row=1,
            column=0,
            title="功率曲线",
            channels=["pin", "pout"],
            time_window=10.0,
        )

        self.add_chart(
            row=1,
            column=1,
            title="温度 / 效率",
            channels=["temp", "efficiency"],
            time_window=30.0,
        )

    def add_chart(
        self,
        row: int,
        column: int,
        title: str,
        channels: list[str],
        time_window: float = 10.0,
        row_span: int = 1,
        column_span: int = 1,
    ) -> RealtimeChartWidget:
        model = ChartModel(self.data_hub)
        model.set_time_window(time_window)
        model.set_selected_channels(channels)

        chart = RealtimeChartWidget(model, self)
        chart.set_title(title)

        self.layout.addWidget(chart, row, column, row_span, column_span)
        self.charts.append(chart)

        return chart