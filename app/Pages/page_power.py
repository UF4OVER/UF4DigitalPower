# -*- coding: utf-8 -*-
from __future__ import annotations

import collections
import time
from dataclasses import dataclass

import pyqtgraph as pg
from PyQt5.QtCore import QEvent, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
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
from app.Core import DeviceScanner, StyleSheet, showMessage
from app.Core import DebugSnapshot, F4CPPowerClient, PowerStatus, pretty_faults


def _read_port_identity() -> tuple[int, int]:
    try:
        return int(SettingMangerInstance.get("port", "vid")), int(SettingMangerInstance.get("port", "pid"))
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

    def set_metric(self, metric: _MetricValue, extra: str = "") -> None:
        self.titleLabel.setText(metric.title)
        self.valueLabel.setText(metric.value)
        self.unitLabel.setText(metric.unit)
        self.extraLabel.setText(extra)


class ParameterRow(QWidget):
    NAME_COLUMN_WIDTH = 170
    VALUE_COLUMN_WIDTH = 118
    UNIT_COLUMN_WIDTH = 52

    def __init__(self, name: str, access: str, unit: str = "", editable: bool = False, parent=None):
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
        layout.addWidget(self.valueLabel if not editable else self.editor, 0, Qt.AlignRight)
        layout.addWidget(self.unitLabel, 0)
        layout.addStretch(1)

    def set_display_value(self, value: str) -> None:
        self.valueLabel.setText(value)
        if self._editable and not self.editor.hasFocus():
            self.editor.setText(value)

    def text(self) -> str:
        return self.editor.text().strip() if self._editable else self.valueLabel.text().strip()

    def retranslate_ui(self) -> None:
        self.nameLabel.setText(self.tr(self._name))
        if self._editable:
            self.editor.setPlaceholderText(self._unit or "value")


class TrendPlotCard(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("trendPlotCard")
        self.titleLabel = SubtitleLabel(self)
        self.tipLabel = CaptionLabel(self)

        self.plotWidget = pg.PlotWidget(self)
        self.plotWidget.setMouseEnabled(x=True, y=True)
        self.plotWidget.showGrid(x=True, y=True, alpha=0.16)
        self.plotWidget.addLegend(offset=(12, 12))
        self.plotWidget.setMenuEnabled(False)
        self.plotWidget.getViewBox().setDefaultPadding(0.05)
        self.plotWidget.setMinimumHeight(360)

        self.voltageInCurve = self.plotWidget.plot(name="VIN", pen=pg.mkPen(width=2))
        self.voltageOutCurve = self.plotWidget.plot(name="VOUT", pen=pg.mkPen(width=2))
        self.currentInCurve = self.plotWidget.plot(name="IIN", pen=pg.mkPen(width=2, style=Qt.DashLine))
        self.currentOutCurve = self.plotWidget.plot(name="IOUT", pen=pg.mkPen(width=2, style=Qt.DotLine))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.tipLabel)
        layout.addWidget(self.plotWidget)

        self.retranslate_ui()
        self.refresh_theme()

    def retranslate_ui(self) -> None:
        self.titleLabel.setText(self.tr("Voltage / Current Trend"))
        self.tipLabel.setText(self.tr("Wheel zoom, left drag pan, right drag zoom area"))

    def refresh_theme(self) -> None:
        dark = isDarkTheme()
        border = "rgba(255,255,255,0.08)" if dark else "rgba(0,0,0,0.08)"
        background = "rgba(255,255,255,0.05)" if dark else "rgba(255,255,255,0.88)"
        axis = "#DCE3EA" if dark else "#273142"
        border_pen_color = QColor(255, 255, 255, 20) if dark else QColor(0, 0, 0, 20)

        self.setStyleSheet(
            f"""
            #trendPlotCard {{
                background: {background};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            """
        )
        self.titleLabel.setStyleSheet(f"color: {'#F5F7FA' if dark else '#111827'};")
        self.tipLabel.setStyleSheet(f"color: {'#9AA4B2' if dark else '#6B7280'};")

        self.plotWidget.setBackground((0, 0, 0, 0))
        plot_item = self.plotWidget.getPlotItem()
        plot_item.getAxis("left").setTextPen(axis)
        plot_item.getAxis("bottom").setTextPen(axis)
        plot_item.getAxis("left").setPen(pg.mkPen(axis))
        plot_item.getAxis("bottom").setPen(pg.mkPen(axis))
        plot_item.getAxis("left").setLabel(self.tr("Scaled Value"), color=axis)
        plot_item.getAxis("bottom").setLabel(self.tr("Samples"), color=axis)
        plot_item.getViewBox().setBorder(pg.mkPen(border_pen_color))
        plot_item.showGrid(x=True, y=True, alpha=0.16)

        self.voltageInCurve.setPen(pg.mkPen(QColor("#2F80ED"), width=2))
        self.voltageOutCurve.setPen(pg.mkPen(QColor("#27AE60"), width=2))
        self.currentInCurve.setPen(pg.mkPen(QColor("#F2994A"), width=2, style=Qt.DashLine))
        self.currentOutCurve.setPen(pg.mkPen(QColor("#EB5757"), width=2, style=Qt.DotLine))

    def update_series(
        self,
        x_values: list[float],
        vin: list[float],
        vout: list[float],
        iin: list[float],
        iout: list[float],
    ) -> None:
        self.voltageInCurve.setData(x_values, vin)
        self.voltageOutCurve.setData(x_values, vout)
        self.currentInCurve.setData(x_values, iin)
        self.currentOutCurve.setData(x_values, iout)


