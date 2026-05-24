# -*- coding: utf-8 -*-
from __future__ import annotations

import collections
import time
from dataclasses import dataclass
from pathlib import Path

from PyQt5.QtBluetooth import QBluetoothLocalDevice, QBluetoothDeviceDiscoveryAgent
from PyQt5.QtCore import QMetaObject, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QFileDialog, QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    CaptionLabel,
    ComboBox,
    FluentIcon as FIF,
    LineEdit,
    PillPushButton,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    StrongBodyLabel,
    SubtitleLabel,
    SwitchButton,
    TextEdit,
    TitleLabel,
    isDarkTheme,
    setFont,
)


from app.session import DebugSnapshot, F4CPPowerClient, PowerStatus, pretty_faults, PowerBluetoothSession
from app.session import (
    SerialConfig,
    SerialSession,
    listSerialPorts,
)
from app.manager import  StyleSheet

from app.core.utility import showMessage

from config import cfg, logger

DEFAULT_OVP_SET_VALUE_MV = 44000
DEFAULT_OVP_SET_VALUE_TEXT = f"{DEFAULT_OVP_SET_VALUE_MV / 1000.0:.3f}"
POWER_POLL_INTERVAL_MS = 500
POWER_SERIAL_BAUD_RATE = 921600
WRITE_POLL_RESTART_DELAY_MS = 600
PLOT_Y_MIN = 0
PLOT_Y_MAX = 45
PLOT_CURRENT_Y_MIN = 0
PLOT_CURRENT_Y_MAX = 12

POWER_TEXT = {
    "core Temperature": "核心温度",
    "Board Temperature": "板载温度",
    "CC/CV Mode": "CC/CV 模式",
    "Topology": "拓扑",
    "State Machine": "状态机",
    "Fault Flags": "故障标志",
    "Fan PWM": "风扇 PWM",
    "Output Voltage Setpoint": "输出电压设定",
    "Output Current Setpoint": "输出电流设定",
    "OVP Threshold": "过压保护阈值",
    "OCP Threshold": "过流保护阈值",
    "OTP Threshold": "过温保护阈值",
    "Fan Set Value": "风扇设定值",
    "Input Voltage": "输入电压",
    "Input Current": "输入电流",
    "Input Power": "输入功率",
    "Output Voltage": "输出电压",
    "Output Current": "输出电流",
    "Output Power": "输出功率",
}


@dataclass(frozen=True)
class _MetricValue:
    title: str
    value: str
    unit: str


class MetricCard(CardWidget):
    def __init__(self, title: str, accent: str, parent=None):
        super().__init__(parent)
        self._accent = accent
        self._title = title
        self.setProperty("cardRole", "metric")

        self.titleLabel = CaptionLabel(title, self)
        self.valueLabel = TitleLabel("--", self)
        self.unitLabel = StrongBodyLabel("", self)
        self.extraLabel = CaptionLabel("", self)

        self.valueLabel.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.unitLabel.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.extraLabel.setWordWrap(True)

        setFont(self.valueLabel, 28, QFont.DemiBold)
        setFont(self.unitLabel, 16, QFont.DemiBold)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(10)
        head.addWidget(self.valueLabel)
        head.addWidget(self.unitLabel)
        head.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)
        layout.addWidget(self.titleLabel)
        layout.addLayout(head)
        layout.addWidget(self.extraLabel)

        self.setMinimumHeight(150)
        self.titleLabel.setStyleSheet(f"color: {self._accent};")
        self.unitLabel.setStyleSheet(f"color: {self._accent};")

    def setMetric(self, metric: _MetricValue, extra: str = "") -> None:
        self.titleLabel.setText(metric.title)
        self.valueLabel.setText(metric.value)
        self.unitLabel.setText(metric.unit)
        self.extraLabel.setText(extra)


class ParameterRow(QWidget):
    NAME_COLUMN_WIDTH = 170
    VALUE_COLUMN_WIDTH = 118
    UNIT_COLUMN_WIDTH = 52

    def __init__(
        self,
        name: str,
        access: str,
        unit: str = "",
        editable: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._editable = editable
        self._unit = unit
        self._name = name

        self.nameLabel = BodyLabel(name, self)
        self.nameLabel.setFixedWidth(self.NAME_COLUMN_WIDTH)
        self.accessBadge = PillPushButton(access, self)
        self.accessBadge.setProperty("accessBadge", True)
        self.accessBadge.setProperty("accessType", access.upper())
        self.accessBadge.setCheckable(False)
        self.accessBadge.setFixedHeight(28)
        self.accessBadge.setFixedWidth(54)

        self.valueLabel = StrongBodyLabel("--", self)
        self.valueLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.valueLabel.setFixedWidth(self.VALUE_COLUMN_WIDTH)
        self.editor = LineEdit(self)
        self.editor.setProperty("parameterEditor", True)
        self.editor.setPlaceholderText(unit or "value")
        self.editor.setFixedWidth(self.VALUE_COLUMN_WIDTH)
        self.editor.setVisible(editable)
        self.valueLabel.setVisible(not editable)

        self.unitLabel = CaptionLabel(unit, self)
        self.unitLabel.setFixedWidth(self.UNIT_COLUMN_WIDTH)
        self.unitLabel.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.nameLabel, 0)
        layout.addWidget(self.accessBadge, 0)
        layout.addWidget(
            self.valueLabel if not editable else self.editor, 0, Qt.AlignRight
        )
        layout.addWidget(self.unitLabel, 0)
        layout.addStretch(1)

    def setDisplayValue(self, value: str) -> None:
        self.valueLabel.setText(value)
        if self._editable and not self.editor.hasFocus():
            self.editor.setText(value)

    def text(self) -> str:
        return (
            self.editor.text().strip()
            if self._editable
            else self.valueLabel.text().strip()
        )

    def applyTexts(self) -> None:
        self.nameLabel.setText(POWER_TEXT.get(self._name, self._name))
        if self._editable:
            self.editor.setPlaceholderText(self._unit or "value")


