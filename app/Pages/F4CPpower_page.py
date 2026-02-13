# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : dark
#  @Time    : 2026 - 02-10 18:39
#  @FileName: F4CPpower_page.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel
)

from qfluentwidgets import (
    CardWidget, BodyLabel, StrongBodyLabel,
    PrimaryPushButton, PushButton,
    DoubleSpinBox, ComboBox,
    TextEdit, LargeTitleLabel, SimpleCardWidget

)


class OutputControlCard(SimpleCardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        layout.addWidget(StrongBodyLabel("输出控制"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        # 输出电压设定
        self.vset = DoubleSpinBox()
        self.vset.setRange(0, 100)
        self.vset.setDecimals(2)

        # 电流限流设定
        self.ilimit = DoubleSpinBox()
        self.ilimit.setRange(0, 50)
        self.ilimit.setDecimals(2)

        grid.addWidget(BodyLabel("输出电压"), 0, 0)
        grid.addWidget(self.vset, 0, 1)

        grid.addWidget(BodyLabel("输出电流"), 1, 0)
        grid.addWidget(self.ilimit, 1, 1)

        layout.addLayout(grid)

        btnLayout = QHBoxLayout()
        self.writeBtn = PrimaryPushButton("保存")
        self.readBtn = PushButton("读取")

        btnLayout.addWidget(self.writeBtn)
        btnLayout.addWidget(self.readBtn)

        layout.addSpacing(16)
        layout.addLayout(btnLayout)


# =========================
# 数据卡片（V I P 组）
# =========================
class PowerGroupCard(SimpleCardWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        layout.addWidget(StrongBodyLabel(title))

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)

        self.vLabel = LargeTitleLabel("0.00 V")
        self.iLabel = LargeTitleLabel("0.00 A")
        self.pLabel = LargeTitleLabel("0.00 W")

        for label in (self.vLabel, self.iLabel, self.pLabel):
            label.setFont(QFont("Consolas", 20, QFont.Bold))

        grid.addWidget(BodyLabel("电压"), 0, 0)
        grid.addWidget(self.vLabel, 0, 1)

        grid.addWidget(BodyLabel("电流"), 1, 0)
        grid.addWidget(self.iLabel, 1, 1)

        grid.addWidget(BodyLabel("功率"), 2, 0)
        grid.addWidget(self.pLabel, 2, 1)

        layout.addSpacing(10)
        layout.addLayout(grid)


# =========================
# 紧凑 PID 组件
# =========================
class CompactPID(SimpleCardWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        layout.addWidget(StrongBodyLabel(title))

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(12)

        self.kp = DoubleSpinBox()
        self.kp.setRange(0, 100)
        self.kp.setDecimals(4)

        self.ki = DoubleSpinBox()
        self.ki.setRange(0, 100)
        self.ki.setDecimals(4)

        self.kd = DoubleSpinBox()
        self.kd.setRange(0, 100)
        self.kd.setDecimals(4)

        grid.addWidget(BodyLabel("KP"), 0, 0)
        grid.addWidget(self.kp, 0, 1)

        grid.addWidget(BodyLabel("KI"), 1, 0)
        grid.addWidget(self.ki, 1, 1)

        grid.addWidget(BodyLabel("KD"), 2, 0)
        grid.addWidget(self.kd, 2, 1)

        layout.addLayout(grid)
        layout.addSpacing(12)

        btnLayout = QHBoxLayout()
        btnLayout.addWidget(PrimaryPushButton("保存"))
        btnLayout.addWidget(PushButton("读取"))
        layout.addLayout(btnLayout)


class F4CPpowerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("F4CPpowerPage")

        mainLayout = QVBoxLayout(self)
        mainLayout.setSpacing(15)
        mainLayout.setContentsMargins(20, 20, 20, 20)

        # =====================
        # 顶部 输入 / 输出 / 效率
        # =====================
        topLayout = QHBoxLayout()
        topLayout.setSpacing(15)

        self.inputGroup = PowerGroupCard("输入侧")
        self.outputGroup = PowerGroupCard("输出侧")

        self.effCard = CardWidget()
        effLayout = QVBoxLayout(self.effCard)
        effLayout.setContentsMargins(18, 18, 18, 18)
        effLayout.addWidget(StrongBodyLabel("效率"))

        self.effLabel = LargeTitleLabel("0.0 %")
        self.effLabel.setFont(QFont("Consolas", 22, QFont.Bold))
        effLayout.addWidget(self.effLabel)

        topLayout.addWidget(self.inputGroup)
        topLayout.addWidget(self.outputGroup)
        topLayout.addWidget(self.effCard)

        mainLayout.addLayout(topLayout)

        # =====================
        # 中部区域
        # =====================
        middleLayout = QHBoxLayout()
        middleLayout.setSpacing(15)

        # 左侧布局
        pidLayout = QVBoxLayout()
        pidLayout.setSpacing(12)

        self.voltagePID = CompactPID("电压环 PID")
        self.currentPID = CompactPID("电流环 PID")

        pidLayout.addWidget(self.voltagePID)
        pidLayout.addWidget(self.currentPID)
        pidLayout.addStretch()

        # 右侧 状态区
        verticalLayout = QVBoxLayout()
        self.outputControl = OutputControlCard()
        verticalLayout.addWidget(self.outputControl)

        statusCard = CardWidget()
        statusLayout = QVBoxLayout(statusCard)
        statusLayout.setContentsMargins(18, 18, 18, 18)

        statusLayout.addWidget(StrongBodyLabel("系统状态"))

        boardTempLabel = BodyLabel("板载温度:")
        coreTempLabel = BodyLabel("核心温度:")
        fanSpeedLabel = BodyLabel("风扇转速:")

        self.boardTempValue = BodyLabel("0.0 ℃")
        self.coreTempValue = BodyLabel("0.0 ℃")
        self.fanSpeedValue = BodyLabel("0 RPM")

        temp_layout = QGridLayout()
        temp_layout.setHorizontalSpacing(10)
        temp_layout.setVerticalSpacing(6)
        temp_layout.addWidget(boardTempLabel, 0, 0)
        temp_layout.addWidget(self.boardTempValue, 0, 1)
        temp_layout.addWidget(coreTempLabel, 1, 0)
        temp_layout.addWidget(self.coreTempValue, 1, 1)
        temp_layout.addWidget(fanSpeedLabel, 2, 0)
        temp_layout.addWidget(self.fanSpeedValue, 2, 1)

        self.modeBox = ComboBox()
        self.modeBox.addItems(["Buck", "Boost", "Mix"])

        self.enableBtn = PrimaryPushButton("启动输出")
        self.disableBtn = PushButton("关闭输出")

        temp_layout1 = QHBoxLayout()
        temp_layout1.addWidget(BodyLabel("工作模式"))
        temp_layout1.addWidget(self.modeBox)

        temp_layout2 = QHBoxLayout()
        temp_layout2.addWidget(self.enableBtn)
        temp_layout2.addWidget(self.disableBtn)

        statusLayout.addLayout(temp_layout)

        statusLayout.addSpacing(10)

        statusLayout.addLayout(temp_layout1)
        statusLayout.addSpacing(10)

        statusLayout.addLayout(temp_layout2)
        statusLayout.addSpacing(10)

        statusLayout.addStretch()

        verticalLayout.addWidget(statusCard)

        middleLayout.addLayout(pidLayout, 1)
        middleLayout.addLayout(verticalLayout, 1)

        mainLayout.addLayout(middleLayout)

        # =====================
        # 日志区
        # =====================
        logCard = CardWidget()
        logLayout = QVBoxLayout(logCard)
        logLayout.setContentsMargins(18, 18, 18, 18)

        logLayout.addWidget(StrongBodyLabel("系统日志"))

        self.logEdit = TextEdit()
        self.logEdit.setReadOnly(True)

        logLayout.addWidget(self.logEdit)

        mainLayout.addWidget(logCard)
