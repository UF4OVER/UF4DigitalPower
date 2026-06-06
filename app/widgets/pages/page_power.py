# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: page_power.py
#  @FileType: 电源页面文件，负责电源监控、参数设置和日志展示
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

import html
import math
import time
from dataclasses import dataclass

from PyQt5.QtCore import QMetaObject, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel, CardWidget, CaptionLabel, ComboBox, DoubleSpinBox,
    FluentIcon as FIF, PillPushButton, PrimaryPushButton, PushButton,
    ScrollArea, SpinBox,
    StrongBodyLabel, SubtitleLabel, SwitchButton, TextEdit, TitleLabel,
    isDarkTheme, setFont,
)

from app.core.channel import ChannelConfig
from app.core.data_hub import DataHub
from app.core.utility import showMessage
from app.controllers import PowerPageController
from app.manager import StyleSheet

from app.session import (
    DEFAULT_STATUS_VALUES, DebugSnapshot, F4CPPowerClient, PowerStatus, SerialConfig,
    SerialSession, listSerialPorts, pretty_faults,
    build_status,
)
from app.widgets.chart.chart_model import ChartModel
from app.widgets.chart.realtime_chart_widget import RealtimeChartWidget
from config import CTX


DEFAULT_OVP_SET_VALUE_MV = 44000
POWER_POLL_INTERVAL_MS = 500
POWER_SERIAL_BAUD_RATE = 921600
WRITE_POLL_RESTART_DELAY_MS = 600
MOCK_SAMPLE_INTERVAL_MS = 20

POWER_CHART_CHANNELS = (
    ChannelConfig("vin", "输入电压", "V", precision=3, group="voltage", color=(47, 128, 237), line_width=2.0),
    ChannelConfig("vout", "输出电压", "V", precision=3, group="voltage", color=(39, 174, 96), line_width=2.0),
    ChannelConfig("iin", "输入电流", "A", precision=3, group="current", color=(242, 153, 74), line_width=2.0),
    ChannelConfig("iout", "输出电流", "A", precision=3, group="current", color=(235, 87, 87), line_width=2.0),
    ChannelConfig("pin", "输入功率", "W", precision=3, group="power", color=(86, 204, 242), line_width=2.0),
    ChannelConfig("pout", "输出功率", "W", precision=3, group="power", color=(155, 81, 224), line_width=2.0),
    ChannelConfig("efficiency", "效率", "%", precision=2, group="efficiency", color=(255, 193, 7), line_width=2.0),
    ChannelConfig("core_temp", "核心温度", "°C", precision=2, group="thermal", color=(255, 112, 67), line_width=2.0),
    ChannelConfig("board_temp", "板载温度", "°C", precision=2, group="thermal", color=(255, 152, 0), line_width=2.0),
)


@dataclass(frozen=True)
class _MetricValue:
    title: str
    value: str
    unit: str
    extra: str = ""