class TrendPlotCard(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("trendPlotCard")
        self.titleLabel = SubtitleLabel(self)
        self.tipLabel = CaptionLabel(self)
        self.saveButton = PushButton(FIF.SAVE, "", self)
        self.plotPanel = QFrame(self)
        self.plotPanel.setObjectName("trendPlotPanel")
        self._viewInitialized = False

        self.voltagePlotWidget = self._createPlotWidget("voltageTrendPlotWidget")
        self.currentPlotWidget = self._createPlotWidget("currentTrendPlotWidget")
        self.voltagePlotWidget.setYRange(PLOT_Y_MIN, PLOT_Y_MAX, padding=0)
        self.currentPlotWidget.setYRange(PLOT_CURRENT_Y_MIN, PLOT_CURRENT_Y_MAX, padding=0)

        self.voltageLegend = self.voltagePlotWidget.addLegend(offset=(12, 12))
        self.currentLegend = self.currentPlotWidget.addLegend(offset=(12, 12))

        self.voltageInCurve = self.voltagePlotWidget.plot(name="VIN", pen=pg.mkPen(width=2))
        self.voltageOutCurve = self.voltagePlotWidget.plot(name="VOUT", pen=pg.mkPen(width=2))
        self.currentInCurve = self.currentPlotWidget.plot(
            name="IIN", pen=pg.mkPen(width=2, style=Qt.DashLine)
        )
        self.currentOutCurve = self.currentPlotWidget.plot(
            name="IOUT", pen=pg.mkPen(width=2, style=Qt.DotLine)
        )

        self.voltageInCurve.setClipToView(True)
        self.voltageOutCurve.setClipToView(True)
        self.currentInCurve.setClipToView(True)
        self.currentOutCurve.setClipToView(True)

        plotPanelLayout = QHBoxLayout(self.plotPanel)
        plotPanelLayout.setContentsMargins(14, 14, 14, 14)
        plotPanelLayout.setSpacing(12)
        plotPanelLayout.addWidget(self.voltagePlotWidget, 1)
        plotPanelLayout.addWidget(self.currentPlotWidget, 1)

        headerLayout = QHBoxLayout()
        headerLayout.setContentsMargins(0, 0, 0, 0)
        headerLayout.setSpacing(10)
        headerLayout.addWidget(self.titleLabel)
        headerLayout.addStretch(1)
        headerLayout.addWidget(self.saveButton)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        layout.addLayout(headerLayout)
        layout.addWidget(self.tipLabel)
        layout.addWidget(self.plotPanel)

        self.saveButton.clicked.connect(self.saveImage)
        self.applyTexts()
        self.refreshTheme()

    def _createPlotWidget(self, objectName: str) -> pg.PlotWidget:
        plotWidget = pg.PlotWidget(self)
        plotWidget.setObjectName(objectName)
        plotWidget.setFrameShape(QFrame.NoFrame)
        plotWidget.setStyleSheet("background: transparent; border: none;")
        plotWidget.setMouseEnabled(x=True, y=True)
        plotWidget.showGrid(x=True, y=True, alpha=0.16)
        plotWidget.setAntialiasing(True)
        plotWidget.setMenuEnabled(False)
        plotWidget.setMinimumHeight(360)
        plotWidget.getPlotItem().hideButtons()
        plotWidget.getViewBox().setMouseEnabled(x=True, y=True)
        plotWidget.getViewBox().setMenuEnabled(False)
        plotWidget.enableAutoRange(x=False, y=False)
        return plotWidget

    def applyTexts(self) -> None:
        self.titleLabel.setText('电压 / 电流趋势')
        self.tipLabel.setText('左侧电压，右侧电流；拖动平移，滚轮缩放')
        self.saveButton.setText('保存图片')

    def saveImage(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            '选择保存文件夹',
            str(Path.home()),
        )
        if not folder:
            return

        path = Path(folder) / f"power-trend-{time.strftime('%Y%m%d-%H%M%S')}.png"
        if not self.plotPanel.grab().save(str(path), "PNG"):
            showMessage(
                self,
                '操作失败',
                '图表图片保存失败。',
                level="error",
            )
            return

        showMessage(
            self,
            '图表已保存',
            '已保存到 {path}'.format(path=str(path)),
            level="success",
        )

    def refreshTheme(self) -> None:
        dark = isDarkTheme()
        axis = "#DCE3EA" if dark else "#334155"
        titleColor = "#F5F7FA" if dark else "#111827"
        tipColor = "#9AA4B2" if dark else "#6B7280"
        legendBackground = (
            QColor(30, 30, 30, 188) if dark else QColor(255, 255, 255, 232)
        )
        legendBorder = QColor(255, 255, 255, 28) if dark else QColor(15, 23, 42, 22)
        borderPenColor = QColor(255, 255, 255, 24) if dark else QColor(15, 23, 42, 24)

        # Card and plot panel surface colors come from theme QSS.
        self.setStyleSheet("")
        self.titleLabel.setStyleSheet(f"color: {titleColor};")
        self.tipLabel.setStyleSheet(f"color: {tipColor};")

        self._stylePlot(
            self.voltagePlotWidget,
            axis,
            borderPenColor,
            "电压",
            "V",
            dark,
        )
        self._stylePlot(
            self.currentPlotWidget,
            axis,
            borderPenColor,
            "电流",
            "A",
            dark,
        )

        self.voltageInCurve.setPen(pg.mkPen(QColor("#2F80ED"), width=2))
        self.voltageOutCurve.setPen(pg.mkPen(QColor("#27AE60"), width=2))
        self.currentInCurve.setPen(
            pg.mkPen(QColor("#F2994A"), width=2, style=Qt.DashLine)
        )
        self.currentOutCurve.setPen(
            pg.mkPen(QColor("#EB5757"), width=2, style=Qt.DotLine)
        )

        for legend in (self.voltageLegend, self.currentLegend):
            if legend is not None:
                legend.setBrush(legendBackground)
                legend.setPen(legendBorder)
                legend.setLabelTextColor(axis)
                legend.setLabelTextSize("9pt")
        for plotWidget in (self.voltagePlotWidget, self.currentPlotWidget):
            plotItem = plotWidget.getPlotItem()
            plotItem.getAxis("left").setGrid(64)
            plotItem.getAxis("bottom").setGrid(64)

    def _stylePlot(
        self,
        plotWidget: pg.PlotWidget,
        axis: str,
        borderPenColor: QColor,
        axisLabel: str,
        unit: str,
        dark: bool,
    ) -> None:
        plotWidget.setBackground((0, 0, 0, 0))
        plotItem = plotWidget.getPlotItem()
        plotItem.setTitle("")
        plotItem.getAxis("left").setTextPen(axis)
        plotItem.getAxis("bottom").setTextPen(axis)
        plotItem.getAxis("left").setPen(pg.mkPen(axis))
        plotItem.getAxis("bottom").setPen(pg.mkPen(axis))
        plotItem.getAxis("left").setLabel(axisLabel, color=axis, units=unit)
        plotItem.getAxis("bottom").setLabel('采样点', color=axis)
        plotItem.getViewBox().setBorder(pg.mkPen(borderPenColor))
        plotItem.showGrid(x=True, y=True, alpha=0.22 if dark else 0.18)

        for axisName in ("left", "bottom"):
            axisItem = plotItem.getAxis(axisName)
            axisItem.setTickPen(pg.mkPen(axis))
            axisItem.setStyle(tickTextOffset=10)
        plotItem.getAxis("left").setGrid(64)
        plotItem.getAxis("bottom").setGrid(64)

    def updateSeries(
        self,
        xValues: list[float],
        vin: list[float],
        vout: list[float],
        iin: list[float],
        iout: list[float],
    ) -> None:
        self.voltageInCurve.setData(xValues, vin)
        self.voltageOutCurve.setData(xValues, vout)
        self.currentInCurve.setData(xValues, iin)
        self.currentOutCurve.setData(xValues, iout)
        if xValues and not self._viewInitialized:
            x_min = xValues[0]
            x_max = xValues[-1]
            if x_max <= x_min:
                x_max = x_min + 1
            self.voltagePlotWidget.setXRange(x_min, x_max, padding=0.02)
            self.currentPlotWidget.setXRange(x_min, x_max, padding=0.02)
            self.voltagePlotWidget.setYRange(PLOT_Y_MIN, PLOT_Y_MAX, padding=0)
            self.currentPlotWidget.setYRange(
                PLOT_CURRENT_Y_MIN, PLOT_CURRENT_Y_MAX, padding=0
            )
            self.voltagePlotWidget.enableAutoRange(x=False, y=False)
            self.currentPlotWidget.enableAutoRange(x=False, y=False)
            self._viewInitialized = True





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

        self._client = F4CPPowerClient()
        self._clientThread = QThread(self)
        self._client.moveToThread(self._clientThread)
        self._clientThread.finished.connect(self._client.deleteLater)
        self._clientThread.start()
        self._manualSession = None
        self._bluetoothDevices: dict[str, str] = {}
        self._bluetoothDiscoveryAgent = None
        self._lastStatus: PowerStatus | None = None
        self._stagedOutputEnabled: bool | None = None
        self._lastVerboseLogTs = 0.0
        self._writePollingRestartPending = False
        self._writeInFlight = False
        self._historyDirty = False
        self._plotRefreshTimer = QTimer(self)
        self._plotRefreshTimer.setInterval(200)
        self._plotRefreshTimer.timeout.connect(self._flushPlotUpdate)
        self._writePollRestartTimer = QTimer(self)
        self._writePollRestartTimer.setSingleShot(True)
        self._writePollRestartTimer.timeout.connect(
            self._restartAutoPollingAfterWrite
        )
        self._history = {
            "t": collections.deque(maxlen=240),
            "vin": collections.deque(maxlen=240),
            "vout": collections.deque(maxlen=240),
            "iin": collections.deque(maxlen=240),
            "iout": collections.deque(maxlen=240),
        }

        self.scrollWidget = QWidget(self)
        self.scrollWidget.setObjectName("powerScrollWidget")
        self.rootLayout = QVBoxLayout(self.scrollWidget)
        self.rootLayout.setContentsMargins(24, 24, 24, 24)
        self.rootLayout.setSpacing(12)

        self.titleLabel = TitleLabel(self.scrollWidget)
        self.rootLayout.addWidget(self.titleLabel)

        self._initSummaryCard()
        self._initMetricCards()
        self._initParameterCards()
        self._initPlotCard()
        self._initLogCard()

        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 0, 0, 0)

        self._bindSignals()
        self._applyDisconnectedState()
        StyleSheet.POWER_PAGE.apply(self)
        self._refreshThemeBundle()
        self._applyTexts()

        self.refreshSerialPorts()

    def _initSummaryCard(self) -> None:
        self.summaryCard = CardWidget(self.scrollWidget)
        self.summaryCard.setObjectName("powerSummaryCard")
        layout = QHBoxLayout(self.summaryCard)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        self.connectionTypeLabel = BodyLabel(self.summaryCard)
        self.connectionTypeCombo = ComboBox(self.summaryCard)
        self.connectionTypeCombo.addItems(["串口", "蓝牙"])
        self.connectionTypeCombo.setMinimumWidth(92)
        self.portLabel = BodyLabel(self.summaryCard)
        self.portCombo = ComboBox(self.summaryCard)
        self.portCombo.setMinimumWidth(132)
        self.bluetoothLabel = BodyLabel(self.summaryCard)
        self.bluetoothCombo = ComboBox(self.summaryCard)
        self.bluetoothCombo.setMinimumWidth(160)
        self.refreshTargetButton = PushButton(FIF.SYNC, "", self.summaryCard)
        self.connectButton = PrimaryPushButton(FIF.LINK, "", self.summaryCard)
        self.stateBadge = PillPushButton(self.summaryCard)
        self.stateBadge.setProperty("statusBadge", True)
        self.stateBadge.setProperty("onlineState", "offline")
        self.stateBadge.setCheckable(False)
        self.stateBadge.setFixedHeight(30)
        self.stateBadge.setFixedWidth(84)

        self.autoPollSwitch = SwitchButton(self.summaryCard)
        self.autoPollSwitch.setChecked(True)

        self.refreshButton = PrimaryPushButton(FIF.SYNC, "", self.summaryCard)
        self.debugButton = PushButton(FIF.SEARCH, "", self.summaryCard)

        layout.addWidget(self.connectionTypeLabel)
        layout.addWidget(self.connectionTypeCombo)
        layout.addWidget(self.portLabel)
        layout.addWidget(self.portCombo)
        layout.addWidget(self.bluetoothLabel)
        layout.addWidget(self.bluetoothCombo)
        layout.addWidget(self.refreshTargetButton)
        layout.addWidget(self.connectButton)
        layout.addSpacing(10)
        self.stateCaptionLabel = BodyLabel(self.summaryCard)
        layout.addWidget(self.stateCaptionLabel)
        layout.addWidget(self.stateBadge)
        layout.addStretch(1)
        layout.addWidget(self.autoPollSwitch)
        layout.addWidget(self.refreshButton)
        layout.addWidget(self.debugButton)

        self.rootLayout.addWidget(self.summaryCard)

    def _initMetricCards(self) -> None:
        self.metricsGrid = QGridLayout()
        self.metricsGrid.setHorizontalSpacing(12)
        self.metricsGrid.setVerticalSpacing(12)

        self.metricCards = {
            "vin": MetricCard("", "#2F80ED", self.scrollWidget),
            "iin": MetricCard("", "#F2994A", self.scrollWidget),
            "pin": MetricCard("", "#56CCF2", self.scrollWidget),
            "vout": MetricCard("", "#27AE60", self.scrollWidget),
            "iout": MetricCard("", "#EB5757", self.scrollWidget),
            "pout": MetricCard("", "#9B51E0", self.scrollWidget),
        }

        positions = [
            ("vin", 0, 0),
            ("iin", 0, 1),
            ("pin", 0, 2),
            ("vout", 1, 0),
            ("iout", 1, 1),
            ("pout", 1, 2),
        ]
        for key, row, col in positions:
            self.metricsGrid.addWidget(self.metricCards[key], row, col)

        self.rootLayout.addLayout(self.metricsGrid)

    def _initParameterCards(self) -> None:
        self.parameterRowLayout = QHBoxLayout()
        self.parameterRowLayout.setSpacing(12)

        self.readCard = CardWidget(self.scrollWidget)
        self.writeCard = CardWidget(self.scrollWidget)
        self.readCard.setObjectName("powerReadCard")
        self.writeCard.setObjectName("powerWriteCard")

        self.parameterRowLayout.addWidget(self.readCard, 1)
        self.parameterRowLayout.addWidget(self.writeCard, 1)

        readLayout = QVBoxLayout(self.readCard)
        readLayout.setContentsMargins(18, 18, 18, 18)
        readLayout.setSpacing(10)
        self.readCardTitle = SubtitleLabel(self.readCard)
        readLayout.addWidget(self.readCardTitle)

        self.readParams = {
            "core_temp": ParameterRow(
                "core Temperature", "RO", "°C", False, self.readCard
            ),
            "board_temp": ParameterRow(
                "Board Temperature", "RO", "°C", False, self.readCard
            ),
            "mode": ParameterRow("CC/CV Mode", "RO", "", False, self.readCard),
            "topology": ParameterRow("Topology", "RO", "", False, self.readCard),
            "state_flag": ParameterRow("State Machine", "RO", "", False, self.readCard),
            "fault": ParameterRow("Fault Flags", "RO", "", False, self.readCard),
            "fan_speed": ParameterRow("Fan PWM", "RO", "0-1000", False, self.readCard),
        }
        for row in self.readParams.values():
            readLayout.addWidget(row)
        readLayout.addStretch(1)

        writeLayout = QVBoxLayout(self.writeCard)
        writeLayout.setContentsMargins(18, 18, 18, 18)
        writeLayout.setSpacing(10)
        self.writeCardTitle = SubtitleLabel(self.writeCard)
        writeLayout.addWidget(self.writeCardTitle)

        self.writeParams = {
            "set_voltage": ParameterRow(
                "Output Voltage Setpoint", "RW", "V", True, self.writeCard
            ),
            "set_current": ParameterRow(
                "Output Current Setpoint", "RW", "A", True, self.writeCard
            ),
            "ovp": ParameterRow("OVP Threshold", "RW", "V", True, self.writeCard),
            "ocp": ParameterRow("OCP Threshold", "RW", "A", True, self.writeCard),
            "otp": ParameterRow("OTP Threshold", "RW", "°C", True, self.writeCard),
            "fan_set": ParameterRow("Fan Set Value", "RW", "0-1000", True, self.writeCard),
        }
        for row in self.writeParams.values():
            writeLayout.addWidget(row)

        controlRow = QHBoxLayout()
        controlRow.setContentsMargins(0, 8, 0, 0)
        controlRow.setSpacing(10)

        self.outputSwitch = SwitchButton(self.writeCard)
        self.applySetButton = PrimaryPushButton(FIF.ACCEPT, "", self.writeCard)
        self.applyProtectButton = PushButton(FIF.SAVE, "", self.writeCard)

        controlRow.addWidget(self.outputSwitch)
        controlRow.addStretch(1)
        controlRow.addWidget(self.applySetButton)
        controlRow.addWidget(self.applyProtectButton)
        writeLayout.addLayout(controlRow)
        writeLayout.addStretch(1)

        self.rootLayout.addLayout(self.parameterRowLayout)

    def _initPlotCard(self) -> None:
        self.plotCard = TrendPlotCard(self.scrollWidget)
        self.rootLayout.addWidget(self.plotCard)

    def _initLogCard(self) -> None:
        self.logCard = CardWidget(self.scrollWidget)
        self.logCard.setObjectName("powerLogCard")
        layout = QVBoxLayout(self.logCard)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        top = QHBoxLayout()
        self.logCardTitle = SubtitleLabel(self.logCard)
        top.addWidget(self.logCardTitle)
        top.addStretch(1)

        self.logLevelCombo = ComboBox(self.logCard)
        self.clearLogButton = PushButton(FIF.BROOM, "", self.logCard)
        top.addWidget(self.logLevelCombo)
        top.addWidget(self.clearLogButton)

        self.logEdit = TextEdit(self.logCard)
        self.logEdit.setMinimumHeight(180)
        self.logEdit.setReadOnly(True)
        self.logEdit.document().setMaximumBlockCount(400)

        layout.addLayout(top)
        layout.addWidget(self.logEdit)
        self.rootLayout.addWidget(self.logCard)

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
        self.protectionValuesRequested.connect(
            self._client.request_set_protection_values
        )
        self.powerStateRequested.connect(self._client.request_set_power_state)
        self.startPollingRequested.connect(self._client.start_polling)
        self.stopPollingRequested.connect(self._client.stop_polling)

        self.connectionTypeCombo.currentTextChanged.connect(self._onConnectionTypeChanged)
        self.refreshTargetButton.clicked.connect(self.refreshCurrentConnectionTargets)
        self.connectButton.clicked.connect(self.toggleConnection)
        self.refreshButton.clicked.connect(self._readStatusOnce)
        self.debugButton.clicked.connect(self._runDebugSnapshot)
        self.autoPollSwitch.checkedChanged.connect(self._onAutoPollChanged)
        self.outputSwitch.checkedChanged.connect(self._onOutputSwitchChanged)
        self.applySetButton.clicked.connect(self._applyOutputLimits)
        self.applyProtectButton.clicked.connect(self._applyProtectionValues)
        self.clearLogButton.clicked.connect(self.logEdit.clear)
        cfg.themeChanged.connect(self._onThemeChanged)

    def refreshSerialPorts(self) -> None:
        ports = [p.strip() for p in (listSerialPorts() or []) if p and p.strip()]
        current = self.portCombo.currentText().strip()
        self.portCombo.clear()
        if ports:
            self.portCombo.addItems(ports)
            if current in ports:
                self.portCombo.setCurrentText(current)
        self._appendLog(f"串口列表: {ports}")

    def refreshBluetoothDevices(self) -> None:
        current = self.bluetoothCombo.currentText().strip()
        self._bluetoothDevices.clear()
        self.bluetoothCombo.clear()

        if QBluetoothLocalDevice is None:
            self._appendLog("错误: 当前环境不支持 Qt Bluetooth")
            return

        try:
            for localInfo in QBluetoothLocalDevice.allDevices():
                localDevice = QBluetoothLocalDevice(localInfo.address())
                for address in localDevice.connectedDevices():
                    self._addBluetoothTarget(address.toString(), address.toString())
        except Exception as exc:
            self._appendLog(f"错误: 蓝牙设备列表读取失败: {exc}")

        if current in self._bluetoothDevices:
            self.bluetoothCombo.setCurrentText(current)

        self._appendLog(f"蓝牙设备列表: {list(self._bluetoothDevices)}")
        self._startBluetoothDiscovery()

    def refreshCurrentConnectionTargets(self) -> None:
        if self._isBluetoothMode():
            self.refreshBluetoothDevices()
        else:
            self.refreshSerialPorts()

    def toggleConnection(self) -> None:
        if self._client.is_connected:
            self._disconnectManualSession()
        else:
            self._connectSelectedTarget()

    def _connectSelectedTarget(self) -> None:
        if self._isBluetoothMode():
            self._connectBluetoothTarget()
        else:
            self._connectSerialTarget()

    def _connectSerialTarget(self) -> None:
        port = self.portCombo.currentText().strip()
        if not port:
            self._appendLog("错误: 未选择串口。请先刷新并选择串口。")
            return

        session = SerialSession(
            SerialConfig(port=port, baudrate=POWER_SERIAL_BAUD_RATE)
        )
        try:
            session.open()
        except Exception as exc:
            self._appendLog(f"错误: {exc}")
            return

        self._manualSession = session
        self.onDeviceConnected(session)

    def _connectBluetoothTarget(self) -> None:
        target = self.bluetoothCombo.currentText().strip()
        address = self._bluetoothDevices.get(target, "")
        if not target or not address:
            self._appendLog("错误: 未选择蓝牙设备。请先刷新并选择设备。")
            return

        session = PowerBluetoothSession(target.rsplit(" (", 1)[0], address, self)
        try:
            session.open()
        except Exception as exc:
            self._appendLog(f"错误: {exc}")
            return

        self._manualSession = session
        self.onDeviceConnected(session)

    def _disconnectManualSession(self) -> None:
        self.stopPollingRequested.emit()
        self.detachSessionRequested.emit()
        try:
            if self._manualSession:
                self._manualSession.close()
        except Exception as exc:
            logger.error(f"PowerPage manual session close failed: {exc}")
        self._manualSession = None
        self._applyDisconnectedState()
        self._appendLog("设备已断开")

    def _isBluetoothMode(self) -> bool:
        return self.connectionTypeCombo.currentText().strip() == "蓝牙"

    def _onConnectionTypeChanged(self, text: str) -> None:
        isBluetooth = text.strip() == "蓝牙"
        self.portLabel.setVisible(not isBluetooth)
        self.portCombo.setVisible(not isBluetooth)
        self.bluetoothLabel.setVisible(isBluetooth)
        self.bluetoothCombo.setVisible(isBluetooth)

    def _startBluetoothDiscovery(self) -> None:
        if QBluetoothDeviceDiscoveryAgent is None:
            return
        try:
            if self._bluetoothDiscoveryAgent:
                self._bluetoothDiscoveryAgent.stop()
                self._bluetoothDiscoveryAgent.deleteLater()
            self._bluetoothDiscoveryAgent = QBluetoothDeviceDiscoveryAgent(self)
            self._bluetoothDiscoveryAgent.deviceDiscovered.connect(self._onBluetoothDeviceDiscovered)
            self._bluetoothDiscoveryAgent.start()
        except Exception as exc:
            self._appendLog(f"错误: 蓝牙扫描启动失败: {exc}")

    def _onBluetoothDeviceDiscovered(self, deviceInfo) -> None:
        try:
            name = deviceInfo.name().strip() or deviceInfo.address().toString()
            address = deviceInfo.address().toString()
        except Exception:
            return
        self._addBluetoothTarget(name, address)

    def _addBluetoothTarget(self, name: str, address: str) -> None:
        label = f"{name} ({address})" if name != address else address
        if label in self._bluetoothDevices:
            return
        self._bluetoothDevices[label] = address
        existing = [self.bluetoothCombo.itemText(i) for i in range(self.bluetoothCombo.count())]
        if label not in existing:
            self.bluetoothCombo.addItem(label)

    def onDeviceConnected(self, session) -> None:
        self.attachSessionRequested.emit(session)
        self.stateBadge.setText('在线')
        self.stateBadge.setProperty("onlineState", "online")
        self.connectButton.setText('断开')
        self._appendLog(f"已连接: {getattr(session.cfg, 'port', '未知')}")
        showMessage(
            self,
            '设备已连接',
            '电源设备会话已连接。',
            level="success",
        )
        if self.autoPollSwitch.isChecked():
            self.startPollingRequested.emit(POWER_POLL_INTERVAL_MS)
        else:
            self.readStatusRequested.emit()

    def closeEvent(self, event) -> None:
        self.shutdown()
        super().closeEvent(event)

    def shutdown(self) -> None:
        if self._shutdownDone:
            return

        self._shutdownDone = True
        self._plotRefreshTimer.stop()
        self._writePollRestartTimer.stop()

        try:
            if self._manualSession:
                self._manualSession.close()
        except Exception as exc:
            logger.error(f"PowerPage manual session shutdown failed: {exc}")
        self._manualSession = None

        try:
            if self._clientThread.isRunning():
                QMetaObject.invokeMethod(
                    self._client, "shutdown", Qt.BlockingQueuedConnection
                )
        except Exception as exc:
            logger.error(f"PowerPage client shutdown failed: {exc}")

        if self._clientThread.isRunning():
            self._clientThread.quit()
            if not self._clientThread.wait(3000):
                logger.error("PowerPage client thread did not exit within 3000 ms")

    def suspendForDaplink(self) -> None:
        self._appendLog("DAPLink 操作开始，已暂停主机轮询。")
        self.stopPollingRequested.emit()

    def resumeAfterDaplink(self) -> None:
        if self._shutdownDone:
            return
        if self.autoPollSwitch.isChecked() and self._client.is_connected:
            self.startPollingRequested.emit(POWER_POLL_INTERVAL_MS)
            self._appendLog("DAPLink 操作结束，已恢复主机轮询。")

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

    def _applyOutputLimits(self) -> None:
        if not self._client.is_connected:
            self._appendLog("错误: 串口会话未连接")
            return
        if self._writeInFlight:
            self._appendLog("写入进行中，请等待当前操作完成")
            return
        voltageMv = int(
            round(float(self.writeParams["set_voltage"].text() or "0") * 1000)
        )
        currentMa = int(
            round(float(self.writeParams["set_current"].text() or "0") * 1000)
        )
        enabled = (
            self._stagedOutputEnabled
            if self._stagedOutputEnabled is not None
            else self.outputSwitch.isChecked()
        )
        self._setWriteControlsEnabled(False)
        self._writePollingRestartPending = True
        self.outputLimitsRequested.emit(voltageMv, currentMa, enabled)

    def _applyProtectionValues(self) -> None:
        if not self._client.is_connected:
            self._appendLog("错误: 串口会话未连接")
            return
        if self._writeInFlight:
            self._appendLog("写入进行中，请等待当前操作完成")
            return
        ovpMv = int(round(float(self.writeParams["ovp"].text() or "0") * 1000))
        ocpMa = int(round(float(self.writeParams["ocp"].text() or "0") * 1000))
        otpMc = int(round(float(self.writeParams["otp"].text() or "0") * 1000))
        fanValue = int(float(self.writeParams["fan_set"].text() or "0"))
        self._setWriteControlsEnabled(False)
        self._writePollingRestartPending = True
        self.protectionValuesRequested.emit(ovpMv, ocpMa, otpMc, fanValue)

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

    def _onConnectionChanged(self, connected: bool) -> None:
        self.stateBadge.setText('在线' if connected else '离线')
        self.stateBadge.setProperty("onlineState", "online" if connected else "offline")
        self.connectButton.setText('断开' if connected else '连接')
        self._refreshStateBadgeStyle()
        if not connected:
            self._closeManualSessionSilently()
            self._applyDisconnectedState()

    def _updateStatusView(self, status: PowerStatus) -> None:
        previous_status = self._lastStatus
        self._lastStatus = status

        self.metricCards["vin"].setMetric(
            _MetricValue('输入电压', f"{status.vin_v:.3f}", "V"),
            f"原始采样有效 | 输入功率={status.pin_w:.2f} W",
        )
        self.metricCards["iin"].setMetric(
            _MetricValue('输入电流', f"{status.iin_a:.3f}", "A"),
            f"效率计算基准 | CC/CV={status.mode_name}",
        )
        self.metricCards["pin"].setMetric(
            _MetricValue('输入功率', f"{status.pin_w:.3f}", "W"),
            f"故障掩码 0x{status.fault_state:04X}",
        )
        self.metricCards["vout"].setMetric(
            _MetricValue('输出电压', f"{status.vout_v:.3f}", "V"),
            f"过压阈值={status.ovp_set_value_v:.3f} V",
        )
        self.metricCards["iout"].setMetric(
            _MetricValue('输出电流', f"{status.iout_a:.3f}", "A"),
            f"过流阈值={status.ocp_set_value_a:.3f} A",
        )
        self.metricCards["pout"].setMetric(
            _MetricValue('输出功率', f"{status.pout_w:.3f}", "W"),
            f"效率={status.efficiency:.2f} %",
        )

        self.readParams["core_temp"].setDisplayValue(f"{status.core_temp_c:.3f}")
        self.readParams["board_temp"].setDisplayValue(f"{status.board_temp_c:.3f}")
        self.readParams["mode"].setDisplayValue(status.mode_name)
        self.readParams["topology"].setDisplayValue(status.topology_name)
        self.readParams["state_flag"].setDisplayValue(status.state_flag_name)
        self.readParams["fault"].setDisplayValue(
            pretty_faults(status.fault_state) or '无'
        )
        self.readParams["fan_speed"].setDisplayValue(str(status.fan_speed))

        self.writeParams["set_voltage"].setDisplayValue(
            f"{status.set_voltage_limit_mv / 1000.0:.3f}"
        )
        self.writeParams["set_current"].setDisplayValue(
            f"{status.set_current_limit_ma / 1000.0:.3f}"
        )
        self.writeParams["ovp"].setDisplayValue(f"{status.ovp_set_value_v:.3f}")
        self.writeParams["ocp"].setDisplayValue(f"{status.ocp_set_value_a:.3f}")
        self.writeParams["otp"].setDisplayValue(f"{status.otp_set_value_c:.3f}")
        self.writeParams["fan_set"].setDisplayValue(str(status.fan_set_value))

        switch_value = status.power_enabled
        if self._stagedOutputEnabled is not None:
            if self._stagedOutputEnabled == status.power_enabled:
                self._stagedOutputEnabled = None
            else:
                switch_value = self._stagedOutputEnabled

        self.outputSwitch.blockSignals(True)
        self.outputSwitch.setChecked(switch_value)
        self.outputSwitch.blockSignals(False)

        if (
            previous_status is None
            or previous_status.power_state != status.power_state
            or previous_status.state_machine_flag_bits != status.state_machine_flag_bits
            or previous_status.fault_state != status.fault_state
        ):
            self._appendLog(
                "状态 "
                f"输出={'开启' if status.power_enabled else '关闭'} "
                f"状态机={status.state_flag_name} "
                f"拓扑={status.topology_name} "
                f"故障={pretty_faults(status.fault_state) or '无'} "
                f"输出电压={status.vout_v:.3f}V "
                f"设定={status.set_voltage_limit_mv / 1000.0:.3f}V/{status.set_current_limit_ma / 1000.0:.3f}A"
            )

        self._appendHistory(status)
        if (
            self.logLevelCombo.currentData() == "verbose"
            and time.monotonic() - self._lastVerboseLogTs >= 2.0
        ):
            self._lastVerboseLogTs = time.monotonic()
            self._appendLog(self._client.pretty_print_status(status))

    def _appendHistory(self, status: PowerStatus) -> None:
        index = self._history["t"][-1] + 1 if self._history["t"] else 0
        self._history["t"].append(index)
        self._history["vin"].append(status.vin_v)
        self._history["vout"].append(status.vout_v)
        self._history["iin"].append(status.iin_a)
        self._history["iout"].append(status.iout_a)
        self._historyDirty = True
        if not self._plotRefreshTimer.isActive():
            self._plotRefreshTimer.start()

    def _flushPlotUpdate(self) -> None:
        if not self._historyDirty:
            self._plotRefreshTimer.stop()
            return
        self._historyDirty = False
        self.plotCard.updateSeries(
            tuple(self._history["t"]),
            tuple(self._history["vin"]),
            tuple(self._history["vout"]),
            tuple(self._history["iin"]),
            tuple(self._history["iout"]),
        )

    def _diagnoseDebugSnapshot(self, snapshot: DebugSnapshot) -> str:
        if snapshot.output_voltage_raw >= 4090:
            return "调试判断: type27 接近 4095，请优先检查 MCU ADC 或前端电路。"
        if (
            snapshot.ovp_set_value_mv is not None
            and snapshot.ovp_set_value_mv == DEFAULT_OVP_SET_VALUE_MV
            and abs(snapshot.output_voltage_mv - snapshot.ovp_set_value_mv) <= 5
        ):
            return "调试判断: type32=44000 与 type12 重叠，主机字段映射可能有误。"
        if snapshot.loop_current_reference_ma is not None:
            return "调试判断: 已收到控制环调试量；带载时重点看 type41/type42 是否跟随，以及 type43 是否顶到设定电压。"
        return "调试判断: type27 数值合理；如果界面仍异常，请检查主机解析和绑定。"

    def _applyDisconnectedState(self) -> None:
        self._stagedOutputEnabled = None
        self._writePollingRestartPending = False
        self._setWriteControlsEnabled(True)
        self._writePollRestartTimer.stop()
        self.stateBadge.setText('离线')
        self.stateBadge.setProperty("onlineState", "offline")
        if hasattr(self, "connectButton"):
            self.connectButton.setText('连接')
        self._refreshStateBadgeStyle()
        self.outputSwitch.blockSignals(True)
        self.outputSwitch.setChecked(False)
        self.outputSwitch.blockSignals(False)
        self.writeParams["ovp"].setDisplayValue(DEFAULT_OVP_SET_VALUE_TEXT)

    def _closeManualSessionSilently(self) -> None:
        session = self._manualSession
        self._manualSession = None
        if session is None:
            return
        try:
            session.set_event_receiver(None)
            session.close()
        except Exception as exc:
            logger.error(f"PowerPage serial cleanup failed: {exc}")

    def _appendLog(self, text: str) -> None:
        if not (
            text.startswith("REQ ") or text.startswith("RX ") or text.startswith("TX ")
        ):
            logger.info(text)
        ts = time.strftime("%H:%M:%S")
        self.logEdit.append(f"[{ts}] {text}")

    def _onClientError(self, message: str) -> None:
        self._appendLog(f"错误: {message}")
        self._setWriteControlsEnabled(True)
        showMessage(self, '通信错误', message, level="error")
        if self._writePollingRestartPending:
            self._scheduleAutoPollingRestartAfterWrite()

    def _disconnectAfterWriteFailures(self) -> None:
        if not self._client.is_connected and self._manualSession is None:
            return
        self._appendLog("连续写入失败 3 次，已断开串口")
        showMessage(
            self,
            '串口已断开',
            '连续写入失败 3 次，已关闭当前串口连接。',
            level="error",
        )
        self._disconnectManualSession()

    def _handleDebugSnapshotReady(self, snapshot: DebugSnapshot) -> None:
        self._appendLog(self._client.pretty_print_debug_snapshot(snapshot))
        self._appendLog(self._diagnoseDebugSnapshot(snapshot))

    def _onOutputLimitsWritten(self) -> None:
        self._setWriteControlsEnabled(True)
        showMessage(
            self,
            '输出参数已更新',
            '电压、电流和输出状态已写入。',
            level="success",
        )
        self._scheduleAutoPollingRestartAfterWrite()

    def _onProtectionValuesWritten(self) -> None:
        self._setWriteControlsEnabled(True)
        showMessage(
            self,
            '保护参数已更新',
            'OVP/OCP/OTP/风扇参数已写入。',
            level="success",
        )
        self._scheduleAutoPollingRestartAfterWrite()

    def _onPowerStateWritten(self, enabled: bool) -> None:
        self._setWriteControlsEnabled(True)
        if self._stagedOutputEnabled == enabled:
            self._stagedOutputEnabled = None
        self._appendLog(f"输出已设置为{'开启' if enabled else '关闭'}")
        self._scheduleAutoPollingRestartAfterWrite()

    def _setWriteControlsEnabled(self, enabled: bool) -> None:
        self._writeInFlight = not enabled
        if hasattr(self, "applySetButton"):
            self.applySetButton.setEnabled(enabled)
        if hasattr(self, "applyProtectButton"):
            self.applyProtectButton.setEnabled(enabled)
        if hasattr(self, "outputSwitch"):
            self.outputSwitch.setEnabled(enabled)

    def _scheduleAutoPollingRestartAfterWrite(self) -> None:
        self._writePollingRestartPending = False
        # Debounce clustered write/error callbacks so polling restart is requested once.
        self._writePollRestartTimer.stop()
        self._writePollRestartTimer.start(WRITE_POLL_RESTART_DELAY_MS)

    def _restartAutoPollingAfterWrite(self) -> None:
        if self._shutdownDone:
            return
        if not self.autoPollSwitch.isChecked():
            return
        if not self._client.is_connected:
            return
        self.startPollingRequested.emit(POWER_POLL_INTERVAL_MS)
        self._appendLog("写入后已请求重启主机轮询")

    def _applyTexts(self) -> None:
        self.titleLabel.setText('电源面板')
        self.connectionTypeLabel.setText('连接方式')
        self.portLabel.setText('串口')
        self.bluetoothLabel.setText('蓝牙')
        self.refreshTargetButton.setText('刷新列表')
        self.connectButton.setText('断开' if self._client.is_connected else '连接')
        self.stateCaptionLabel.setText('状态')
        self.autoPollSwitch.setOnText('自动轮询')
        self.autoPollSwitch.setOffText('自动轮询')
        self.refreshButton.setText('立即刷新')
        self.debugButton.setText('调试快照')

        metricTitles = {
            "vin": "Input Voltage",
            "iin": "Input Current",
            "pin": "Input Power",
            "vout": "Output Voltage",
            "iout": "Output Current",
            "pout": "Output Power",
        }
        for key, text in metricTitles.items():
            self.metricCards[key].titleLabel.setText(POWER_TEXT.get(text, text))

        self.readCardTitle.setText('实时只读参数')
        self.writeCardTitle.setText('输出设定与保护阈值')
        for row in list(self.readParams.values()) + list(self.writeParams.values()):
            row.applyTexts()

        self.outputSwitch.setOnText('输出开启')
        self.outputSwitch.setOffText('输出关闭')
        self.applySetButton.setText('应用输出参数')
        self.applyProtectButton.setText('应用保护参数')

        self.logCardTitle.setText('协议 / 状态日志')
        currentLevel = self.logLevelCombo.currentData()
        self.logLevelCombo.blockSignals(True)
        self.logLevelCombo.clear()
        self.logLevelCombo.addItem('普通', userData="normal")
        self.logLevelCombo.addItem('详细', userData="verbose")
        self.logLevelCombo.setCurrentIndex(1 if currentLevel == "verbose" else 0)
        self.logLevelCombo.blockSignals(False)
        self.clearLogButton.setText('清空')

        self.plotCard.applyTexts()
        self._onConnectionTypeChanged(self.connectionTypeCombo.currentText())
        self._applyDisconnectedState() if not self._client.is_connected else None

    def _onThemeChanged(self, *_):
        QTimer.singleShot(0, self._refreshThemeBundle)

    def _refreshThemeBundle(self) -> None:
        StyleSheet.POWER_PAGE.apply(self)
        self._refreshStateBadgeStyle()
        self.plotCard.refreshTheme()

    def _refreshStateBadgeStyle(self) -> None:
        online = self.stateBadge.property("onlineState") == "online"
        if online:
            background = "rgba(34, 197, 94, 0.22)"
            foreground = "#22C55E" if isDarkTheme() else "#166534"
            border = "rgba(34, 197, 94, 0.36)"
        else:
            background = "rgba(239, 68, 68, 0.20)"
            foreground = "#F87171" if isDarkTheme() else "#B91C1C"
            border = "rgba(239, 68, 68, 0.34)"

        self.stateBadge.setStyleSheet(f"""
            background: {background};
            color: {foreground};
            border: 1px solid {border};
            border-radius: 14px;
            padding: 0 10px;
            font-weight: 700;
            """)
