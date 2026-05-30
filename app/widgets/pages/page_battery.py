# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/5/9
#  @FileName: page_battery.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------

from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt5.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    CaptionLabel,
    ComboBox,
    FluentIcon as FIF,
    PillPushButton,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    StrongBodyLabel,
    SubtitleLabel,
    TitleLabel,
    isDarkTheme,
    setFont,
    ProgressBar,
)

from app.manager import StyleSheet
from config import cfg


@dataclass(frozen=True)
class BatterySnapshot:
    cell_soc: tuple[float, float, float, float]
    cell_voltage: tuple[float, float, float, float]
    input_online: bool
    output_online: bool
    charge_state: str
    charge_current_a: float
    discharge_current_a: float
    pack_soc: float
    pack_voltage_v: float
    pack_current_a: float
    nominal_capacity_ah: float
    remaining_capacity_ah: float
    health_percent: float
    remaining_discharge_minutes: int
    charged_in_ah: float
    energy_in_wh: float
    energy_out_wh: float


@dataclass(frozen=True)
class CellState:
    index: int
    voltage: float
    soc: float
    soh: float
    capacity_mah: float
    temperature: float
    status: str


class WaterTankWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 70.0
        self._phase = 0.0
        self._status = "idle"
        self.setMinimumSize(92, 150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._onTimeout)
        self.timer.start(40)

    def setValue(self, value: float) -> None:
        self._value = max(0.0, min(100.0, value))
        self.update()

    def setStatus(self, status: str) -> None:
        self._status = status
        self.update()

    def refreshTheme(self) -> None:
        self.update()

    def _onTimeout(self) -> None:
        self._phase += 0.18
        if self._phase > math.pi * 2:
            self._phase = 0.0
        self.update()

    def _themeColor(self) -> QColor:
        color = getattr(cfg.themeColor, "value", None)
        return QColor(color) if isinstance(color, QColor) else QColor("#3B82F6")

    def _waterColor(self) -> QColor:
        status = self._status.lower()
        if status == "fault":
            return QColor(255, 90, 90)
        if self._value >= 70:
            return self._themeColor()
        if self._value >= 30:
            return QColor(255, 185, 70)
        return QColor(255, 95, 95)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)

        tank_rect = QRectF(18, 12, self.width() - 36, self.height() - 24)
        radius = 18

        tank_path = QPainterPath()
        tank_path.addRoundedRect(tank_rect, radius, radius)

        dark = isDarkTheme()
        bg_gradient = QLinearGradient(tank_rect.topLeft(), tank_rect.bottomLeft())
        if dark:
            bg_gradient.setColorAt(0, QColor(31, 41, 55))
            bg_gradient.setColorAt(1, QColor(15, 23, 42))
        else:
            bg_gradient.setColorAt(0, QColor(245, 247, 250))
            bg_gradient.setColorAt(1, QColor(228, 233, 240))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bg_gradient))
        painter.drawPath(tank_path)

        if self._value > 0.5:
            water_height = tank_rect.height() * self._value / 100.0
            water_top = tank_rect.bottom() - water_height
            wave_amp = min(4.0, max(0.0, water_height * 0.30))
            wave_len = tank_rect.width() / 1.2

            water_path = QPainterPath()
            water_path.moveTo(tank_rect.left(), tank_rect.bottom())
            water_path.lineTo(tank_rect.left(), water_top)

            x = tank_rect.left()
            while x <= tank_rect.right():
                y = water_top + math.sin((x / wave_len) * math.pi * 2 + self._phase) * wave_amp
                y = max(tank_rect.top(), min(y, tank_rect.bottom()))
                water_path.lineTo(x, y)
                x += 2

            water_path.lineTo(tank_rect.right(), tank_rect.bottom())
            water_path.closeSubpath()

            water_color = self._waterColor()
            water_gradient = QLinearGradient(tank_rect.topLeft(), tank_rect.bottomLeft())
            water_gradient.setColorAt(0.0, QColor(water_color.red(), water_color.green(), water_color.blue(), 210))
            water_gradient.setColorAt(1.0, QColor(water_color.red(), water_color.green(), water_color.blue(), 255))

            painter.save()
            painter.setClipPath(tank_path)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(water_gradient))
            painter.drawPath(water_path)
            painter.restore()

        highlight = QPainterPath()
        highlight.addRoundedRect(
            QRectF(tank_rect.left() + 8, tank_rect.top() + 8, tank_rect.width() * 0.22, tank_rect.height() - 16),
            8,
            8,
        )
        painter.setBrush(QColor(255, 255, 255, 70 if not dark else 36))
        painter.setPen(Qt.NoPen)
        painter.drawPath(highlight.intersected(tank_path))

        border_color = QColor(95, 108, 125) if not dark else QColor(148, 163, 184)
        painter.setPen(QPen(border_color, 1.6))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(tank_path)

        painter.setPen(QColor(35, 42, 52) if not dark else QColor(248, 250, 252))
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(tank_rect, Qt.AlignCenter, f"{self._value:.0f}%")


