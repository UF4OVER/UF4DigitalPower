# -*- coding: utf-8 -*-

import math
import time
from dataclasses import dataclass

from PyQt5.QtCore import QMetaObject, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QDoubleValidator, QFont, QIntValidator
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel, CardWidget, CaptionLabel, ComboBox, FluentIcon as FIF,
    LineEdit, PillPushButton, PrimaryPushButton, PushButton, ScrollArea,
    StrongBodyLabel, SubtitleLabel, SwitchButton, TextEdit, TitleLabel,
    isDarkTheme, setFont,
)

from app.core.channel import ChannelConfig
from app.core.data_hub import DataHub
from app.core.utility import showMessage
from app.manager import StyleSheet

from app.session import (
    DebugSnapshot, F4CPPowerClient, PowerStatus, SerialConfig,
    SerialSession, listSerialPorts, pretty_faults,
)
from app.widgets.chart.chart_model import ChartModel
from app.widgets.chart.realtime_chart_widget import RealtimeChartWidget
from config import CTX, cfg, logger

DEFAULT_OVP_SET_VALUE_MV = 44000
DEFAULT_OVP_SET_VALUE_TEXT = f"{DEFAULT_OVP_SET_VALUE_MV / 1000.0:.3f}"
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
        setFont(self.valueLabel, 28, QFont.DemiBold)
        setFont(self.unitLabel, 15, QFont.DemiBold)

        value_row = QHBoxLayout()
        value_row.setContentsMargins(0, 0, 0, 0)
        value_row.setSpacing(8)
        value_row.addWidget(self.valueLabel)
        value_row.addWidget(self.unitLabel)
        value_row.addStretch(1)

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
        self.unitLabel.setText(metric.unit)
        self.extraLabel.setText(metric.extra)

    def refreshTheme(self) -> None:
        dark = isDarkTheme()
        text = "#F5F7FA" if dark else "#111827"
        muted = "#9AA4B2" if dark else "#64748B"
        self.titleLabel.setStyleSheet(f"color: {self._accent};")
        self.unitLabel.setStyleSheet(f"color: {self._accent};")
        self.valueLabel.setStyleSheet(f"color: {text};")
        self.extraLabel.setStyleSheet(f"color: {muted};")


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


