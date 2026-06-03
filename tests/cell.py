# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: cell.py
#  @FileType: 自动化测试文件，用来守住关键功能行为
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

import sys
import math
from dataclasses import dataclass
from typing import List

from PySide6.QtCore import Qt, QTimer, QRectF, Signal
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QBrush,
    QFont,
    QLinearGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QSizePolicy,
)

from qfluentwidgets import (
    CardWidget,
    BodyLabel,
    CaptionLabel,
    StrongBodyLabel,
    ProgressBar,
    FluentWindow,
    setTheme,
    Theme,
)
from qfluentwidgets import FluentWindow, setTheme, Theme, FluentIcon as FIF

@dataclass
class CellState:
    index: int
    voltage: float          # V
    soc: float              # 0 ~ 100
    soh: float              # 0 ~ 100
    capacity_mah: float     # mAh
    temperature: float      # ℃
    status: str             # Idle / Charge / Discharge / Balance / Fault


@dataclass
class PackState:
    cells: List[CellState]
    current: float          # A, 充电为正，放电为负
    state: str              # Charging / Discharging / Idle / Fault

    @property
    def total_voltage(self) -> float:
        return sum(cell.voltage for cell in self.cells)

    @property
    def avg_soc(self) -> float:
        if not self.cells:
            return 0.0
        return sum(cell.soc for cell in self.cells) / len(self.cells)

    @property
    def min_voltage(self) -> float:
        return min(cell.voltage for cell in self.cells) if self.cells else 0.0

    @property
    def max_voltage(self) -> float:
        return max(cell.voltage for cell in self.cells) if self.cells else 0.0

    @property
    def voltage_delta_mv(self) -> float:
        return (self.max_voltage - self.min_voltage) * 1000.0

    @property
    def power(self) -> float:
        return self.total_voltage * self.current


class WaterTankWidget(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._value = 70.0
        self._phase = 0.0
        self._status = "Idle"

        self.setMinimumSize(92, 150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timeout)
        self.timer.start(40)

    def setValue(self, value: float):
        self._value = max(0.0, min(100.0, value))
        self.update()

    def setStatus(self, status: str):
        self._status = status
        self.update()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def _on_timeout(self):
        self._phase += 0.18
        if self._phase > math.pi * 2:
            self._phase = 0.0
        self.update()

    def _water_color(self) -> QColor:
        if self._status.lower() == "fault":
            return QColor(255, 90, 90)
        if self._value >= 70:
            return QColor(32, 178, 170)
        if self._value >= 30:
            return QColor(255, 185, 70)
        return QColor(255, 95, 95)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)

        w = self.width()
        h = self.height()

        tank_margin_x = 18
        tank_margin_y = 12
        tank_rect = QRectF(
            tank_margin_x,
            tank_margin_y,
            w - tank_margin_x * 2,
            h - tank_margin_y * 2,
        )

        radius = 18

        # 外壳路径
        tank_path = QPainterPath()
        tank_path.addRoundedRect(tank_rect, radius, radius)

        # 背景
        bg_gradient = QLinearGradient(tank_rect.topLeft(), tank_rect.bottomLeft())
        bg_gradient.setColorAt(0, QColor(245, 247, 250))
        bg_gradient.setColorAt(1, QColor(228, 233, 240))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bg_gradient))
        painter.drawPath(tank_path)
        # 水位
        if self._value > 0.5:
            water_height = tank_rect.height() * self._value / 100.0
            water_top = tank_rect.bottom() - water_height

            # 水浅时自动降低波浪幅度，避免穿出底部
            wave_amp = min(4.0, max(0.0, water_height * 0.30))
            wave_len = tank_rect.width() / 1.2

            water_path = QPainterPath()

            # 从左下角开始封闭液体区域
            water_path.moveTo(tank_rect.left(), tank_rect.bottom())
            water_path.lineTo(tank_rect.left(), water_top)

            x = tank_rect.left()
            while x <= tank_rect.right():
                y = water_top + math.sin((x / wave_len) * math.pi * 2 + self._phase) * wave_amp

                # 限制水面范围，避免路径越界
                y = max(tank_rect.top(), min(y, tank_rect.bottom()))

                water_path.lineTo(x, y)
                x += 2

            water_path.lineTo(tank_rect.right(), tank_rect.bottom())
            water_path.closeSubpath()

            water_color = self._water_color()

            water_gradient = QLinearGradient(tank_rect.topLeft(), tank_rect.bottomLeft())
            water_gradient.setColorAt(
                0.0,
                QColor(water_color.red(), water_color.green(), water_color.blue(), 210)
            )
            water_gradient.setColorAt(
                1.0,
                QColor(water_color.red(), water_color.green(), water_color.blue(), 255)
            )

            painter.save()
            painter.setClipPath(tank_path)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(water_gradient))
            painter.drawPath(water_path)
            painter.restore()

        # 高光
        highlight = QPainterPath()
        highlight.addRoundedRect(
            QRectF(tank_rect.left() + 8, tank_rect.top() + 8, tank_rect.width() * 0.22, tank_rect.height() - 16),
            8,
            8,
        )
        painter.setBrush(QColor(255, 255, 255, 70))
        painter.setPen(Qt.NoPen)
        painter.drawPath(highlight.intersected(tank_path))

        # 外框
        border_color = QColor(95, 108, 125)
        painter.setPen(QPen(border_color, 1.6))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(tank_path)

        # 百分比文字
        painter.setPen(QColor(35, 42, 52))
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(tank_rect, Qt.AlignCenter, f"{self._value:.0f}%")


