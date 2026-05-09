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

from dataclasses import dataclass

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
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
)

from App.Core import StyleSheet
from Config import cfg


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


class LevelFillWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._percent = 0.0
        self.setMinimumSize(34, 110)

    def setPercent(self, percent: float) -> None:
        self._percent = max(0.0, min(100.0, percent))
        self.update()

    def refreshTheme(self) -> None:
        self.update()

    def _accentColor(self) -> QColor:
        color = getattr(cfg.themeColor, "value", None)
        return color if isinstance(color, QColor) else QColor("#3B82F6")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        border = QColor(255, 255, 255, 84) if isDarkTheme() else QColor(15, 23, 42, 65)
        shell = QColor(148, 163, 184, 42) if isDarkTheme() else QColor(148, 163, 184, 34)

        outer = self.rect().adjusted(4, 4, -4, -4)
        painter.setPen(border)
        painter.setBrush(shell)
        painter.drawRoundedRect(outer, 10, 10)

        inner = outer.adjusted(3, 3, -3, -3)
        fill_height = int(round(inner.height() * (self._percent / 100.0)))
        if fill_height <= 0:
            return

        fill_rect = inner.adjusted(0, inner.height() - fill_height, 0, 0)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._accentColor())
        painter.drawRoundedRect(fill_rect, 7, 7)


class BatteryCellCard(CardWidget):
    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.setObjectName(f"batteryCellCard{index}")
        self.setProperty("batteryCard", True)
        self.setProperty("cellCard", True)
        self.setBorderRadius(10)
        self._soc = 0.0

        self.titleLabel = SubtitleLabel(self)
        self.voltageLabel = TitleLabel("--", self)
        self.socLabel = StrongBodyLabel("--", self)
        self.levelWidget = LevelFillWidget(self)

        self.voltageLabel.setProperty("cellVoltage", True)
        self.socLabel.setProperty("cellSoc", True)
        setFont(self.voltageLabel, 30, QFont.DemiBold)

        infoLayout = QVBoxLayout()
        infoLayout.setContentsMargins(0, 0, 0, 0)
        infoLayout.setSpacing(6)
        infoLayout.addWidget(self.titleLabel)
        infoLayout.addWidget(self.voltageLabel)
        infoLayout.addWidget(self.socLabel)
        infoLayout.addStretch(1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addLayout(infoLayout, 1)
        layout.addWidget(self.levelWidget, 0, Qt.AlignRight | Qt.AlignVCenter)

        self._applyCardColor()
        self.applyTexts()

    def applyTexts(self) -> None:
        self.titleLabel.setText('电芯 {index}'.format(index=self.index))

    def setCellValue(self, soc_percent: float, voltage_v: float) -> None:
        self._soc = max(0.0, min(100.0, soc_percent))
        self.voltageLabel.setText(f"{voltage_v:.3f} V")
        self.socLabel.setText('电量 {value:.1f}%'.format(value=self._soc))
        self.levelWidget.setPercent(self._soc)

    def refreshTheme(self) -> None:
        self._applyCardColor()
        self.levelWidget.refreshTheme()

    def _applyCardColor(self) -> None:
        color = QColor(15, 23, 42, 128) if isDarkTheme() else QColor(255, 255, 255, 210)
        self.setBackgroundColor(color)


class MetricTile(CardWidget):
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
        self.summaryCard = CardWidget(self.scrollWidget)
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
        self.cellCard = CardWidget(self.scrollWidget)
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
            self.cellGrid.addWidget(card, index // 2, index % 2)

        layout.addLayout(self.cellGrid)
        self.rootLayout.addWidget(self.cellCard)

    def _initFlowCard(self) -> None:
        self.flowCard = CardWidget(self.scrollWidget)
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
        self.titleLabel.setText('电池组看板')
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
        self.updateSnapshot(
            BatterySnapshot(
                cell_soc=(89.5, 88.1, 90.4, 87.8),
                cell_voltage=(3.986, 3.974, 3.994, 3.968),
                input_online=True,
                output_online=True,
                charge_state="discharging",
                charge_current_a=0.0,
                discharge_current_a=3.2,
                pack_soc=88.9,
                pack_voltage_v=15.92,
                pack_current_a=-3.2,
                nominal_capacity_ah=20.0,
                remaining_capacity_ah=17.8,
                health_percent=96.0,
                remaining_discharge_minutes=333,
                charged_in_ah=5.42,
                energy_in_wh=86.1,
                energy_out_wh=21.4,
            )
        )

    def updateSnapshot(self, snapshot: BatterySnapshot) -> None:
        soc_values = list(snapshot.cell_soc)[:4]
        volt_values = list(snapshot.cell_voltage)[:4]
        while len(soc_values) < 4:
            soc_values.append(0.0)
        while len(volt_values) < 4:
            volt_values.append(0.0)

        for index, card in enumerate(self.cellCards):
            card.setCellValue(soc_values[index], volt_values[index])

        pack_soc = max(0.0, min(100.0, snapshot.pack_soc))
        self.packSocLabel.setText('整组电量 {value:.1f}%'.format(value=pack_soc))
        self.packPowerLabel.setText(
            '整组电压: {voltage:.2f} V | 电流: {current:+.2f} A'.format(
                voltage=snapshot.pack_voltage_v,
                current=snapshot.pack_current_a,
            )
        )
        voltage_spread_mv = (max(volt_values) - min(volt_values)) * 1000.0
        self.packHintLabel.setText('单节最大电压差: {value:.0f} mV'.format(value=voltage_spread_mv))

        state = (snapshot.charge_state or "idle").strip().lower()
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
        self._refreshStateStyles()
        for card in self.cellCards:
            card.refreshTheme()

