# -*- coding: utf-8 -*-
from __future__ import annotations

import collections
import time
from dataclasses import dataclass
from pathlib import Path

import pyqtgraph as pg
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

from Config import SettingMangerInstance, cfg, logger
from App.Core import DeviceScanner, StyleSheet, showMessage
from App.Core import DebugSnapshot, F4CPPowerClient, PowerStatus, pretty_faults

DEFAULT_OVP_SET_VALUE_MV = 44000
DEFAULT_OVP_SET_VALUE_TEXT = f"{DEFAULT_OVP_SET_VALUE_MV / 1000.0:.3f}"
PLOT_Y_MIN = -10
PLOT_Y_MAX = 60


def _readPortIdentity() -> tuple[int, int]:
    try:
        return int(SettingMangerInstance.get("port", "vid")), int(
            SettingMangerInstance.get("port", "pid")
        )
    except Exception as exc:
        logger.error(f"Failed to load VID/PID from settings: {exc}")
        return -1, -1


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
        self.nameLabel.setText(self.tr(self._name))
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

        self.plotWidget = pg.PlotWidget(self)
        self.plotWidget.setObjectName("trendPlotWidget")
        self.plotWidget.setFrameShape(QFrame.NoFrame)
        self.plotWidget.setStyleSheet("background: transparent; border: none;")
        self.plotWidget.setMouseEnabled(x=True, y=False)
        self.plotWidget.showGrid(x=True, y=True, alpha=0.16)
        self.plotWidget.setAntialiasing(True)
        self.plotWidget.setMenuEnabled(False)
        self.plotWidget.setMinimumHeight(360)
        self.plotWidget.getPlotItem().hideButtons()
        self.plotWidget.getViewBox().setMouseEnabled(x=True, y=False)
        self.plotWidget.getViewBox().setMenuEnabled(False)
        self.plotWidget.getViewBox().setLimits(
            yMin=PLOT_Y_MIN,
            yMax=PLOT_Y_MAX,
            minYRange=PLOT_Y_MAX - PLOT_Y_MIN,
            maxYRange=PLOT_Y_MAX - PLOT_Y_MIN,
        )
        self.plotWidget.setYRange(PLOT_Y_MIN, PLOT_Y_MAX, padding=0)
        self.legend = self.plotWidget.addLegend(offset=(12, 12))

        self.voltageInCurve = self.plotWidget.plot(name="VIN", pen=pg.mkPen(width=2))
        self.voltageOutCurve = self.plotWidget.plot(name="VOUT", pen=pg.mkPen(width=2))
        self.currentInCurve = self.plotWidget.plot(
            name="IIN", pen=pg.mkPen(width=2, style=Qt.DashLine)
        )
        self.currentOutCurve = self.plotWidget.plot(
            name="IOUT", pen=pg.mkPen(width=2, style=Qt.DotLine)
        )

        self.voltageInCurve.setClipToView(True)
        self.voltageOutCurve.setClipToView(True)
        self.currentInCurve.setClipToView(True)
        self.currentOutCurve.setClipToView(True)

        plotPanelLayout = QVBoxLayout(self.plotPanel)
        plotPanelLayout.setContentsMargins(14, 14, 14, 14)
        plotPanelLayout.setSpacing(0)
        plotPanelLayout.addWidget(self.plotWidget)

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

    def applyTexts(self) -> None:
        self.titleLabel.setText(self.tr("Voltage / Current Trend"))
        self.tipLabel.setText(self.tr("Y range fixed: -10 to 60; drag or zoom horizontally"))
        self.saveButton.setText(self.tr("Save Image"))

    def saveImage(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            self.tr("Select save folder"),
            str(Path.home()),
        )
        if not folder:
            return

        path = Path(folder) / f"power-trend-{time.strftime('%Y%m%d-%H%M%S')}.png"
        if not self.plotWidget.grab().save(str(path), "PNG"):
            showMessage(
                self,
                self.tr("Action failed"),
                self.tr("Failed to save chart image."),
                level="error",
            )
            return

        showMessage(
            self,
            self.tr("Chart saved"),
            self.tr("Saved to {path}").format(path=str(path)),
            level="success",
        )

    def refreshTheme(self) -> None:
        dark = isDarkTheme()
        cardBorder = "rgba(255,255,255,0.08)" if dark else "rgba(0,0,0,0.08)"
        panelBackground = (
            "rgba(15, 23, 42, 0.72)" if dark else "rgba(248, 250, 252, 0.98)"
        )
        panelBorder = "rgba(255,255,255,0.10)" if dark else "rgba(15,23,42,0.08)"
        axis = "#DCE3EA" if dark else "#334155"
        titleColor = "#F5F7FA" if dark else "#111827"
        tipColor = "#9AA4B2" if dark else "#6B7280"
        legendBackground = (
            QColor(9, 14, 24, 188) if dark else QColor(255, 255, 255, 232)
        )
        legendBorder = QColor(255, 255, 255, 28) if dark else QColor(15, 23, 42, 22)
        borderPenColor = QColor(255, 255, 255, 24) if dark else QColor(15, 23, 42, 24)

        self.setStyleSheet(f"""
            #trendPlotCard {{
                border: 1px solid {cardBorder};
                border-radius: 18px;
            }}
            #trendPlotPanel {{
                background: {panelBackground};
                border: 1px solid {panelBorder};
                border-radius: 14px;
            }}
            """)
        self.titleLabel.setStyleSheet(f"color: {titleColor};")
        self.tipLabel.setStyleSheet(f"color: {tipColor};")

        self.plotWidget.setBackground((0, 0, 0, 0))
        plotItem = self.plotWidget.getPlotItem()
        plotItem.setTitle("")
        plotItem.getAxis("left").setTextPen(axis)
        plotItem.getAxis("bottom").setTextPen(axis)
        plotItem.getAxis("left").setPen(pg.mkPen(axis))
        plotItem.getAxis("bottom").setPen(pg.mkPen(axis))
        plotItem.getAxis("left").setLabel(self.tr("Voltage / Current"), color=axis, units="V / A")
        plotItem.getAxis("bottom").setLabel(self.tr("Samples"), color=axis)
        self.plotWidget.setYRange(PLOT_Y_MIN, PLOT_Y_MAX, padding=0)
        plotItem.getViewBox().setBorder(pg.mkPen(borderPenColor))
        plotItem.showGrid(x=True, y=True, alpha=0.22 if dark else 0.18)

        for axisName in ("left", "bottom"):
            axisItem = plotItem.getAxis(axisName)
            axisItem.setTickPen(pg.mkPen(axis))
            axisItem.setStyle(tickTextOffset=10)

        self.voltageInCurve.setPen(pg.mkPen(QColor("#2F80ED"), width=2))
        self.voltageOutCurve.setPen(pg.mkPen(QColor("#27AE60"), width=2))
        self.currentInCurve.setPen(
            pg.mkPen(QColor("#F2994A"), width=2, style=Qt.DashLine)
        )
        self.currentOutCurve.setPen(
            pg.mkPen(QColor("#EB5757"), width=2, style=Qt.DotLine)
        )

        if self.legend is not None:
            self.legend.setBrush(legendBackground)
            self.legend.setPen(legendBorder)
            self.legend.setLabelTextColor(axis)
            self.legend.setLabelTextSize("9pt")
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
        if xValues:
            x_min = xValues[0]
            x_max = xValues[-1]
            if x_max <= x_min:
                x_max = x_min + 1
            self.plotWidget.setXRange(x_min, x_max, padding=0.02)
        self.plotWidget.setYRange(PLOT_Y_MIN, PLOT_Y_MAX, padding=0)


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

        vid, pid = _readPortIdentity()
        self._client = F4CPPowerClient()
        self._clientThread = QThread(self)
        self._client.moveToThread(self._clientThread)
        self._clientThread.finished.connect(self._client.deleteLater)
        self._clientThread.start()
        self._scanner = DeviceScanner(vid=vid, pid=pid, parent=self)
        self._lastStatus: PowerStatus | None = None
        self._lastVerboseLogTs = 0.0
        self._historyDirty = False
        self._plotRefreshTimer = QTimer(self)
        self._plotRefreshTimer.setInterval(200)
        self._plotRefreshTimer.timeout.connect(self._flushPlotUpdate)
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

        self._scanner.start()

    def _initSummaryCard(self) -> None:
        self.summaryCard = CardWidget(self.scrollWidget)
        self.summaryCard.setObjectName("powerSummaryCard")
        layout = QHBoxLayout(self.summaryCard)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        self.deviceLabel = StrongBodyLabel(self.summaryCard)
        self.stateBadge = PillPushButton(self.summaryCard)
        self.stateBadge.setProperty("statusBadge", True)
        self.stateBadge.setProperty("onlineState", "offline")
        self.stateBadge.setCheckable(False)
        self.stateBadge.setFixedHeight(30)
        self.stateBadge.setFixedWidth(84)

        self.autoPollSwitch = SwitchButton(self.summaryCard)
        self.autoPollSwitch.setChecked(False)

        self.refreshButton = PrimaryPushButton(FIF.SYNC, "", self.summaryCard)
        self.debugButton = PushButton(FIF.SEARCH, "", self.summaryCard)

        self.deviceCaptionLabel = BodyLabel(self.summaryCard)
        layout.addWidget(self.deviceCaptionLabel)
        layout.addWidget(self.deviceLabel)
        layout.addSpacing(18)
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
                "Core Temperature", "RO", "°C", False, self.readCard
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
        self._scanner.device_connected.connect(self.onDeviceConnected)
        self._scanner.device_disconnected.connect(self.onDeviceDisconnected)

        self._client.log.connect(self._appendLog)
        self._client.error.connect(self._onClientError)
        self._client.connectionChanged.connect(self._onConnectionChanged)
        self._client.statusUpdated.connect(self._updateStatusView)
        self._client.debugSnapshotReady.connect(self._handleDebugSnapshotReady)
        self._client.outputLimitsWritten.connect(self._onOutputLimitsWritten)
        self._client.protectionValuesWritten.connect(self._onProtectionValuesWritten)
        self._client.powerStateWritten.connect(self._onPowerStateWritten)

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

        self.refreshButton.clicked.connect(self._readStatusOnce)
        self.debugButton.clicked.connect(self._runDebugSnapshot)
        self.autoPollSwitch.checkedChanged.connect(self._onAutoPollChanged)
        self.outputSwitch.checkedChanged.connect(self._onOutputSwitchChanged)
        self.applySetButton.clicked.connect(self._applyOutputLimits)
        self.applyProtectButton.clicked.connect(self._applyProtectionValues)
        self.clearLogButton.clicked.connect(self.logEdit.clear)
        cfg.themeChanged.connect(self._onThemeChanged)

    def onDeviceConnected(self, session) -> None:
        self.attachSessionRequested.emit(session)
        self.stopPollingRequested.emit()
        self.deviceLabel.setText(session.cfg.port or self.tr("Unknown"))
        self.stateBadge.setText(self.tr("ONLINE"))
        self.stateBadge.setProperty("onlineState", "online")
        self._appendLog(f"Connected on {session.cfg.port}")
        self.autoPollSwitch.blockSignals(True)
        self.autoPollSwitch.setChecked(False)
        self.autoPollSwitch.blockSignals(False)
        showMessage(
            self,
            self.tr("Device Connected"),
            self.tr("Power device session attached."),
            level="success",
        )
        self._appendLog("Waiting for device REPORT frames")

    def onDeviceDisconnected(self) -> None:
        self.detachSessionRequested.emit()
        self._applyDisconnectedState()
        self._appendLog("Device disconnected")
        showMessage(
            self,
            self.tr("Device Disconnected"),
            self.tr("Power device session closed."),
            level="error",
        )

    def closeEvent(self, event) -> None:
        self.shutdown()
        super().closeEvent(event)

    def shutdown(self) -> None:
        if self._shutdownDone:
            return

        self._shutdownDone = True
        self._plotRefreshTimer.stop()

        try:
            self._scanner.stop()
        except Exception as exc:
            logger.error(f"PowerPage scanner shutdown failed: {exc}")

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

    def _readStatusOnce(self) -> None:
        if not self._client.is_connected:
            self._appendLog("ERR: Serial session is not connected")
            return
        self.readStatusRequested.emit()

    def _runDebugSnapshot(self) -> None:
        if not self._client.is_connected:
            self._appendLog("ERR: Serial session is not connected")
            return
        self.debugSnapshotRequested.emit()

    def _applyOutputLimits(self) -> None:
        if not self._client.is_connected:
            self._appendLog("ERR: Serial session is not connected")
            return
        voltageMv = int(
            round(float(self.writeParams["set_voltage"].text() or "0") * 1000)
        )
        currentMa = int(
            round(float(self.writeParams["set_current"].text() or "0") * 1000)
        )
        self.outputLimitsRequested.emit(voltageMv, currentMa, self.outputSwitch.isChecked())

    def _applyProtectionValues(self) -> None:
        if not self._client.is_connected:
            self._appendLog("ERR: Serial session is not connected")
            return
        ovpMv = int(round(float(self.writeParams["ovp"].text() or "0") * 1000))
        ocpMa = int(round(float(self.writeParams["ocp"].text() or "0") * 1000))
        otpMc = int(round(float(self.writeParams["otp"].text() or "0") * 1000))
        fanValue = int(float(self.writeParams["fan_set"].text() or "0"))
        self.protectionValuesRequested.emit(ovpMv, ocpMa, otpMc, fanValue)

    def _onAutoPollChanged(self, checked: bool) -> None:
        self.stopPollingRequested.emit()
        if checked:
            self.autoPollSwitch.blockSignals(True)
            self.autoPollSwitch.setChecked(False)
            self.autoPollSwitch.blockSignals(False)
            self._appendLog("Host polling is disabled; use REPORT or Refresh Now")
        else:
            self._appendLog("Host polling disabled")

    def _onOutputSwitchChanged(self, checked: bool) -> None:
        if not self._client.is_connected:
            return
        self._appendLog(f"Output switch staged as {'ON' if checked else 'OFF'}")

    def _onConnectionChanged(self, connected: bool) -> None:
        self.stateBadge.setText(self.tr("ONLINE") if connected else self.tr("OFFLINE"))
        self.stateBadge.setProperty("onlineState", "online" if connected else "offline")
        self._refreshStateBadgeStyle()
        if not connected:
            self._applyDisconnectedState()

    def _updateStatusView(self, status: PowerStatus) -> None:
        self._lastStatus = status

        self.metricCards["vin"].setMetric(
            _MetricValue(self.tr("Input Voltage"), f"{status.vin_v:.3f}", "V"),
            f"raw source active | pin={status.pin_w:.2f} W",
        )
        self.metricCards["iin"].setMetric(
            _MetricValue(self.tr("Input Current"), f"{status.iin_a:.3f}", "A"),
            f"efficiency basis | cc/cv={status.mode_name}",
        )
        self.metricCards["pin"].setMetric(
            _MetricValue(self.tr("Input Power"), f"{status.pin_w:.3f}", "W"),
            f"fault mask 0x{status.fault_state:04X}",
        )
        self.metricCards["vout"].setMetric(
            _MetricValue(self.tr("Output Voltage"), f"{status.vout_v:.3f}", "V"),
            f"ovp={status.ovp_set_value_v:.3f} V",
        )
        self.metricCards["iout"].setMetric(
            _MetricValue(self.tr("Output Current"), f"{status.iout_a:.3f}", "A"),
            f"ocp={status.ocp_set_value_a:.3f} A",
        )
        self.metricCards["pout"].setMetric(
            _MetricValue(self.tr("Output Power"), f"{status.pout_w:.3f}", "W"),
            f"efficiency={status.efficiency:.2f} %",
        )

        self.readParams["core_temp"].setDisplayValue(f"{status.core_temp_c:.3f}")
        self.readParams["board_temp"].setDisplayValue(f"{status.board_temp_c:.3f}")
        self.readParams["mode"].setDisplayValue(status.mode_name)
        self.readParams["topology"].setDisplayValue(status.topology_name)
        self.readParams["state_flag"].setDisplayValue(status.state_flag_name)
        self.readParams["fault"].setDisplayValue(
            pretty_faults(status.fault_state) or self.tr("None")
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

        self.outputSwitch.blockSignals(True)
        self.outputSwitch.setChecked(status.power_enabled)
        self.outputSwitch.blockSignals(False)

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
            return "DEBUG_JUDGEMENT: type27 is close to 4095, check MCU ADC/front-end first."
        if (
            snapshot.ovp_set_value_mv == DEFAULT_OVP_SET_VALUE_MV
            and abs(snapshot.output_voltage_mv - snapshot.ovp_set_value_mv) <= 5
        ):
            return "DEBUG_JUDGEMENT: type32=44000 overlaps type12, field mapping is likely wrong on host side."
        return "DEBUG_JUDGEMENT: type27 is reasonable, if UI is still wrong check host parsing/binding."

    def _applyDisconnectedState(self) -> None:
        self.deviceLabel.setText(self.tr("Disconnected"))
        self.stateBadge.setText(self.tr("OFFLINE"))
        self.stateBadge.setProperty("onlineState", "offline")
        self._refreshStateBadgeStyle()
        self.outputSwitch.blockSignals(True)
        self.outputSwitch.setChecked(False)
        self.outputSwitch.blockSignals(False)
        self.writeParams["ovp"].setDisplayValue(DEFAULT_OVP_SET_VALUE_TEXT)

    def _appendLog(self, text: str) -> None:
        if not (
            text.startswith("REQ ") or text.startswith("RX ") or text.startswith("TX ")
        ):
            logger.info(text)
        ts = time.strftime("%H:%M:%S")
        self.logEdit.append(f"[{ts}] {text}")

    def _onClientError(self, message: str) -> None:
        self._appendLog(f"ERR: {message}")
        showMessage(self, self.tr("Communication Error"), message, level="error")

    def _handleDebugSnapshotReady(self, snapshot: DebugSnapshot) -> None:
        self._appendLog(self._client.pretty_print_debug_snapshot(snapshot))
        self._appendLog(self._diagnoseDebugSnapshot(snapshot))

    def _onOutputLimitsWritten(self) -> None:
        showMessage(
            self,
            self.tr("Output Updated"),
            self.tr("Voltage/current/output state have been written."),
            level="success",
        )
        self._readStatusOnce()

    def _onProtectionValuesWritten(self) -> None:
        showMessage(
            self,
            self.tr("Protection Updated"),
            self.tr("OVP/OCP/OTP/Fan parameters have been written."),
            level="success",
        )
        self._readStatusOnce()

    def _onPowerStateWritten(self, enabled: bool) -> None:
        self._appendLog(f"Output set to {'ON' if enabled else 'OFF'}")

    def _applyTexts(self) -> None:
        self.titleLabel.setText(self.tr("Power Dashboard"))
        self.deviceCaptionLabel.setText(self.tr("Device"))
        self.stateCaptionLabel.setText(self.tr("State"))
        self.autoPollSwitch.setOnText(self.tr("Auto Poll"))
        self.autoPollSwitch.setOffText(self.tr("Auto Poll"))
        self.refreshButton.setText(self.tr("Refresh Now"))
        self.debugButton.setText(self.tr("Debug Snapshot"))

        metricTitles = {
            "vin": "Input Voltage",
            "iin": "Input Current",
            "pin": "Input Power",
            "vout": "Output Voltage",
            "iout": "Output Current",
            "pout": "Output Power",
        }
        for key, text in metricTitles.items():
            self.metricCards[key].titleLabel.setText(self.tr(text))

        self.readCardTitle.setText(self.tr("Live Read Parameters"))
        self.writeCardTitle.setText(self.tr("Output and Protection Settings"))
        for row in list(self.readParams.values()) + list(self.writeParams.values()):
            row.applyTexts()

        self.outputSwitch.setOnText(self.tr("Output ON"))
        self.outputSwitch.setOffText(self.tr("Output OFF"))
        self.applySetButton.setText(self.tr("Apply Output"))
        self.applyProtectButton.setText(self.tr("Apply Protect"))

        self.logCardTitle.setText(self.tr("Protocol / Status Log"))
        currentLevel = self.logLevelCombo.currentData()
        self.logLevelCombo.blockSignals(True)
        self.logLevelCombo.clear()
        self.logLevelCombo.addItem(self.tr("Normal"), userData="normal")
        self.logLevelCombo.addItem(self.tr("Verbose"), userData="verbose")
        self.logLevelCombo.setCurrentIndex(1 if currentLevel == "verbose" else 0)
        self.logLevelCombo.blockSignals(False)
        self.clearLogButton.setText(self.tr("Clear"))

        self.plotCard.applyTexts()
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