class CellCard(CardWidget):
    def __init__(self, cell: CellState, parent=None):
        super().__init__(parent)

        self.cell = cell

        self.setMinimumWidth(170)
        self.setMaximumWidth(220)

        self.titleLabel = StrongBodyLabel(f"Cell {cell.index}")
        self.statusLabel = CaptionLabel(cell.status)

        self.tank = WaterTankWidget()
        self.tank.setValue(cell.soc)
        self.tank.setStatus(cell.status)

        self.voltageLabel = BodyLabel()
        self.capacityLabel = CaptionLabel()
        self.tempLabel = CaptionLabel()

        self.sohLabel = CaptionLabel("SOH")
        self.sohBar = ProgressBar()
        self.sohBar.setRange(0, 100)

        self._init_layout()
        self.updateCell(cell)

    def _init_layout(self):
        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(14, 12, 14, 12)
        mainLayout.setSpacing(8)

        topLayout = QHBoxLayout()
        topLayout.addWidget(self.titleLabel)
        topLayout.addStretch(1)
        topLayout.addWidget(self.statusLabel)

        mainLayout.addLayout(topLayout)
        mainLayout.addWidget(self.tank, alignment=Qt.AlignCenter)

        mainLayout.addWidget(self.voltageLabel)
        mainLayout.addWidget(self.capacityLabel)
        mainLayout.addWidget(self.tempLabel)

        sohLayout = QHBoxLayout()
        sohLayout.addWidget(self.sohLabel)
        sohLayout.addStretch(1)
        sohLayout.addWidget(CaptionLabel("健康度"))

        mainLayout.addLayout(sohLayout)
        mainLayout.addWidget(self.sohBar)

    def updateCell(self, cell: CellState):
        self.cell = cell

        self.titleLabel.setText(f"Cell {cell.index}")
        self.statusLabel.setText(cell.status)

        self.tank.setValue(cell.soc)
        self.tank.setStatus(cell.status)

        self.voltageLabel.setText(f"电压：{cell.voltage:.3f} V")
        self.capacityLabel.setText(f"容量：{cell.capacity_mah:.0f} mAh")
        self.tempLabel.setText(f"温度：{cell.temperature:.1f} ℃")

        self.sohBar.setValue(int(cell.soh))

        if cell.status.lower() == "fault":
            self.statusLabel.setStyleSheet("color: rgb(255, 70, 70); font-weight: 600;")
        elif cell.status.lower() == "charge":
            self.statusLabel.setStyleSheet("color: rgb(0, 170, 120); font-weight: 600;")
        elif cell.status.lower() == "discharge":
            self.statusLabel.setStyleSheet("color: rgb(0, 120, 215); font-weight: 600;")
        elif cell.status.lower() == "balance":
            self.statusLabel.setStyleSheet("color: rgb(180, 120, 0); font-weight: 600;")
        else:
            self.statusLabel.setStyleSheet("color: rgb(100, 100, 100);")