class ParameterEditor(CardWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("PowerParameterEditor")
        self.titleLabel = SubtitleLabel(title, self)
        self.outputVoltage = LineEdit(self)
        self.outputCurrent = LineEdit(self)
        self.ovp = LineEdit(self)
        self.ocp = LineEdit(self)
        self.otp = LineEdit(self)
        self.fan = LineEdit(self)

        self._editors = (
            self.outputVoltage,
            self.outputCurrent,
            self.ovp,
            self.ocp,
            self.otp,
            self.fan,
        )

        for editor in self._editors:
            editor.setFixedHeight(34)
            editor.setClearButtonEnabled(True)
            editor.setMinimumWidth(148)
            editor.setAlignment(Qt.AlignmentFlag.AlignRight)

        decimal_validator = QDoubleValidator(0.0, 9999.999, 3, self)
        decimal_validator.setNotation(QDoubleValidator.StandardNotation)
        fan_validator = QIntValidator(0, 1000, self)

        self.outputVoltage.setValidator(decimal_validator)
        self.outputCurrent.setValidator(decimal_validator)
        self.ovp.setValidator(decimal_validator)
        self.ocp.setValidator(decimal_validator)
        self.otp.setValidator(decimal_validator)
        self.fan.setValidator(fan_validator)

        self.outputVoltage.setPlaceholderText("输出电压 V")
        self.outputCurrent.setPlaceholderText("输出电流 A")
        self.ovp.setPlaceholderText("OVP V")
        self.ocp.setPlaceholderText("OCP A")
        self.otp.setPlaceholderText("OTP °C")
        self.fan.setPlaceholderText("风扇 0-1000")

        self.outputSwitch = SwitchButton(self)
        self.outputSwitch.setOnText("输出开启")
        self.outputSwitch.setOffText("输出关闭")
        self.applyOutputButton = PrimaryPushButton(FIF.ACCEPT, "应用输出", self)
        self.applyProtectButton = PushButton(FIF.SAVE, "应用保护", self)
        self.outputSwitch.setFixedHeight(34)
        self.applyOutputButton.setFixedHeight(34)
        self.applyProtectButton.setFixedHeight(34)
        self.applyOutputButton.setMinimumWidth(110)
        self.applyProtectButton.setMinimumWidth(110)

        form = QGridLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(10)
        labels = (("电压", self.outputVoltage), ("电流", self.outputCurrent), ("OVP", self.ovp), ("OCP", self.ocp), ("OTP", self.otp), ("风扇", self.fan))
        for i, (label, editor) in enumerate(labels):
            r, c = divmod(i, 2)
            form.addWidget(BodyLabel(label, self), r, c * 2)
            form.addWidget(editor, r, c * 2 + 1)

        control = QHBoxLayout()
        control.setContentsMargins(0, 6, 0, 0)
        control.setSpacing(10)
        control.addWidget(self.outputSwitch)
        control.addStretch(1)
        control.addWidget(self.applyOutputButton)
        control.addWidget(self.applyProtectButton)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(self.titleLabel)
        layout.addLayout(form)
        layout.addLayout(control)

    def setFromStatus(self, status: PowerStatus) -> None:
        values = {
            self.outputVoltage: f"{status.set_voltage_limit_mv / 1000.0:.3f}",
            self.outputCurrent: f"{status.set_current_limit_ma / 1000.0:.3f}",
            self.ovp: f"{status.ovp_set_value_v:.3f}",
            self.ocp: f"{status.ocp_set_value_a:.3f}",
            self.otp: f"{status.otp_set_value_c:.3f}",
            self.fan: str(status.fan_set_value),
        }
        for editor, value in values.items():
            if not editor.hasFocus():
                editor.setText(value)

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

        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 0, 0, 0)
        self.verticalScrollBar().valueChanged.connect(self._onScrollValueChanged)

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
        self.metricsGrid.setVerticalSpacing(12)
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
        row.setSpacing(12)
        self.statusCard = CardWidget(self.scrollWidget)
        self.statusCard.setObjectName("PowerStatusCard")
        statusLayout = QVBoxLayout(self.statusCard)
        statusLayout.setContentsMargins(18, 18, 18, 18)
        statusLayout.setSpacing(10)
        self.statusTitle = SubtitleLabel("状态", self.statusCard)
        self.statusInfo = QLabel("等待设备数据", self.statusCard)
        self.statusInfo.setWordWrap(True)
        self.statusInfo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        statusLayout.addWidget(self.statusTitle)
        statusLayout.addWidget(self.statusInfo, 1)
        self.parameterEditor = ParameterEditor("输出设定与保护阈值", self.scrollWidget)
        row.addWidget(self.statusCard, 1)
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
        self._client.log.connect(self._appendLog)
        self._client.error.connect(self._onClientError)
        self._client.connectionChanged.connect(self._onConnectionChanged)
        self._client.statusUpdated.connect(self._updateStatusView)
        self._client.debugSnapshotReady.connect(self._handleDebugSnapshotReady)
        self._client.outputLimitsWritten.connect(self._onOutputLimitsWritten)
        self._client.protectionValuesWritten.connect(self._onProtectionValuesWritten)
        self._client.powerStateWritten.connect(self._onPowerStateWritten)
        self._client.writeFailureLimitReached.connect(self._disconnectAfterWriteFailures)

        self.attachSessionRequested.connect(self._client.attach_session)
        self.detachSessionRequested.connect(self._client.detach_session)
        self.readStatusRequested.connect(self._client.request_read_status)
        self.debugSnapshotRequested.connect(self._client.request_debug_snapshot)
        self.outputLimitsRequested.connect(self._client.request_set_output_limits)
        self.protectionValuesRequested.connect(self._client.request_set_protection_values)
        self.powerStateRequested.connect(self._client.request_set_power_state)
        self.startPollingRequested.connect(self._client.start_polling)
        self.stopPollingRequested.connect(self._client.stop_polling)
        self.refreshTargetButton.clicked.connect(self.refreshSerialPorts)
        self.connectButton.clicked.connect(self.toggleConnection)
        self.refreshButton.clicked.connect(self._readStatusOnce)
        self.debugButton.clicked.connect(self._runDebugSnapshot)
        self.autoPollSwitch.checkedChanged.connect(self._onAutoPollChanged)
        self.parameterEditor.outputSwitch.checkedChanged.connect(self._onOutputSwitchChanged)
        self.parameterEditor.applyOutputButton.clicked.connect(self._applyOutputLimits)
        self.parameterEditor.applyProtectButton.clicked.connect(self._applyProtectionValues)
        self.clearLogButton.clicked.connect(self.logEdit.clear)
        self.mockButton.toggled.connect(self._setMockEnabled)
        cfg.themeChanged.connect(self._onThemeChanged)

    def _onThemeChanged(self, *_):
        StyleSheet.POWER_PAGE.apply(self)
        for card in self.metricCards.values():
            card.refreshTheme()
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

    def toggleConnection(self) -> None:
        if self._client.is_connected:
            self._disconnectManualSession()
        else:
            self._connectSerialTarget()

    def _connectSerialTarget(self) -> None:
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
        previous = self._lastStatus
        self._lastStatus = status
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
        faults = pretty_faults(status.fault_state) or "无"
        self.statusInfo.setText(
            f"输出：{'开启' if status.power_enabled else '关闭'}\n"
            f"拓扑：{status.topology_name}\n"
            f"控制模式：{status.mode_name}\n"
            f"状态机：{status.state_flag_name}\n"
            f"故障：{faults}\n"
            f"核心温度：{status.core_temp_c:.2f} °C\n"
            f"板载温度：{status.board_temp_c:.2f} °C\n"
            f"PWM A/D：{status.pwm_a_compare} / {status.pwm_d_compare}\n"
            f"风扇：{status.fan_speed} / 设定 {status.fan_set_value}"
        )
        if previous is None or previous.power_state != status.power_state or previous.state_machine_flag_bits != status.state_machine_flag_bits or previous.fault_state != status.fault_state:
            self._appendLog(f"状态 输出={'开启' if status.power_enabled else '关闭'} 状态机={status.state_flag_name} 拓扑={status.topology_name} 故障={faults} VOUT={status.vout_v:.3f}V IOUT={status.iout_a:.3f}A")
        if self.logLevelCombo.currentData() == "verbose" and time.monotonic() - self._lastVerboseLogTs >= 2.0:
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
        if checked:
            self.startPollingRequested.emit(POWER_POLL_INTERVAL_MS)
        else:
            self.stopPollingRequested.emit()
            self._appendLog("主机轮询已关闭")

    def _onOutputSwitchChanged(self, checked: bool) -> None:
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
        if not self._client.is_connected:
            self._appendLog("错误: 串口会话未连接")
            return
        if self._writeInFlight:
            self._appendLog("写入进行中，请等待当前操作完成")
            return
        try:
            voltage_mv = int(round(float(self.parameterEditor.outputVoltage.text() or "0") * 1000))
            current_ma = int(round(float(self.parameterEditor.outputCurrent.text() or "0") * 1000))
        except ValueError:
            self._appendLog("错误: 输出电压/电流格式不正确")
            return
        enabled = self._stagedOutputEnabled if self._stagedOutputEnabled is not None else self.parameterEditor.outputSwitch.isChecked()
        self._setWriteControlsEnabled(False)
        self._writePollingRestartPending = True
        self.outputLimitsRequested.emit(voltage_mv, current_ma, enabled)

    def _applyProtectionValues(self) -> None:
        if not self._client.is_connected:
            self._appendLog("错误: 串口会话未连接")
            return
        if self._writeInFlight:
            self._appendLog("写入进行中，请等待当前操作完成")
            return
        try:
            ovp_mv = int(round(float(self.parameterEditor.ovp.text() or "0") * 1000))
            ocp_ma = int(round(float(self.parameterEditor.ocp.text() or "0") * 1000))
            otp_mc = int(round(float(self.parameterEditor.otp.text() or "0") * 1000))
            fan_value = int(float(self.parameterEditor.fan.text() or "0"))
        except ValueError:
            self._appendLog("错误: 保护参数格式不正确")
            return
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

    def _scheduleAutoPollingRestartAfterWrite(self) -> None:
        self._writePollingRestartPending = False
        self._writePollRestartTimer.stop()
        self._writePollRestartTimer.start(WRITE_POLL_RESTART_DELAY_MS)

    def _restartAutoPollingAfterWrite(self) -> None:
        if self._shutdownDone or not self.autoPollSwitch.isChecked() or not self._client.is_connected:
            return
        self.startPollingRequested.emit(POWER_POLL_INTERVAL_MS)
        self._appendLog("写入后已请求重启主机轮询")

    def _handleDebugSnapshotReady(self, snapshot: DebugSnapshot) -> None:
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
        self._stagedOutputEnabled = None
        self._writePollingRestartPending = False
        self._setWriteControlsEnabled(False)
        self._writePollRestartTimer.stop()
        self.stateBadge.setOnline(False)
        self.connectButton.setText("连接")
        self.parameterEditor.outputSwitch.blockSignals(True)
        self.parameterEditor.outputSwitch.setChecked(False)
        self.parameterEditor.outputSwitch.blockSignals(False)
        if not self.parameterEditor.ovp.text():
            self.parameterEditor.ovp.setText(DEFAULT_OVP_SET_VALUE_TEXT)

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