class BatteryCardWidget(CardWidget):
    """Battery page card with transparent state colors to avoid hover mask flicker."""

    def _normalBackgroundColor(self):
        return QColor(0, 0, 0, 0)

    def _hoverBackgroundColor(self):
        return QColor(0, 0, 0, 0)

    def _pressedBackgroundColor(self):
        return QColor(0, 0, 0, 0)


class BatteryCellCard(BatteryCardWidget):
    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.setObjectName(f"batteryCellCard{index}")
        self.setProperty("batteryCard", True)
        self.setProperty("cellCard", True)
        self.setBorderRadius(10)
        self._cell = CellState(index, 0.0, 0.0, 100.0, 0.0, 25.0, "idle")

        self.titleLabel = StrongBodyLabel(self)
        self.statusLabel = CaptionLabel(self)
        self.tank = WaterTankWidget(self)
        self.voltageLabel = BodyLabel(self)
        self.capacityLabel = CaptionLabel(self)
        self.tempLabel = CaptionLabel(self)
        self.sohLabel = CaptionLabel("SOH", self)
        self.sohTextLabel = CaptionLabel("健康度", self)
        self.sohBar = ProgressBar(self)
        self.sohBar.setRange(0, 100)

        setFont(self.titleLabel, 14, QFont.DemiBold)
        setFont(self.voltageLabel, 15, QFont.DemiBold)
        setFont(self.statusLabel, 12, QFont.DemiBold)

        self._initLayout()
        self.updateCell(self._cell)

    def _initLayout(self) -> None:
        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(14, 12, 14, 12)
        mainLayout.setSpacing(8)

        topLayout = QHBoxLayout()
        topLayout.setContentsMargins(0, 0, 0, 0)
        topLayout.addWidget(self.titleLabel)
        topLayout.addStretch(1)
        topLayout.addWidget(self.statusLabel)

        mainLayout.addLayout(topLayout)
        mainLayout.addWidget(self.tank, alignment=Qt.AlignCenter)
        mainLayout.addWidget(self.voltageLabel)
        mainLayout.addWidget(self.capacityLabel)
        mainLayout.addWidget(self.tempLabel)

        sohLayout = QHBoxLayout()
        sohLayout.setContentsMargins(0, 0, 0, 0)
        sohLayout.addWidget(self.sohLabel)
        sohLayout.addStretch(1)
        sohLayout.addWidget(self.sohTextLabel)
        mainLayout.addLayout(sohLayout)
        mainLayout.addWidget(self.sohBar)

    def applyTexts(self) -> None:
        self.updateCell(self._cell)

    def setCellValue(self, soc_percent: float, voltage_v: float) -> None:
        self.updateCell(
            CellState(
                index=self.index,
                voltage=voltage_v,
                soc=soc_percent,
                soh=self._cell.soh,
                capacity_mah=self._cell.capacity_mah,
                temperature=self._cell.temperature,
                status=self._cell.status,
            )
        )

    def updateCell(self, cell: CellState) -> None:
        self._cell = cell
        self.titleLabel.setText(f"电芯 {cell.index}")
        self.statusLabel.setText(self._statusText(cell.status))
        self.tank.setValue(cell.soc)
        self.tank.setStatus(cell.status)
        self.voltageLabel.setText(f"电压：{cell.voltage:.3f} V")
        self.capacityLabel.setText(f"容量：{cell.capacity_mah:.0f} mAh")
        self.tempLabel.setText(f"温度：{cell.temperature:.1f} ℃")
        self.sohBar.setValue(int(max(0.0, min(100.0, cell.soh))))
        self.refreshTheme()

    def refreshTheme(self) -> None:
        self.tank.refreshTheme()
        text = "#F5F7FA" if isDarkTheme() else "#111827"
        muted = "#A7B0BE" if isDarkTheme() else "#475569"
        self.titleLabel.setStyleSheet(f"color: {text};")
        self.voltageLabel.setStyleSheet(f"color: {text};")
        for label in (self.capacityLabel, self.tempLabel, self.sohLabel, self.sohTextLabel):
            label.setStyleSheet(f"color: {muted};")
        accent = self._themeColor().name()
        track = "rgba(255,255,255,0.12)" if isDarkTheme() else "rgba(15,23,42,0.10)"
        self.sohBar.setStyleSheet(f"""
            ProgressBar {{
                background: {track};
                border-radius: 4px;
            }}
            ProgressBar::chunk {{
                background: {accent};
                border-radius: 4px;
            }}
            """)
        self._refreshStatusColor()

    def _themeColor(self) -> QColor:
        color = getattr(cfg.themeColor, "value", None)
        return QColor(color) if isinstance(color, QColor) else QColor("#3B82F6")

    def _statusText(self, status: str) -> str:
        return {
            "fault": "故障",
            "charge": "充电",
            "charging": "充电",
            "discharge": "放电",
            "discharging": "放电",
            "balance": "均衡",
            "idle": "待机",
        }.get(status.lower(), status)

    def _refreshStatusColor(self) -> None:
        status = self._cell.status.lower()
        if status == "fault":
            color = "rgb(255, 70, 70)"
        elif status in ("charge", "charging"):
            color = self._themeColor().name()
        elif status in ("discharge", "discharging"):
            color = "rgb(0, 120, 215)"
        elif status == "balance":
            color = "rgb(180, 120, 0)"
        else:
            color = "#A7B0BE" if isDarkTheme() else "rgb(100, 100, 100)"
        self.statusLabel.setStyleSheet(f"color: {color}; font-weight: 600;")