class PackSummaryCard(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.titleLabel = StrongBodyLabel("Battery Pack AFE Status")
        self.stateLabel = BodyLabel("Idle")

        self.totalVoltageLabel = BodyLabel()
        self.currentLabel = BodyLabel()
        self.powerLabel = BodyLabel()
        self.avgSocLabel = BodyLabel()
        self.deltaLabel = BodyLabel()

        self.socBar = ProgressBar()
        self.socBar.setRange(0, 100)

        self._init_layout()

    def _init_layout(self):
        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(18, 16, 18, 16)
        mainLayout.setSpacing(12)

        topLayout = QHBoxLayout()
        topLayout.addWidget(self.titleLabel)
        topLayout.addStretch(1)
        topLayout.addWidget(self.stateLabel)

        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(8)

        grid.addWidget(self.totalVoltageLabel, 0, 0)
        grid.addWidget(self.currentLabel, 0, 1)
        grid.addWidget(self.powerLabel, 0, 2)
        grid.addWidget(self.avgSocLabel, 1, 0)
        grid.addWidget(self.deltaLabel, 1, 1)

        mainLayout.addLayout(topLayout)
        mainLayout.addLayout(grid)
        mainLayout.addWidget(self.socBar)

    def updatePack(self, pack: PackState):
        self.stateLabel.setText(pack.state)

        self.totalVoltageLabel.setText(f"总电压：{pack.total_voltage:.3f} V")
        self.currentLabel.setText(f"电流：{pack.current:+.2f} A")
        self.powerLabel.setText(f"功率：{pack.power:+.1f} W")
        self.avgSocLabel.setText(f"平均 SOC：{pack.avg_soc:.1f}%")
        self.deltaLabel.setText(f"压差：{pack.voltage_delta_mv:.1f} mV")

        self.socBar.setValue(int(pack.avg_soc))

        if pack.state.lower() == "fault":
            self.stateLabel.setStyleSheet("color: rgb(255, 70, 70); font-weight: 600;")
        elif pack.state.lower() == "charging":
            self.stateLabel.setStyleSheet("color: rgb(0, 170, 120); font-weight: 600;")
        elif pack.state.lower() == "discharging":
            self.stateLabel.setStyleSheet("color: rgb(0, 120, 215); font-weight: 600;")
        else:
            self.stateLabel.setStyleSheet("color: rgb(100, 100, 100);")


class AfeBatteryStatusWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.summaryCard = PackSummaryCard()
        self.cellCards: List[CellCard] = []

        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(20, 20, 20, 20)
        self.mainLayout.setSpacing(16)

        self.cellGrid = QGridLayout()
        self.cellGrid.setSpacing(14)

        self.mainLayout.addWidget(self.summaryCard)
        self.mainLayout.addLayout(self.cellGrid)
        self.mainLayout.addStretch(1)

    def setPackState(self, pack: PackState):
        self.summaryCard.updatePack(pack)

        while len(self.cellCards) < len(pack.cells):
            card = CellCard(pack.cells[len(self.cellCards)])
            self.cellCards.append(card)

        for card in self.cellCards:
            card.setParent(None)

        for i, cell in enumerate(pack.cells):
            self.cellCards[i].updateCell(cell)

            row = i // 4
            col = i % 4
            self.cellGrid.addWidget(self.cellCards[i], row, col)

        for i in range(len(pack.cells), len(self.cellCards)):
            self.cellCards[i].hide()

        for i in range(len(pack.cells)):
            self.cellCards[i].show()


class DemoWindow(FluentWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("AFE Battery Status Demo")
        self.resize(980, 720)

        self.afeWidget = AfeBatteryStatusWidget()
        self.afeWidget.setObjectName("AfeBatteryStatusInterface")
        self.addSubInterface(self.afeWidget, FIF.POWER_BUTTON, "AFE 状态")

        self.demoPack = PackState(
            cells=[
                CellState(1, 4.120, 92, 98, 2950, 28.1, "Charge"),
                CellState(2, 4.105, 88, 97, 2920, 28.3, "Charge"),
                CellState(3, 4.098, 86, 96, 2880, 29.0, "Balance"),
                CellState(4, 4.115, 90, 99, 2960, 28.5, "Charge"),
                CellState(5, 3.860, 56, 94, 2810, 30.2, "Discharge"),
                CellState(6, 3.780, 42, 91, 2700, 31.0, "Discharge"),
                CellState(7, 3.620, 25, 89, 2600, 32.1, "Idle"),
                CellState(8, 3.300, 12, 80, 2350, 36.5, "Fault"),
            ],
            current=3.25,
            state="Charging",
        )

        self.afeWidget.setPackState(self.demoPack)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    setTheme(Theme.AUTO)

    window = DemoWindow()
    window.show()

    sys.exit(app.exec())