class MetricCard(CardWidget):
    def __init__(self, title: str, accent: str, parent=None):
        super().__init__(parent)
        self._accent = accent
        self.setObjectName("PowerMetricCard")
        self.titleLabel = CaptionLabel(title, self)
        self.valueLabel = TitleLabel("--", self)
        self.unitLabel = StrongBodyLabel("", self)
        self.extraLabel = CaptionLabel("等待数据", self)
        self.extraLabel.setWordWrap(True)
        self.valueLabel.setWordWrap(False)
        self.unitLabel.setWordWrap(False)
        self.unitLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self.unitLabel.setMinimumWidth(44)
        setFont(self.valueLabel, 28, QFont.DemiBold)
        setFont(self.unitLabel, 18, QFont.DemiBold)

        value_row = QHBoxLayout()
        value_row.setContentsMargins(0, 0, 0, 0)
        value_row.setSpacing(8)
        value_row.addWidget(self.valueLabel, 1)
        value_row.addWidget(self.unitLabel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        layout.addWidget(self.titleLabel)
        layout.addLayout(value_row)
        layout.addWidget(self.extraLabel)
        self.setMinimumHeight(138)
        self.refreshTheme()

    def setMetric(self, metric: _MetricValue) -> None:
        self.titleLabel.setText(metric.title)
        self.valueLabel.setText(metric.value)
        self._setAccentText(self.unitLabel, metric.unit)
        self._setAccentText(self.extraLabel, metric.extra)

    def _setAccentText(self, label, text: str) -> None:
        if not text:
            label.setText("")
            return
        safe_text = html.escape(text).replace("\n", "<br/>")
        label.setText(f'<span style="color: {self._accent};">{safe_text}</span>')

    def refreshTheme(self) -> None:
        dark = isDarkTheme()
        text = "#F5F7FA" if dark else "#111827"
        self.titleLabel.setStyleSheet(f"color: {self._accent};")
        self.valueLabel.setStyleSheet(f"color: {text};")


class StatusChip(PillPushButton):
    def __init__(self, text: str = "离线", parent=None):
        super().__init__(text, parent)
        self.setCheckable(False)
        self.setFixedHeight(30)
        self.setMinimumWidth(86)
        self.setProperty("onlineState", "offline")
        self.refreshTheme()

    def setOnline(self, online: bool) -> None:
        self.setText("在线" if online else "离线")
        self.setProperty("onlineState", "online" if online else "offline")
        self.refreshTheme()

    def refreshTheme(self) -> None:
        online = self.property("onlineState") == "online"
        if online:
            background = "rgba(34, 197, 94, 0.22)"
            foreground = "#22C55E" if isDarkTheme() else "#166534"
            border = "rgba(34, 197, 94, 0.36)"
        else:
            background = "rgba(239, 68, 68, 0.20)"
            foreground = "#F87171" if isDarkTheme() else "#B91C1C"
            border = "rgba(239, 68, 68, 0.34)"
        self.setStyleSheet(f"""
            PillPushButton {{
                background: {background}; color: {foreground};
                border: 1px solid {border}; border-radius: 14px;
                padding: 0 12px; font-weight: 700;
            }}
        """)


class StatusValueWidget(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("PowerStatusValue")
        self.titleLabel = CaptionLabel(title, self)
        self.valueLabel = StrongBodyLabel("--", self)
        self.valueLabel.setWordWrap(True)
        self.valueLabel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        setFont(self.titleLabel, 12)
        setFont(self.valueLabel, 20, QFont.DemiBold)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.valueLabel, 1)
        self.setMinimumHeight(96)
        self.refreshTheme()

    def setValue(self, value: str) -> None:
        self.valueLabel.setText(value)

    def refreshTheme(self) -> None:
        dark = isDarkTheme()
        title = "#9AA4B2" if dark else "#64748B"
        value = "#F5F7FA" if dark else "#111827"
        border = "rgba(255, 255, 255, 0.10)" if dark else "rgba(15, 23, 42, 0.08)"
        background = "rgba(255, 255, 255, 0.045)" if dark else "rgba(248, 250, 252, 0.82)"
        self.titleLabel.setStyleSheet(f"color: {title};")
        self.valueLabel.setStyleSheet(f"color: {value};")
        self.setStyleSheet(f"""
            QWidget#PowerStatusValue {{
                background: {background};
                border: 1px solid {border};
                border-radius: 8px;
            }}
        """)


class ParameterEditor(CardWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("PowerParameterEditor")
        self.titleLabel = SubtitleLabel(title, self)
        self._selectorBlocks: list[tuple[QWidget, CaptionLabel]] = []
        self.outputVoltage = self._createDoubleSelector("V", 0.0, 80.0, 0.1)
        self.outputCurrent = self._createDoubleSelector("A", 0.0, 60.0, 0.1)
        self.ovp = self._createDoubleSelector("V", 0.0, 100.0, 0.1)
        self.ocp = self._createDoubleSelector("A", 0.0, 80.0, 0.1)
        self.otp = self._createDoubleSelector("°C", 0.0, 150.0, 1.0)
        self.fan = self._createFanSelector()

        self._editors = (
            self.outputVoltage,
            self.outputCurrent,
            self.ovp,
            self.ocp,
            self.otp,
            self.fan,
        )

        self.outputSwitch = SwitchButton(self)
        self.outputSwitch.setOnText("输出开启")
        self.outputSwitch.setOffText("输出关闭")
        self.applyOutputButton = PrimaryPushButton(FIF.ACCEPT, "应用输出", self)
        self.applyProtectButton = PushButton(FIF.SAVE, "应用保护", self)
        self.outputSwitch.setFixedHeight(38)
        self.applyOutputButton.setFixedHeight(38)
        self.applyProtectButton.setFixedHeight(38)
        self.applyOutputButton.setMinimumWidth(110)
        self.applyProtectButton.setMinimumWidth(110)
        self._sectionLabels = [
            BodyLabel("输出设定", self),
            BodyLabel("保护阈值", self),
        ]

        outputGrid = QGridLayout()
        outputGrid.setContentsMargins(0, 0, 0, 0)
        outputGrid.setHorizontalSpacing(10)
        outputGrid.setVerticalSpacing(8)
        outputGrid.addWidget(self._selectorBlock("输出电压", self.outputVoltage), 0, 0)
        outputGrid.addWidget(self._selectorBlock("输出电流", self.outputCurrent), 0, 1)
        outputGrid.setColumnStretch(0, 1)
        outputGrid.setColumnStretch(1, 1)

        protectGrid = QGridLayout()
        protectGrid.setContentsMargins(0, 0, 0, 0)
        protectGrid.setHorizontalSpacing(10)
        protectGrid.setVerticalSpacing(8)
        protectGrid.addWidget(self._selectorBlock("过压保护", self.ovp), 0, 0)
        protectGrid.addWidget(self._selectorBlock("过流保护", self.ocp), 0, 1)
        protectGrid.addWidget(self._selectorBlock("过温保护", self.otp), 1, 0)
        protectGrid.addWidget(self._selectorBlock("风扇设定", self.fan), 1, 1)
        protectGrid.setColumnStretch(0, 1)
        protectGrid.setColumnStretch(1, 1)

        control = QHBoxLayout()
        control.setContentsMargins(0, 6, 0, 0)
        control.setSpacing(10)
        control.addWidget(self.outputSwitch)
        control.addStretch(1)
        control.addWidget(self.applyOutputButton)
        control.addWidget(self.applyProtectButton)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self._sectionLabels[0])
        layout.addLayout(outputGrid)
        layout.addWidget(self._sectionLabels[1])
        layout.addLayout(protectGrid)
        layout.addLayout(control)
        self.refreshTheme()

    def _createDoubleSelector(self, suffix: str, minimum: float, maximum: float, step: float) -> DoubleSpinBox:
        selector = DoubleSpinBox(self)
        selector.setRange(minimum, maximum)
        selector.setDecimals(3)
        selector.setSingleStep(step)
        selector.setSuffix(f" {suffix}")
        selector.setFixedHeight(40)
        selector.setMinimumWidth(132)
        selector.setAlignment(Qt.AlignmentFlag.AlignRight)
        selector.setAccelerated(True)
        return selector

    def _createFanSelector(self) -> SpinBox:
        selector = SpinBox(self)
        selector.setRange(0, 1000)
        selector.setSingleStep(10)
        selector.setSuffix(" /1000")
        selector.setFixedHeight(40)
        selector.setMinimumWidth(132)
        selector.setAlignment(Qt.AlignmentFlag.AlignRight)
        selector.setAccelerated(True)
        return selector

    def _selectorBlock(self, title: str, selector) -> QWidget:
        block = QWidget(self)
        block.setObjectName("PowerParameterBlock")
        label = CaptionLabel(title, block)
        setFont(label, 12)
        layout = QVBoxLayout(block)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        layout.addWidget(label)
        layout.addWidget(selector)
        block.setMinimumHeight(92)
        self._selectorBlocks.append((block, label))
        return block

    def refreshTheme(self) -> None:
        dark = isDarkTheme()
        title = "#F5F7FA" if dark else "#111827"
        caption = "#9AA4B2" if dark else "#64748B"
        border = "rgba(255, 255, 255, 0.10)" if dark else "rgba(15, 23, 42, 0.08)"
        background = "rgba(255, 255, 255, 0.045)" if dark else "rgba(248, 250, 252, 0.82)"
        self.titleLabel.setStyleSheet(f"color: {title};")
        for sectionLabel in self._sectionLabels:
            sectionLabel.setStyleSheet(f"color: {title}; font-weight: 700;")
        for block, label in self._selectorBlocks:
            label.setStyleSheet(f"color: {caption};")
            block.setStyleSheet(f"""
                QWidget#PowerParameterBlock {{
                    background: {background};
                    border: 1px solid {border};
                    border-radius: 8px;
                }}
            """)

    def setFromStatus(self, status: PowerStatus) -> None:
        values = {
            self.outputVoltage: status.set_voltage_limit_mv / 1000.0,
            self.outputCurrent: status.set_current_limit_ma / 1000.0,
            self.ovp: status.ovp_set_value_v,
            self.ocp: status.ocp_set_value_a,
            self.otp: status.otp_set_value_c,
            self.fan: status.fan_set_value,
        }
        for editor, value in values.items():
            if not self._selectorHasFocus(editor):
                editor.setValue(value)

    @staticmethod
    def _selectorHasFocus(editor) -> bool:
        try:
            return editor.hasFocus() or editor.lineEdit().hasFocus()
        except Exception:
            return editor.hasFocus()

    def setWriteEnabled(self, enabled: bool) -> None:
        for editor in self._editors:
            editor.setEnabled(enabled)
        self.outputSwitch.setEnabled(enabled)
        self.applyOutputButton.setEnabled(enabled)
        self.applyProtectButton.setEnabled(enabled)


class TelemetryChartCard(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TelemetryChartCard")
        self.dataHub = DataHub(default_max_points=6000)
        self.dataHub.register_channels(POWER_CHART_CHANNELS, max_points=6000)
        self.chartModel = ChartModel(self.dataHub)
        self.chartModel.set_time_window(30.0)
        self.chartModel.set_auto_y_range(True)
        self.titleLabel = SubtitleLabel("实时曲线", self)
        self.tipLabel = CaptionLabel("左键拖动平移时间轴，滚轮缩放时基，双击回到实时位置。", self)
        self.chart = RealtimeChartWidget(self.chartModel, self)
        self.chart.set_title("F4CP Power Telemetry")
        self.chart.setMinimumHeight(440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.tipLabel)
        layout.addWidget(self.chart, 1)
        self.refreshTheme()

    def refreshTheme(self) -> None:
        dark = isDarkTheme()
        self.titleLabel.setStyleSheet(f"color: {'#F5F7FA' if dark else '#111827'};")
        self.tipLabel.setStyleSheet(f"color: {'#9AA4B2' if dark else '#64748B'};")
        self.chart.refreshTheme()

    def pushStatus(self, status: PowerStatus) -> None:
        self.dataHub.push_many({
            "vin": status.vin_v, "vout": status.vout_v,
            "iin": status.iin_a, "iout": status.iout_a,
            "pin": status.pin_w, "pout": status.pout_w,
            "efficiency": status.efficiency,
            "core_temp": status.core_temp_c,
            "board_temp": status.board_temp_c,
        }, t=time.time())
        self.chart.mark_data_dirty()

    def pushMock(self) -> None:
        t = time.time()
        phase = t * 0.8
        vin = 16.8 + math.sin(phase) * 0.08
        vout = 12.0 + math.sin(phase * 1.2) * 0.18
        iin = 2.4 + math.sin(phase * 0.7) * 0.25
        iout = 3.0 + math.sin(phase * 0.9) * 0.35
        pin = vin * iin
        pout = vout * iout
        self.dataHub.push_many({
            "vin": vin, "vout": vout, "iin": iin, "iout": iout,
            "pin": pin, "pout": pout,
            "efficiency": 0.0 if pin <= 0 else pout / pin * 100.0,
            "core_temp": 42.0 + math.sin(phase * 0.25) * 2.0,
            "board_temp": 38.0 + math.sin(phase * 0.32) * 1.4,
        }, t=t)
        self.chart.mark_data_dirty()


class PowerPage(ScrollArea):
    attachSessionRequested = pyqtSignal(object)
    detachSessionRequested = pyqtSignal()
    readStatusRequested = pyqtSignal()
    debugSnapshotRequested = pyqtSignal()
    outputLimitsRequested = pyqtSignal(int, int, bool)
    protectionValuesRequested = pyqtSignal(int, int, int, int)
    powerStateRequested = pyqtSignal(bool)
    startPollingRequested = pyqtSignal(int)
    stopPollingRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("PowerPage")

        self._shutdownDone = False
        self._manualSession = None
        self._lastStatus: PowerStatus | None = None
        self._stagedOutputEnabled: bool | None = None
        self._writeInFlight = False
        self._writePollingRestartPending = False
        self._lastVerboseLogTs = 0.0
        self._appendLogBusy = False

        self._pageLogPath = CTX.dirs.LogDir / f"power_page_{time.strftime('%Y-%m-%d')}.log"

        self._client = F4CPPowerClient()
        self._clientThread = QThread(self)
        self._client.moveToThread(self._clientThread)
        self._clientThread.finished.connect(self._client.deleteLater)
        self._clientThread.start()

        self._writePollRestartTimer = QTimer(self)
        self._writePollRestartTimer.setSingleShot(True)
        self._writePollRestartTimer.timeout.connect(self._restartAutoPollingAfterWrite)
        self._scrollIdleTimer = QTimer(self)
        self._scrollIdleTimer.setSingleShot(True)
        self._scrollIdleTimer.setInterval(180)
        self._scrollIdleTimer.timeout.connect(self._resumeChartAfterScroll)
        self._mockTimer = QTimer(self)
        self._mockTimer.setInterval(MOCK_SAMPLE_INTERVAL_MS)
        self._mockTimer.timeout.connect(self.pushMockPowerSample)

        self.scrollWidget = QWidget(self)
        self.scrollWidget.setObjectName("powerScrollWidget")
        self.rootLayout = QVBoxLayout(self.scrollWidget)
        self.rootLayout.setContentsMargins(24, 24, 24, 24)
        self.rootLayout.setSpacing(12)

        self._initHeader()
        self._initMetricCards()
        self._initTelemetryChart()
        self._initStatusAndParameters()
        self._initLogCard()
        self._initEmptyStatusView()

        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 0, 0, 0)
        self.verticalScrollBar().valueChanged.connect(self._onScrollValueChanged)

        self._controller = PowerPageController(self)
        self._bindSignals()
        self._applyDisconnectedState()
        StyleSheet.POWER_PAGE.apply(self)
        self.refreshSerialPorts()

    def _initHeader(self) -> None:
        self.headerCard = CardWidget(self.scrollWidget)
        self.headerCard.setObjectName("powerHeaderCard")
        layout = QHBoxLayout(self.headerCard)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        titleBox = QVBoxLayout()
        titleBox.setContentsMargins(0, 0, 0, 0)
        titleBox.setSpacing(2)
        self.titleLabel = TitleLabel("电源面板", self.headerCard)
        self.subtitleLabel = CaptionLabel("UF4 Digital Power 运行监控 / 参数设置 / 实时曲线", self.headerCard)
        titleBox.addWidget(self.titleLabel)
        titleBox.addWidget(self.subtitleLabel)

        self.portCombo = ComboBox(self.headerCard)
        self.portCombo.setMinimumWidth(140)
        self.refreshTargetButton = PushButton(FIF.SYNC, "刷新串口", self.headerCard)
        self.connectButton = PrimaryPushButton(FIF.LINK, "连接", self.headerCard)
        self.stateBadge = StatusChip("离线", self.headerCard)
        self.autoPollSwitch = SwitchButton(self.headerCard)
        self.autoPollSwitch.setOnText("自动轮询")
        self.autoPollSwitch.setOffText("自动轮询")
        self.autoPollSwitch.setChecked(True)
        self.refreshButton = PushButton(FIF.SYNC, "立即刷新", self.headerCard)
        self.debugButton = PushButton(FIF.SEARCH, "调试快照", self.headerCard)
        self.mockButton = PushButton(FIF.PLAY, "假数据", self.headerCard)
        self.mockButton.setCheckable(True)

        layout.addLayout(titleBox, 1)
        layout.addWidget(BodyLabel("串口", self.headerCard))
        layout.addWidget(self.portCombo)
        layout.addWidget(self.refreshTargetButton)
        layout.addWidget(self.connectButton)
        layout.addWidget(self.stateBadge)
        layout.addSpacing(8)
        layout.addWidget(self.autoPollSwitch)
        layout.addWidget(self.refreshButton)
        layout.addWidget(self.debugButton)
        layout.addWidget(self.mockButton)
        self.rootLayout.addWidget(self.headerCard)

    def _initMetricCards(self) -> None:
        self.metricsGrid = QGridLayout()
        self.metricsGrid.setHorizontalSpacing(12)
        self.metricsGrid.setVerticalSpacing(6)
        self.metricCards = {
            "vin": MetricCard("输入电压", "#2F80ED", self.scrollWidget),
            "iin": MetricCard("输入电流", "#F2994A", self.scrollWidget),
            "pin": MetricCard("输入功率", "#56CCF2", self.scrollWidget),
            "vout": MetricCard("输出电压", "#27AE60", self.scrollWidget),
            "iout": MetricCard("输出电流", "#EB5757", self.scrollWidget),
            "pout": MetricCard("输出功率", "#9B51E0", self.scrollWidget),
        }
        for index, key in enumerate(("vin", "iin", "pin", "vout", "iout", "pout")):
            self.metricsGrid.addWidget(self.metricCards[key], index // 3, index % 3)
        self.rootLayout.addLayout(self.metricsGrid)

    def _initTelemetryChart(self) -> None:
        self.chartCard = TelemetryChartCard(self.scrollWidget)
        self.rootLayout.addWidget(self.chartCard)

    def _initStatusAndParameters(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(6)
        self.statusCard = CardWidget(self.scrollWidget)
        self.statusCard.setObjectName("PowerStatusCard")
        statusLayout = QVBoxLayout(self.statusCard)
        statusLayout.setContentsMargins(12, 12, 12, 12)
        statusLayout.setSpacing(6)
        self.statusTitle = SubtitleLabel("状态", self.statusCard)
        self.statusGrid = QGridLayout()
        self.statusGrid.setContentsMargins(0, 0, 0, 0)
        self.statusGrid.setHorizontalSpacing(10)
        self.statusGrid.setVerticalSpacing(10)
        self.statusFields = {
            "output": StatusValueWidget("输出", self.statusCard),
            "topology": StatusValueWidget("拓扑", self.statusCard),
            "mode": StatusValueWidget("控制模式", self.statusCard),
            "state": StatusValueWidget("状态机", self.statusCard),
            "fault": StatusValueWidget("故障", self.statusCard),
            "core_temp": StatusValueWidget("核心温度", self.statusCard),
            "board_temp": StatusValueWidget("板载温度", self.statusCard),
            "pwm": StatusValueWidget("PWM A/D", self.statusCard),
            "fan": StatusValueWidget("风扇", self.statusCard),
        }
        for index, key in enumerate((
            "output", "topology", "mode",
            "state", "fault", "core_temp",
            "board_temp", "pwm", "fan",
        )):
            self.statusGrid.addWidget(self.statusFields[key], index // 3, index % 3)
        for column in range(3):
            self.statusGrid.setColumnStretch(column, 1)
        statusLayout.addWidget(self.statusTitle)
        statusLayout.addLayout(self.statusGrid, 1)
        self.parameterEditor = ParameterEditor("输出设定与保护阈值", self.scrollWidget)
        row.addWidget(self.statusCard, 3)
        row.addWidget(self.parameterEditor, 2)
        self.rootLayout.addLayout(row)

    def _initLogCard(self) -> None:
        self.logCard = CardWidget(self.scrollWidget)
        self.logCard.setObjectName("powerLogCard")
        layout = QVBoxLayout(self.logCard)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        top = QHBoxLayout()
        self.logCardTitle = SubtitleLabel("协议 / 状态日志", self.logCard)
        self.logLevelCombo = ComboBox(self.logCard)
        self.logLevelCombo.addItem("普通", userData="normal")
        self.logLevelCombo.addItem("详细", userData="verbose")
        self.clearLogButton = PushButton(FIF.BROOM, "清空", self.logCard)
        top.addWidget(self.logCardTitle)
        top.addStretch(1)
        top.addWidget(self.logLevelCombo)
        top.addWidget(self.clearLogButton)
        self.logEdit = TextEdit(self.logCard)
        self.logEdit.setMinimumHeight(170)
        self.logEdit.setReadOnly(True)
        self.logEdit.document().setMaximumBlockCount(400)
        layout.addLayout(top)
        layout.addWidget(self.logEdit)
        self.rootLayout.addWidget(self.logCard)

    def _onScrollValueChanged(self, _value: int) -> None:
        self.chartCard.chart.set_live_updates_suspended(True)
        self._scrollIdleTimer.start()

    def _resumeChartAfterScroll(self) -> None:
        self.chartCard.chart.set_live_updates_suspended(False)

    def _bindSignals(self) -> None:
        # 复杂信号注册下沉到 Controller，页面保留 UI 创建和状态渲染。
        self._controller.bind()

    def _onThemeChanged(self, *_):
        StyleSheet.POWER_PAGE.apply(self)
        self._refreshThemeWidgets()
        QTimer.singleShot(0, self._refreshThemeWidgets)

    def _refreshThemeWidgets(self) -> None:
        for card in self.metricCards.values():
            card.refreshTheme()
        for field in self.statusFields.values():
            field.refreshTheme()
        self.parameterEditor.refreshTheme()
        self.stateBadge.refreshTheme()
        self.chartCard.refreshTheme()

    def refreshSerialPorts(self) -> None:
        ports = [p.strip() for p in (listSerialPorts() or []) if p and p.strip()]
        current = self.portCombo.currentText().strip()
        self.portCombo.blockSignals(True)
        self.portCombo.clear()
        if ports:
            self.portCombo.addItems(ports)
            if current in ports:
                self.portCombo.setCurrentText(current)
        self.portCombo.blockSignals(False)
        self._writePageLogFile(f"串口列表: {ports}")

    def _initEmptyStatusView(self) -> None:
        self._renderStatusView(
            build_status(dict(DEFAULT_STATUS_VALUES)),
            update_chart=False,
            log_changes=False,
        )

    def toggleConnection(self) -> None:
        """连接按钮入口：根据当前状态在打开串口和断开会话之间切换。"""
        if self._client.is_connected:
            self._disconnectManualSession()
        else:
            self._connectSerialTarget()

    def _connectSerialTarget(self) -> None:
        """按页面选择创建串口会话，打开成功后交给电源协议客户端接管。"""
        port = self.portCombo.currentText().strip()
        if not port:
            self._appendLog("错误: 未选择串口。请先刷新并选择串口。")
            return
        session = SerialSession(SerialConfig(port=port, baudrate=POWER_SERIAL_BAUD_RATE))
        try:
            session.open()
        except Exception as exc:
            self.parameterEditor.setWriteEnabled(False)
            self._appendLog(f"错误: {exc}")
            return
        self._manualSession = session
        self.onDeviceConnected(session)

    def onDeviceConnected(self, session) -> None:
        """串口建立后同步 UI 状态，并按开关决定读一次还是持续轮询。"""
        self.attachSessionRequested.emit(session)
        self.stateBadge.setOnline(True)
        self.connectButton.setText("断开")
        self.parameterEditor.setWriteEnabled(True)
        self._appendLog(f"已连接: {getattr(getattr(session, 'cfg', None), 'port', '未知')}")
        showMessage(self, "设备已连接", "电源设备会话已连接。", level="success")
        if self.autoPollSwitch.isChecked():
            self.startPollingRequested.emit(POWER_POLL_INTERVAL_MS)
        else:
            self.readStatusRequested.emit()

    def _disconnectManualSession(self) -> None:
        """主动断开页面自己创建的串口会话，并让协议客户端清空状态。"""
        self.stopPollingRequested.emit()
        self.detachSessionRequested.emit()
        try:
            if self._manualSession:
                self._manualSession.close()
        except Exception as exc:
            self._writePageLogFile(f"PowerPage manual session close failed: {exc}")
        self._manualSession = None
        self._applyDisconnectedState()
        self._appendLog("设备已断开")

    def _closeManualSessionSilently(self) -> None:
        session = self._manualSession
        self._manualSession = None
        if session is None:
            return
        try:
            session.set_event_receiver(None)
            session.close()
        except Exception as exc:
            self._writePageLogFile(f"PowerPage serial cleanup failed: {exc}")

    def _onConnectionChanged(self, connected: bool) -> None:
        self.stateBadge.setOnline(connected)
        self.connectButton.setText("断开" if connected else "连接")
        self.parameterEditor.setWriteEnabled(connected)
        if not connected:
            self._closeManualSessionSilently()
            self._applyDisconnectedState()

    def _updateStatusView(self, status: PowerStatus) -> None:
        self._renderStatusView(status, update_chart=True, log_changes=True)

    def _renderStatusView(
        self,
        status: PowerStatus,
        *,
        update_chart: bool,
        log_changes: bool,
    ) -> None:
        """把一帧 PowerStatus 映射到指标卡、状态栏、参数编辑器和曲线图。"""
        previous = self._lastStatus
        if log_changes:
            self._lastStatus = status
        if update_chart:
            self.chartCard.pushStatus(status)
        self.metricCards["vin"].setMetric(_MetricValue("输入电压", f"{status.vin_v:.3f}", "V", f"输入功率 {status.pin_w:.2f} W"))
        self.metricCards["iin"].setMetric(_MetricValue("输入电流", f"{status.iin_a:.3f}", "A", f"模式 {status.mode_name}"))
        self.metricCards["pin"].setMetric(_MetricValue("输入功率", f"{status.pin_w:.3f}", "W", f"故障 0x{status.fault_state:04X}"))
        self.metricCards["vout"].setMetric(_MetricValue("输出电压", f"{status.vout_v:.3f}", "V", f"设定 {status.set_voltage_limit_mv / 1000.0:.3f} V"))
        self.metricCards["iout"].setMetric(_MetricValue("输出电流", f"{status.iout_a:.3f}", "A", f"设定 {status.set_current_limit_ma / 1000.0:.3f} A"))
        self.metricCards["pout"].setMetric(_MetricValue("输出功率", f"{status.pout_w:.3f}", "W", f"效率 {status.efficiency:.2f} %"))
        self.parameterEditor.setFromStatus(status)
        switch_value = status.power_enabled
        if self._stagedOutputEnabled is not None:
            if self._stagedOutputEnabled == status.power_enabled:
                self._stagedOutputEnabled = None
            else:
                switch_value = self._stagedOutputEnabled
        self.parameterEditor.outputSwitch.blockSignals(True)
        self.parameterEditor.outputSwitch.setChecked(switch_value)
        self.parameterEditor.outputSwitch.blockSignals(False)
        faults = pretty_faults(status.fault_state)
        if not faults or faults == "None":
            faults = "无"
        self.statusFields["output"].setValue("开启" if status.power_enabled else "关闭")
        self.statusFields["topology"].setValue(status.topology_name)
        self.statusFields["mode"].setValue(status.mode_name)
        self.statusFields["state"].setValue(status.state_flag_name)
        self.statusFields["fault"].setValue(faults)
        self.statusFields["core_temp"].setValue(f"{status.core_temp_c:.2f} °C")
        self.statusFields["board_temp"].setValue(f"{status.board_temp_c:.2f} °C")
        self.statusFields["pwm"].setValue(f"{status.pwm_a_compare} / {status.pwm_d_compare}")
        self.statusFields["fan"].setValue(f"{status.fan_speed} / 设定 {status.fan_set_value}")
        if log_changes and (
            previous is None
            or previous.power_state != status.power_state
            or previous.state_machine_flag_bits != status.state_machine_flag_bits
            or previous.fault_state != status.fault_state
        ):
            self._appendLog(f"状态 输出={'开启' if status.power_enabled else '关闭'} 状态机={status.state_flag_name} 拓扑={status.topology_name} 故障={faults} VOUT={status.vout_v:.3f}V IOUT={status.iout_a:.3f}A")
        if log_changes and self.logLevelCombo.currentData() == "verbose" and time.monotonic() - self._lastVerboseLogTs >= 2.0:
            self._lastVerboseLogTs = time.monotonic()
            self._appendLog(self._client.pretty_print_status(status))

    def _readStatusOnce(self) -> None:
        if not self._client.is_connected:
            self._appendLog("错误: 串口会话未连接")
            return
        self.readStatusRequested.emit()

    def _runDebugSnapshot(self) -> None:
        if not self._client.is_connected:
            self._appendLog("错误: 串口会话未连接")
            return
        self.debugSnapshotRequested.emit()

    def _onAutoPollChanged(self, checked: bool) -> None:
        """自动轮询开关变化时，直接通知协议客户端启动或停止刷新。"""
        if checked:
            self.startPollingRequested.emit(POWER_POLL_INTERVAL_MS)
        else:
            self.stopPollingRequested.emit()
            self._appendLog("主机轮询已关闭")

    def _onOutputSwitchChanged(self, checked: bool) -> None:
        """输出开关先暂存用户意图，再交给协议层写入，避免界面被旧状态立刻覆盖。"""
        self._stagedOutputEnabled = checked
        if not self._client.is_connected:
            return
        if self._writeInFlight:
            self._appendLog("写入进行中，请等待当前操作完成")
            return
        self._setWriteControlsEnabled(False)
        self._writePollingRestartPending = True
        self._appendLog(f"输出开关正在设置为{'开启' if checked else '关闭'}")
        self.powerStateRequested.emit(checked)

    def _applyOutputLimits(self) -> None:
        """提交输出限制值；界面用 V/A，协议层用 mV/mA。"""
        if not self._client.is_connected:
            self._appendLog("错误: 串口会话未连接")
            return
        if self._writeInFlight:
            self._appendLog("写入进行中，请等待当前操作完成")
            return
        voltage_mv = int(round(self.parameterEditor.outputVoltage.value() * 1000))
        current_ma = int(round(self.parameterEditor.outputCurrent.value() * 1000))
        enabled = self._stagedOutputEnabled if self._stagedOutputEnabled is not None else self.parameterEditor.outputSwitch.isChecked()
        self._setWriteControlsEnabled(False)
        self._writePollingRestartPending = True
        self.outputLimitsRequested.emit(voltage_mv, current_ma, enabled)

    def _applyProtectionValues(self) -> None:
        """提交保护参数；温度在界面是摄氏度，协议层按毫摄氏度传输。"""
        if not self._client.is_connected:
            self._appendLog("错误: 串口会话未连接")
            return
        if self._writeInFlight:
            self._appendLog("写入进行中，请等待当前操作完成")
            return
        ovp_mv = int(round(self.parameterEditor.ovp.value() * 1000))
        ocp_ma = int(round(self.parameterEditor.ocp.value() * 1000))
        otp_mc = int(round(self.parameterEditor.otp.value() * 1000))
        fan_value = int(self.parameterEditor.fan.value())
        self._setWriteControlsEnabled(False)
        self._writePollingRestartPending = True
        self.protectionValuesRequested.emit(ovp_mv, ocp_ma, otp_mc, fan_value)

    def _setWriteControlsEnabled(self, enabled: bool) -> None:
        self._writeInFlight = not enabled
        self.parameterEditor.setWriteEnabled(enabled)

    def _onOutputLimitsWritten(self) -> None:
        self._setWriteControlsEnabled(True)
        showMessage(self, "输出参数已更新", "电压、电流和输出状态已写入。", level="success")
        self._scheduleAutoPollingRestartAfterWrite()

    def _onProtectionValuesWritten(self) -> None:
        self._setWriteControlsEnabled(True)
        showMessage(self, "保护参数已更新", "OVP/OCP/OTP/风扇参数已写入。", level="success")
        self._scheduleAutoPollingRestartAfterWrite()

    def _onPowerStateWritten(self, enabled: bool) -> None:
        self._setWriteControlsEnabled(True)
        if self._stagedOutputEnabled == enabled:
            self._stagedOutputEnabled = None
        self._appendLog(f"输出已设置为{'开启' if enabled else '关闭'}")
        self._scheduleAutoPollingRestartAfterWrite()

    def _onClientError(self, message: str) -> None:
        """协议层错误统一落到这里，恢复按钮状态并给用户一个明确提示。"""
        self._appendLog(f"错误: {message}")
        self._setWriteControlsEnabled(True)
        showMessage(self, "通信错误", message, level="error")
        if self._writePollingRestartPending:
            self._scheduleAutoPollingRestartAfterWrite()

    def _disconnectAfterWriteFailures(self) -> None:
        if not self._client.is_connected and self._manualSession is None:
            return
        self._appendLog("连续写入失败 3 次，已断开串口")
        showMessage(self, "串口已断开", "连续写入失败 3 次，已关闭当前串口连接。", level="error")
        self._disconnectManualSession()

    def _disconnectAfterCommunicationFailures(self, message: str) -> None:
        if not self._client.is_connected and self._manualSession is None:
            return
        self._appendLog(f"连续通信失败 3 次，已断开串口。最后错误: {message}")
        showMessage(self, "串口已断开", "连续 3 次无回复或错误，已关闭当前串口连接。", level="error")
        self._disconnectManualSession()

    def _scheduleAutoPollingRestartAfterWrite(self) -> None:
        """写操作结束后延迟恢复轮询，给设备一点时间完成内部状态更新。"""
        self._writePollingRestartPending = False
        self._writePollRestartTimer.stop()
        self._writePollRestartTimer.start(WRITE_POLL_RESTART_DELAY_MS)

    def _restartAutoPollingAfterWrite(self) -> None:
        if self._shutdownDone or not self.autoPollSwitch.isChecked() or not self._client.is_connected:
            return
        self.startPollingRequested.emit(POWER_POLL_INTERVAL_MS)
        self._appendLog("写入后已请求重启主机轮询")

    def _handleDebugSnapshotReady(self, snapshot: DebugSnapshot) -> None:
        """显示调试快照，并附带一段面向硬件排查的判断提示。"""
        self._appendLog(self._client.pretty_print_debug_snapshot(snapshot))
        self._appendLog(self._diagnoseDebugSnapshot(snapshot))

    def _diagnoseDebugSnapshot(self, snapshot: DebugSnapshot) -> str:
        if snapshot.output_voltage_raw >= 4090:
            return "调试判断: type27 接近 4095，请优先检查 MCU ADC 或前端电路。"
        if snapshot.ovp_set_value_mv is not None and snapshot.ovp_set_value_mv == DEFAULT_OVP_SET_VALUE_MV and abs(snapshot.output_voltage_mv - snapshot.ovp_set_value_mv) <= 5:
            return "调试判断: type32=44000 与 type12 重叠，主机字段映射可能有误。"
        if snapshot.loop_current_reference_ma is not None:
            return "调试判断: 已收到控制环调试量；带载时重点看 type41/type42 是否跟随，以及 type43 是否顶到设定电压。"
        return "调试判断: type27 数值合理；如果界面仍异常，请检查主机解析和绑定。"

    def _applyDisconnectedState(self) -> None:
        """回到离线 UI 状态，清掉暂存开关和正在写入的标记。"""
        self._stagedOutputEnabled = None
        self._writePollingRestartPending = False
        self._setWriteControlsEnabled(False)
        self._writePollRestartTimer.stop()
        self.stateBadge.setOnline(False)
        self.connectButton.setText("连接")
        self.parameterEditor.outputSwitch.blockSignals(True)
        self.parameterEditor.outputSwitch.setChecked(False)
        self.parameterEditor.outputSwitch.blockSignals(False)
        if self.parameterEditor.ovp.value() <= 0:
            self.parameterEditor.ovp.setValue(DEFAULT_OVP_SET_VALUE_MV / 1000.0)

    def _writePageLogFile(self, text: str) -> None:
        try:
            self._pageLogPath.parent.mkdir(parents=True, exist_ok=True)
            with self._pageLogPath.open("a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")
        except Exception:
            pass

    def _appendLog(self, text: str) -> None:
        if self._appendLogBusy:
            return
        self._appendLogBusy = True
        try:
            ts = time.strftime("%H:%M:%S")
            self._writePageLogFile(text)
            if getattr(self, "logEdit", None) is not None:
                self.logEdit.append(f"[{ts}] {text}")
        finally:
            self._appendLogBusy = False

    def _setMockEnabled(self, enabled: bool) -> None:
        if enabled:
            self._mockTimer.start()
            self.mockButton.setText("停止假数据")
            self._appendLog("假数据已开启")
        else:
            self._mockTimer.stop()
            self.mockButton.setText("假数据")
            self._appendLog("假数据已关闭")

    def pushMockPowerSample(self) -> None:
        self.chartCard.pushMock()

    def suspendForDaplink(self) -> None:
        self._appendLog("DAPLink 操作开始，已暂停主机轮询。")
        self.stopPollingRequested.emit()

    def resumeAfterDaplink(self) -> None:
        if self._shutdownDone:
            return
        if self.autoPollSwitch.isChecked() and self._client.is_connected:
            self.startPollingRequested.emit(POWER_POLL_INTERVAL_MS)
            self._appendLog("DAPLink 操作结束，已恢复主机轮询。")

    def closeEvent(self, event) -> None:
        self.shutdown()
        super().closeEvent(event)

    def shutdown(self) -> None:
        if self._shutdownDone:
            return
        self._shutdownDone = True
        self._mockTimer.stop()
        self._writePollRestartTimer.stop()
        try:
            if self._manualSession:
                self._manualSession.close()
        except Exception as exc:
            self._writePageLogFile(f"PowerPage manual session shutdown failed: {exc}")
        self._manualSession = None
        try:
            if self._clientThread.isRunning():
                QMetaObject.invokeMethod(self._client, "shutdown", Qt.ConnectionType.BlockingQueuedConnection)
        except Exception as exc:
            self._writePageLogFile(f"PowerPage client shutdown failed: {exc}")
        if self._clientThread.isRunning():
            self._clientThread.quit()
            if not self._clientThread.wait(3000):
                self._writePageLogFile("PowerPage client thread did not exit within 3000 ms")