class MetricTile(BatteryCardWidget):
    def __init__(self, title: str, icon: FIF, parent=None):
        super().__init__(parent)
        self.setProperty("batteryCard", True)
        self.setBorderRadius(10)
        self._titleText = title

        self.titleLabel = SubtitleLabel(self)
        self.valueLabel = TitleLabel("--", self)
        self.noteLabel = CaptionLabel("", self)

        self.titleLabel.setProperty("metricTileTitle", True)
        self.noteLabel.setWordWrap(True)
        setFont(self.valueLabel, 26, QFont.DemiBold)

        self.iconBadge = PillPushButton(icon, "", self)
        self.iconBadge.setCheckable(False)
        self.iconBadge.setEnabled(False)
        self.iconBadge.setFixedHeight(28)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addWidget(self.titleLabel)
        header.addStretch(1)
        header.addWidget(self.iconBadge)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addWidget(self.valueLabel)
        layout.addWidget(self.noteLabel)

        self.applyTexts()

    def applyTexts(self) -> None:
        self.titleLabel.setText(self._titleText)

    def setMetric(self, value_text: str, note_text: str = "") -> None:
        self.valueLabel.setText(value_text)
        self.noteLabel.setText(note_text)


class BatteryPage(ScrollArea):
    readBatteryRequested = pyqtSignal()
    connectionRequested = pyqtSignal(str)
    startPollingRequested = pyqtSignal(int)
    stopPollingRequested = pyqtSignal()

    POLL_INTERVAL_MS = 400

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BatteryPage")
        self._defaultSnapshot = BatterySnapshot(
            cell_soc=(0.0, 0.0, 0.0, 0.0),
            cell_voltage=(0.0, 0.0, 0.0, 0.0),
            input_online=False,
            output_online=False,
            charge_state="idle",
            charge_current_a=0.0,
            discharge_current_a=0.0,
            pack_soc=0.0,
            pack_voltage_v=0.0,
            pack_current_a=0.0,
            nominal_capacity_ah=0.0,
            remaining_capacity_ah=0.0,
            health_percent=0.0,
            remaining_discharge_minutes=0,
            charged_in_ah=0.0,
            energy_in_wh=0.0,
            energy_out_wh=0.0,
        )

        self.scrollWidget = QWidget(self)
        self.scrollWidget.setObjectName("batteryScrollWidget")
        self.rootLayout = QVBoxLayout(self.scrollWidget)
        self.rootLayout.setContentsMargins(24, 24, 24, 24)
        self.rootLayout.setSpacing(12)

        self.titleLabel = TitleLabel(self.scrollWidget)
        self.rootLayout.addWidget(self.titleLabel)

        self._initSummaryCard()
        self._initCellOverviewCard()
        self._initFlowCard()
        self._initMetricTiles()

        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.refreshButton.clicked.connect(self.readBatteryRequested.emit)
        self.connectButton.clicked.connect(self._onConnectionRequested)
        cfg.themeChanged.connect(self._onThemeChanged)

        self._applyTexts()
        self._applyDemoSnapshot()
        self._refreshStateStyles()
        StyleSheet.BATTERY_PAGE.apply(self)

    def _initSummaryCard(self) -> None:
        self.summaryCard = BatteryCardWidget(self.scrollWidget)
        self.summaryCard.setObjectName("batterySummaryCard")
        self.summaryCard.setProperty("batteryCard", True)
        self.summaryCard.setBorderRadius(10)
        layout = QHBoxLayout(self.summaryCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self.deviceCaptionLabel = BodyLabel(self.summaryCard)
        self.deviceLabel = StrongBodyLabel(self.summaryCard)
        self.connectionModeLabel = BodyLabel(self.summaryCard)
        self.connectionModeCombo = ComboBox(self.summaryCard)
        self.connectionModeCombo.setMinimumWidth(128)
        self.connectionModeCombo.addItems(["串口", "蓝牙", "USB", "网络"])
        self.connectButton = PrimaryPushButton(FIF.LINK, "", self.summaryCard)

        self.inputBadge = PillPushButton(self.summaryCard)
        self.inputBadge.setCheckable(False)
        self.inputBadge.setFixedHeight(28)

        self.outputBadge = PillPushButton(self.summaryCard)
        self.outputBadge.setCheckable(False)
        self.outputBadge.setFixedHeight(28)

        self.refreshButton = PushButton(FIF.SYNC, "", self.summaryCard)

        layout.addWidget(self.deviceCaptionLabel)
        layout.addWidget(self.deviceLabel)
        layout.addSpacing(12)
        layout.addWidget(self.connectionModeLabel)
        layout.addWidget(self.connectionModeCombo)
        layout.addWidget(self.connectButton)
        layout.addSpacing(8)
        layout.addWidget(self.inputBadge)
        layout.addWidget(self.outputBadge)
        layout.addStretch(1)
        layout.addWidget(self.refreshButton)

        self.rootLayout.addWidget(self.summaryCard)

    def _initCellOverviewCard(self) -> None:
        self.cellCard = BatteryCardWidget(self.scrollWidget)
        self.cellCard.setObjectName("batteryCellOverviewCard")
        self.cellCard.setProperty("batteryCard", True)
        self.cellCard.setBorderRadius(10)
        layout = QVBoxLayout(self.cellCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self.cellCardTitle = SubtitleLabel(self.cellCard)
        self.packSocLabel = TitleLabel("--", self.cellCard)
        self.packPowerLabel = CaptionLabel("--", self.cellCard)
        self.packHintLabel = CaptionLabel("--", self.cellCard)

        header.addWidget(self.cellCardTitle)
        header.addStretch(1)
        header.addWidget(self.packSocLabel)

        layout.addLayout(header)
        layout.addWidget(self.packPowerLabel)
        layout.addWidget(self.packHintLabel)

        self.cellGrid = QGridLayout()
        self.cellGrid.setHorizontalSpacing(10)
        self.cellGrid.setVerticalSpacing(10)
        self.cellCards: list[BatteryCellCard] = []
        for index in range(4):
            card = BatteryCellCard(index + 1, self.cellCard)
            self.cellCards.append(card)
            self.cellGrid.addWidget(card, 0, index)

        layout.addLayout(self.cellGrid)
        self.rootLayout.addWidget(self.cellCard)

    def _initFlowCard(self) -> None:
        self.flowCard = BatteryCardWidget(self.scrollWidget)
        self.flowCard.setObjectName("batteryFlowCard")
        self.flowCard.setProperty("batteryCard", True)
        self.flowCard.setBorderRadius(10)
        layout = QVBoxLayout(self.flowCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.flowTitleLabel = SubtitleLabel(self.flowCard)
        self.flowStateLabel = TitleLabel("--", self.flowCard)
        self.flowHintLabel = CaptionLabel("--", self.flowCard)
        self.flowCurrentLabel = StrongBodyLabel("--", self.flowCard)

        layout.addWidget(self.flowTitleLabel)
        layout.addWidget(self.flowStateLabel)
        layout.addWidget(self.flowHintLabel)
        layout.addWidget(self.flowCurrentLabel)

        self.rootLayout.addWidget(self.flowCard)

    def _initMetricTiles(self) -> None:
        self.metricGrid = QGridLayout()
        self.metricGrid.setHorizontalSpacing(10)
        self.metricGrid.setVerticalSpacing(10)

        self.capacityTile = MetricTile("剩余容量", FIF.SAVE, self.scrollWidget)
        self.healthTile = MetricTile("健康度", FIF.UPDATE, self.scrollWidget)
        self.remainingTile = MetricTile("剩余放电时间", FIF.SEARCH, self.scrollWidget)
        self.energyTile = MetricTile("累计充入", FIF.SYNC, self.scrollWidget)

        self.metricGrid.addWidget(self.capacityTile, 0, 0)
        self.metricGrid.addWidget(self.healthTile, 0, 1)
        self.metricGrid.addWidget(self.remainingTile, 1, 0)
        self.metricGrid.addWidget(self.energyTile, 1, 1)

        self.rootLayout.addLayout(self.metricGrid)
        self.rootLayout.addStretch(1)

    def _applyTexts(self) -> None:
        self.titleLabel.setText('电池组面板')
        self.deviceCaptionLabel.setText('电池组')
        self.deviceLabel.setText('4 串电池组')
        self.connectionModeLabel.setText('连接方式')
        self.connectButton.setText('连接')
        self.inputBadge.setText('输入: --')
        self.outputBadge.setText('输出: --')
        self.refreshButton.setText('立即刷新')

        self.cellCardTitle.setText('单体电芯总览')
        self.flowTitleLabel.setText('充放电状态')

        for card in self.cellCards:
            card.applyTexts()
        for tile in [
            self.capacityTile,
            self.healthTile,
            self.remainingTile,
            self.energyTile,
        ]:
            tile.applyTexts()

    def _applyDemoSnapshot(self) -> None:
        self.updateSnapshot(self._defaultSnapshot)

    # Public APIs for external modules to update battery page content.
    def setDeviceName(self, device_name: str) -> None:
        self.deviceLabel.setText(device_name.strip() if device_name else "--")

    def setConnectionModes(self, modes: list[str], current_mode: str | None = None) -> None:
        items = [item.strip() for item in modes if item and item.strip()]
        if not items:
            return

        self.connectionModeCombo.blockSignals(True)
        self.connectionModeCombo.clear()
        self.connectionModeCombo.addItems(items)
        self.connectionModeCombo.blockSignals(False)
        if current_mode:
            self.setConnectionMode(current_mode)
        else:
            self.connectionModeCombo.setCurrentIndex(0)

    def setConnectionMode(self, mode: str) -> None:
        text = (mode or "").strip()
        if not text:
            return
        index = self.connectionModeCombo.findText(text)
        if index >= 0:
            self.connectionModeCombo.setCurrentIndex(index)

    def setBatterySnapshot(self, snapshot: BatterySnapshot) -> None:
        self.updateSnapshot(snapshot)

    def resetContent(self) -> None:
        self.connectionModeCombo.setCurrentIndex(0)
        self._applyTexts()
        self._applyDemoSnapshot()
        self._refreshStateStyles()

    def updateSnapshot(self, snapshot: BatterySnapshot) -> None:
        soc_values = list(snapshot.cell_soc)[:4]
        volt_values = list(snapshot.cell_voltage)[:4]
        while len(soc_values) < 4:
            soc_values.append(0.0)
        while len(volt_values) < 4:
            volt_values.append(0.0)

        pack_soc = max(0.0, min(100.0, snapshot.pack_soc))
        state = (snapshot.charge_state or "idle").strip().lower()
        cell_status = {
            "charging": "charge",
            "discharging": "discharge",
            "fault": "fault",
            "balance": "balance",
        }.get(state, "idle")
        capacity_per_cell_mah = max(0.0, snapshot.remaining_capacity_ah * 1000.0 / max(1, len(self.cellCards)))
        for index, card in enumerate(self.cellCards):
            card.updateCell(
                CellState(
                    index=index + 1,
                    voltage=volt_values[index],
                    soc=soc_values[index],
                    soh=snapshot.health_percent,
                    capacity_mah=capacity_per_cell_mah,
                    temperature=25.0,
                    status=cell_status,
                )
            )

        self.packSocLabel.setText('整组电量 {value:.1f}%'.format(value=pack_soc))
        self.packPowerLabel.setText(
            '整组电压: {voltage:.2f} V | 电流: {current:+.2f} A'.format(
                voltage=snapshot.pack_voltage_v,
                current=snapshot.pack_current_a,
            )
        )
        voltage_spread_mv = (max(volt_values) - min(volt_values)) * 1000.0
        self.packHintLabel.setText('单节最大电压差: {value:.0f} mV'.format(value=voltage_spread_mv))

        if state == "charging":
            state_text = '充电中'
            current_value = max(0.0, snapshot.charge_current_a)
            hint = '电池正在充电'
            current_text = '充电电流: {value:.2f} A'.format(value=current_value)
        elif state == "discharging":
            state_text = '放电中'
            current_value = max(0.0, snapshot.discharge_current_a)
            hint = '电池正在对外供电'
            current_text = '放电电流: {value:.2f} A'.format(value=current_value)
        else:
            state_text = '待机'
            hint = '当前无明显充放电'
            current_text = '整组电流: {value:+.2f} A'.format(value=snapshot.pack_current_a)

        self.flowStateLabel.setText(state_text)
        self.flowHintLabel.setText(hint)
        self.flowCurrentLabel.setText(current_text)

        self.capacityTile.setMetric(
            f"{snapshot.remaining_capacity_ah:.2f} Ah",
            '标称容量: {value:.2f} Ah'.format(value=snapshot.nominal_capacity_ah),
        )
        self.healthTile.setMetric(
            f"{snapshot.health_percent:.1f}%",
            '电池健康状态',
        )

        total_minutes = max(0, int(snapshot.remaining_discharge_minutes))
        hours = total_minutes // 60
        minutes = total_minutes % 60
        self.remainingTile.setMetric(
            f"{hours:02d}:{minutes:02d}",
            '预计可持续放电',
        )

        self.energyTile.setMetric(
            f"{snapshot.charged_in_ah:.2f} Ah",
            '累计充入: {e_in:.1f} Wh | 累计放出: {e_out:.1f} Wh'.format(
                e_in=snapshot.energy_in_wh,
                e_out=snapshot.energy_out_wh,
            ),
        )

        self._setIoStatus(snapshot.input_online, snapshot.output_online)

    def _setIoStatus(self, input_online: bool, output_online: bool) -> None:
        self.inputBadge.setText('输入: 已连接' if input_online else '输入: 未连接')
        self.outputBadge.setText('输出: 已使能' if output_online else '输出: 未使能')

        self.inputBadge.setProperty("onlineState", "online" if input_online else "offline")
        self.outputBadge.setProperty("onlineState", "online" if output_online else "offline")
        self._refreshStateStyles()

    def _refreshStateStyles(self) -> None:
        for badge in (self.inputBadge, self.outputBadge):
            online = badge.property("onlineState") == "online"
            if online:
                background = "rgba(34, 197, 94, 0.22)"
                foreground = "#22C55E" if isDarkTheme() else "#166534"
                border = "rgba(34, 197, 94, 0.36)"
            else:
                background = "rgba(239, 68, 68, 0.20)"
                foreground = "#F87171" if isDarkTheme() else "#B91C1C"
                border = "rgba(239, 68, 68, 0.34)"
            badge.setStyleSheet(
                f"""
                background: {background};
                color: {foreground};
                border: 1px solid {border};
                border-radius: 14px;
                padding: 0 10px;
                font-weight: 700;
                """
            )

    def _onConnectionRequested(self) -> None:
        # Reserved for future serial/Bluetooth/USB/network connection implementations.
        self.connectionRequested.emit(self.connectionModeCombo.currentText())

    def _onThemeChanged(self, *_):
        StyleSheet.BATTERY_PAGE.apply(self)
        self._refreshStateStyles()
        for card in self.cellCards:
            card.refreshTheme()