class PowerPage(ScrollArea):
    attachSessionRequested = pyqtSignal(object)
    detachSessionRequested = pyqtSignal()
    readStatusRequested = pyqtSignal()
    debugSnapshotRequested = pyqtSignal()
    outputLimitsRequested = pyqtSignal(int, int)
    protectionValuesRequested = pyqtSignal(int, int, int, int)
    powerStateRequested = pyqtSignal(bool)
    startPollingRequested = pyqtSignal(int)
    stopPollingRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("PowerPage")

        vid, pid = _read_port_identity()
        self._client = F4CPPowerClient()
        self._clientThread = QThread(self)
        self._client.moveToThread(self._clientThread)
        self._clientThread.start()
        self._scanner = DeviceScanner(vid=vid, pid=pid, parent=self)
        self._last_status: PowerStatus | None = None
        self._last_verbose_log_ts = 0.0
        self._history_dirty = False
        self._plot_refresh_timer = QTimer(self)
        self._plot_refresh_timer.setInterval(200)
        self._plot_refresh_timer.timeout.connect(self._flush_plot_update)
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

        self._init_summary_card()
        self._init_metric_cards()
        self._init_parameter_cards()
        self._init_plot_card()
        self._init_log_card()

        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 0, 0, 0)

        self._bind_signals()
        self._apply_disconnected_state()
        StyleSheet.POWER_PAGE.apply(self)
        self._refresh_theme_bundle()
        self._retranslate_ui()

        self._scanner.start()

    def _init_summary_card(self) -> None:
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
        self.autoPollSwitch.setChecked(True)

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

    def _init_metric_cards(self) -> None:
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

    def _init_parameter_cards(self) -> None:
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
            "core_temp": ParameterRow("Core Temperature", "RO", "°C", False, self.readCard),
            "board_temp": ParameterRow("Board Temperature", "RO", "°C", False, self.readCard),
            "mode": ParameterRow("CC/CV Mode", "RO", "", False, self.readCard),
            "topology": ParameterRow("Topology", "RO", "", False, self.readCard),
            "state_flag": ParameterRow("State Machine", "RO", "", False, self.readCard),
            "fault": ParameterRow("Fault Flags", "RO", "", False, self.readCard),
            "fan_speed": ParameterRow("Fan Speed", "RO", "RPM", False, self.readCard),
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
            "set_voltage": ParameterRow("Set Voltage Limit", "RW", "V", True, self.writeCard),
            "set_current": ParameterRow("Set Current Limit", "RW", "A", True, self.writeCard),
            "ovp": ParameterRow("OVP Set Value", "RW", "V", True, self.writeCard),
            "ocp": ParameterRow("OCP Set Value", "RW", "A", True, self.writeCard),
            "otp": ParameterRow("OTP Set Value", "RW", "°C", True, self.writeCard),
            "fan_set": ParameterRow("Fan Set Value", "RW", "RPM", True, self.writeCard),
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

    def _init_plot_card(self) -> None:
        self.plotCard = TrendPlotCard(self.scrollWidget)
        self.rootLayout.addWidget(self.plotCard)

    def _init_log_card(self) -> None:
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

    def _bind_signals(self) -> None:
        self._scanner.device_connected.connect(self.on_device_connected)
        self._scanner.device_disconnected.connect(self.on_device_disconnected)

        self._client.log.connect(self._append_log)
        self._client.error.connect(self._on_client_error)
        self._client.connectionChanged.connect(self._on_connection_changed)
        self._client.statusUpdated.connect(self._update_status_view)
        self._client.debugSnapshotReady.connect(self._handle_debug_snapshot_ready)
        self._client.outputLimitsWritten.connect(self._on_output_limits_written)
        self._client.protectionValuesWritten.connect(self._on_protection_values_written)
        self._client.powerStateWritten.connect(self._on_power_state_written)

        self.attachSessionRequested.connect(self._client.attach_session)
        self.detachSessionRequested.connect(self._client.detach_session)
        self.readStatusRequested.connect(self._client.request_read_status)
        self.debugSnapshotRequested.connect(self._client.request_debug_snapshot)
        self.outputLimitsRequested.connect(self._client.request_set_output_limits)
        self.protectionValuesRequested.connect(self._client.request_set_protection_values)
        self.powerStateRequested.connect(self._client.request_set_power_state)
        self.startPollingRequested.connect(self._client.start_polling)
        self.stopPollingRequested.connect(self._client.stop_polling)

        self.refreshButton.clicked.connect(self._read_status_once)
        self.debugButton.clicked.connect(self._run_debug_snapshot)
        self.autoPollSwitch.checkedChanged.connect(self._on_auto_poll_changed)
        self.outputSwitch.checkedChanged.connect(self._on_output_switch_changed)
        self.applySetButton.clicked.connect(self._apply_output_limits)
        self.applyProtectButton.clicked.connect(self._apply_protection_values)
        self.clearLogButton.clicked.connect(self.logEdit.clear)
        cfg.themeChanged.connect(self._on_theme_changed)

    def on_device_connected(self, session) -> None:
        self.attachSessionRequested.emit(session)
        self.deviceLabel.setText(session.cfg.port or self.tr("Unknown"))
        self.stateBadge.setText(self.tr("ONLINE"))
        self.stateBadge.setProperty("onlineState", "online")
        self._append_log(f"Connected on {session.cfg.port}")
        if self.autoPollSwitch.isChecked():
            self.startPollingRequested.emit(500)
        showMessage(self, self.tr("Device Connected"), self.tr("Power device session attached."), level="success")
        self._read_status_once()

    def on_device_disconnected(self) -> None:
        self.detachSessionRequested.emit()
        self._apply_disconnected_state()
        self._append_log("Device disconnected")
        showMessage(self, self.tr("Device Disconnected"), self.tr("Power device session closed."), level="error")

    def closeEvent(self, event) -> None:
        self.stopPollingRequested.emit()
        self.detachSessionRequested.emit()
        self._scanner.stop()
        self._clientThread.quit()
        self._clientThread.wait(1500)
        super().closeEvent(event)

    def _read_status_once(self) -> None:
        if not self._client.is_connected:
            self._append_log("ERR: Serial session is not connected")
            return
        self.readStatusRequested.emit()

    def _run_debug_snapshot(self) -> None:
        if not self._client.is_connected:
            self._append_log("ERR: Serial session is not connected")
            return
        self.debugSnapshotRequested.emit()

    def _apply_output_limits(self) -> None:
        if not self._client.is_connected:
            self._append_log("ERR: Serial session is not connected")
            return
        voltage_mv = int(round(float(self.writeParams["set_voltage"].text() or "0") * 1000))
        current_ma = int(round(float(self.writeParams["set_current"].text() or "0") * 1000))
        self.outputLimitsRequested.emit(voltage_mv, current_ma)

    def _apply_protection_values(self) -> None:
        if not self._client.is_connected:
            self._append_log("ERR: Serial session is not connected")
            return
        ovp_mv = int(round(float(self.writeParams["ovp"].text() or "0") * 1000))
        ocp_ma = int(round(float(self.writeParams["ocp"].text() or "0") * 1000))
        otp_mc = int(round(float(self.writeParams["otp"].text() or "0") * 1000))
        fan_value = int(float(self.writeParams["fan_set"].text() or "0"))
        self.protectionValuesRequested.emit(ovp_mv, ocp_ma, otp_mc, fan_value)

    def _on_auto_poll_changed(self, checked: bool) -> None:
        if checked:
            self.startPollingRequested.emit(500)
            self._append_log("Auto polling enabled")
        else:
            self.stopPollingRequested.emit()
            self._append_log("Auto polling disabled")

    def _on_output_switch_changed(self, checked: bool) -> None:
        if not self._client.is_connected:
            return
        self.powerStateRequested.emit(checked)

    def _on_connection_changed(self, connected: bool) -> None:
        self.stateBadge.setText(self.tr("ONLINE") if connected else self.tr("OFFLINE"))
        self.stateBadge.setProperty("onlineState", "online" if connected else "offline")
        self._refresh_state_badge_style()
        if not connected:
            self._apply_disconnected_state()

    def _update_status_view(self, status: PowerStatus) -> None:
        self._last_status = status

        self.metricCards["vin"].set_metric(_MetricValue(self.tr("Input Voltage"), f"{status.vin_v:.3f}", "V"), f"raw source active | pin={status.pin_w:.2f} W")
        self.metricCards["iin"].set_metric(_MetricValue(self.tr("Input Current"), f"{status.iin_a:.3f}", "A"), f"efficiency basis | cc/cv={status.mode_name}")
        self.metricCards["pin"].set_metric(_MetricValue(self.tr("Input Power"), f"{status.pin_w:.3f}", "W"), f"fault mask 0x{status.fault_state:04X}")
        self.metricCards["vout"].set_metric(_MetricValue(self.tr("Output Voltage"), f"{status.vout_v:.3f}", "V"), f"ovp={status.ovp_set_value_v:.3f} V")
        self.metricCards["iout"].set_metric(_MetricValue(self.tr("Output Current"), f"{status.iout_a:.3f}", "A"), f"ocp={status.ocp_set_value_a:.3f} A")
        self.metricCards["pout"].set_metric(_MetricValue(self.tr("Output Power"), f"{status.pout_w:.3f}", "W"), f"efficiency={status.efficiency:.2f} %")

        self.readParams["core_temp"].set_display_value(f"{status.core_temp_c:.3f}")
        self.readParams["board_temp"].set_display_value(f"{status.board_temp_c:.3f}")
        self.readParams["mode"].set_display_value(status.mode_name)
        self.readParams["topology"].set_display_value(status.topology_name)
        self.readParams["state_flag"].set_display_value(status.state_flag_name)
        self.readParams["fault"].set_display_value(pretty_faults(status.fault_state) or self.tr("None"))
        self.readParams["fan_speed"].set_display_value(str(status.fan_speed))

        self.writeParams["set_voltage"].set_display_value(f"{status.set_voltage_limit_mv / 1000.0:.3f}")
        self.writeParams["set_current"].set_display_value(f"{status.set_current_limit_ma / 1000.0:.3f}")
        self.writeParams["ovp"].set_display_value(f"{status.ovp_set_value_v:.3f}")
        self.writeParams["ocp"].set_display_value(f"{status.ocp_set_value_a:.3f}")
        self.writeParams["otp"].set_display_value(f"{status.otp_set_value_c:.3f}")
        self.writeParams["fan_set"].set_display_value(str(status.fan_set_value))

        self.outputSwitch.blockSignals(True)
        self.outputSwitch.setChecked(status.power_enabled)
        self.outputSwitch.blockSignals(False)

        self._append_history(status)
        if self.logLevelCombo.currentData() == "verbose" and time.monotonic() - self._last_verbose_log_ts >= 2.0:
            self._last_verbose_log_ts = time.monotonic()
            self._append_log(self._client.pretty_print_status(status))

    def _append_history(self, status: PowerStatus) -> None:
        index = self._history["t"][-1] + 1 if self._history["t"] else 0
        self._history["t"].append(index)
        self._history["vin"].append(status.vin_v)
        self._history["vout"].append(status.vout_v)
        self._history["iin"].append(status.iin_a)
        self._history["iout"].append(status.iout_a)
        self._history_dirty = True
        if not self._plot_refresh_timer.isActive():
            self._plot_refresh_timer.start()

    def _flush_plot_update(self) -> None:
        if not self._history_dirty:
            self._plot_refresh_timer.stop()
            return
        self._history_dirty = False
        self.plotCard.update_series(
            tuple(self._history["t"]),
            tuple(self._history["vin"]),
            tuple(self._history["vout"]),
            tuple(self._history["iin"]),
            tuple(self._history["iout"]),
        )

    def _diagnose_debug_snapshot(self, snapshot: DebugSnapshot) -> str:
        if snapshot.output_voltage_raw >= 4090:
            return "DEBUG_JUDGEMENT: type27 is close to 4095, check MCU ADC/front-end first."
        if snapshot.ovp_set_value_mv == 33000 and abs(snapshot.output_voltage_mv - snapshot.ovp_set_value_mv) <= 5:
            return "DEBUG_JUDGEMENT: type32=33000 overlaps type12, field mapping is likely wrong on host side."
        return "DEBUG_JUDGEMENT: type27 is reasonable, if UI is still wrong check host parsing/binding."

    def _apply_disconnected_state(self) -> None:
        self.deviceLabel.setText(self.tr("Disconnected"))
        self.stateBadge.setText(self.tr("OFFLINE"))
        self.stateBadge.setProperty("onlineState", "offline")
        self._refresh_state_badge_style()
        self.outputSwitch.blockSignals(True)
        self.outputSwitch.setChecked(False)
        self.outputSwitch.blockSignals(False)

    def _append_log(self, text: str) -> None:
        if not (text.startswith("REQ ") or text.startswith("RX ") or text.startswith("TX ")):
            logger.info(text)
        ts = time.strftime("%H:%M:%S")
        self.logEdit.append(f"[{ts}] {text}")

    def _on_client_error(self, message: str) -> None:
        self._append_log(f"ERR: {message}")
        showMessage(self, self.tr("Communication Error"), message, level="error")

    def _handle_debug_snapshot_ready(self, snapshot: DebugSnapshot) -> None:
        self._append_log(self._client.pretty_print_debug_snapshot(snapshot))
        self._append_log(self._diagnose_debug_snapshot(snapshot))

    def _on_output_limits_written(self) -> None:
        showMessage(self, self.tr("Output Updated"), self.tr("Voltage/current limits have been written."), level="success")
        self._read_status_once()

    def _on_protection_values_written(self) -> None:
        showMessage(self, self.tr("Protection Updated"), self.tr("OVP/OCP/OTP/Fan parameters have been written."), level="success")
        self._read_status_once()

    def _on_power_state_written(self, enabled: bool) -> None:
        self._append_log(f"Output set to {'ON' if enabled else 'OFF'}")

    def _retranslate_ui(self) -> None:
        self.titleLabel.setText(self.tr("Power Dashboard"))
        self.deviceCaptionLabel.setText(self.tr("Device"))
        self.stateCaptionLabel.setText(self.tr("State"))
        self.autoPollSwitch.setOnText(self.tr("Auto Poll"))
        self.autoPollSwitch.setOffText(self.tr("Auto Poll"))
        self.refreshButton.setText(self.tr("Refresh Now"))
        self.debugButton.setText(self.tr("Debug Snapshot"))

        metric_titles = {
            "vin": "Input Voltage",
            "iin": "Input Current",
            "pin": "Input Power",
            "vout": "Output Voltage",
            "iout": "Output Current",
            "pout": "Output Power",
        }
        for key, text in metric_titles.items():
            self.metricCards[key].titleLabel.setText(self.tr(text))

        self.readCardTitle.setText(self.tr("Live Read Parameters"))
        self.writeCardTitle.setText(self.tr("Read / Write Parameters"))
        for row in list(self.readParams.values()) + list(self.writeParams.values()):
            row.retranslate_ui()

        self.outputSwitch.setOnText(self.tr("Output ON"))
        self.outputSwitch.setOffText(self.tr("Output OFF"))
        self.applySetButton.setText(self.tr("Apply Output"))
        self.applyProtectButton.setText(self.tr("Apply Protect"))

        self.logCardTitle.setText(self.tr("Protocol / Status Log"))
        current_level = self.logLevelCombo.currentData()
        self.logLevelCombo.blockSignals(True)
        self.logLevelCombo.clear()
        self.logLevelCombo.addItem(self.tr("Normal"), userData="normal")
        self.logLevelCombo.addItem(self.tr("Verbose"), userData="verbose")
        self.logLevelCombo.setCurrentIndex(1 if current_level == "verbose" else 0)
        self.logLevelCombo.blockSignals(False)
        self.clearLogButton.setText(self.tr("Clear"))

        self.plotCard.retranslate_ui()
        self._apply_disconnected_state() if not self._client.is_connected else None

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.LanguageChange:
            self._retranslate_ui()

    def _on_theme_changed(self, *_):
        QTimer.singleShot(0, self._refresh_theme_bundle)

    def _refresh_theme_bundle(self) -> None:
        StyleSheet.POWER_PAGE.apply(self)
        self._refresh_state_badge_style()
        self.plotCard.refresh_theme()

    def _refresh_state_badge_style(self) -> None:
        online = self.stateBadge.property("onlineState") == "online"
        if online:
            background = "rgba(34, 197, 94, 0.22)"
            foreground = "#22C55E" if isDarkTheme() else "#166534"
            border = "rgba(34, 197, 94, 0.36)"
        else:
            background = "rgba(239, 68, 68, 0.20)"
            foreground = "#F87171" if isDarkTheme() else "#B91C1C"
            border = "rgba(239, 68, 68, 0.34)"

        self.stateBadge.setStyleSheet(
            f"""
            background: {background};
            color: {foreground};
            border: 1px solid {border};
            border-radius: 14px;
            padding: 0 10px;
            font-weight: 700;
            """
        )
