# -*- coding: utf-8 -*-
from __future__ import annotations

import binascii
import json
import time
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from PyQt5.QtCore import QCoreApplication, QIODevice, QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QSizePolicy,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from PyQt5.QtBluetooth import (
        QBluetoothAddress,
        QBluetoothDeviceDiscoveryAgent,
        QBluetoothLocalDevice,
        QBluetoothServiceInfo,
        QBluetoothSocket,
        QBluetoothUuid,
    )
except Exception:  # pragma: no cover - Qt Bluetooth 在部分精简环境中不存在
    QBluetoothAddress = None
    QBluetoothDeviceDiscoveryAgent = None
    QBluetoothLocalDevice = None
    QBluetoothServiceInfo = None
    QBluetoothSocket = None
    QBluetoothUuid = None

from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    CaptionLabel,
    ComboBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SpinBox,
    StrongBodyLabel,
    SwitchButton,
    TableWidget,
    TextEdit,
    TitleLabel,
    isDarkTheme,
)

from config import cfg
from app.manager import StyleSheet
from app.session import (
    ErrorEvent,
    RxEvent,
    SerialConfig,
    SerialEventType,
    SerialSession,
    SerialState,
    StateEvent,
    TxEvent,
    listSerialPorts,
    logger,
)
from app.core.const import (
    SESSION_PAGE_BAUD_RATES,
    SESSION_PAGE_RAW_FORMATS,
    SESSION_PAGE_SEND_MODES,
    SESSION_PAGE_V2_DEFAULT_CMD,
    SESSION_PAGE_V2_TYPE_ALIAS_TO_ID,
)
from app.protocol import Dispatcher as V2Dispatcher
from app.protocol import FrameBuilder as V2FrameBuilder
from app.protocol import FrameParser as V2FrameParser
from app.protocol import Payload as V2Payload, TYPE_REGISTRY
from app.protocol.dataType import DataFloat, DataInt, DataString, TypeBase


class DeviceTransport(Protocol):
    @property
    def is_open(self) -> bool: ...

    def open(self): ...

    def close(self): ...

    def write(self, data: bytes) -> int: ...


@dataclass
class _TlvRow:
    kind: str
    value: str
    typeId: int = 0


class PageCard(CardWidget):
    """QFluentWidgets card container used by the serial debug page."""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("PageCard")
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(20, 18, 20, 20)
        self.vBoxLayout.setSpacing(12)

        header = QWidget(self)
        headerLayout = QVBoxLayout(header)
        headerLayout.setContentsMargins(0, 0, 0, 0)
        headerLayout.setSpacing(2)

        self.titleLabel = StrongBodyLabel(title, header)
        headerLayout.addWidget(self.titleLabel)
        self.subtitleLabel = CaptionLabel(subtitle, header)
        self.subtitleLabel.setVisible(bool(subtitle))
        headerLayout.addWidget(self.subtitleLabel)
        self.vBoxLayout.addWidget(header)

    def addWidget(self, widget: QWidget, stretch: int = 0) -> None:
        self.vBoxLayout.addWidget(widget, stretch)

    def addLayout(self, layout, stretch: int = 0) -> None:
        self.vBoxLayout.addLayout(layout, stretch)


class QLabelCompat(BodyLabel):
    pass


class StatusPill(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SerialStatusPill")
        self.setFixedHeight(32)
        self.setMinimumWidth(104)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)
        self.dot = QLabelCompat("●", self)
        self.label = StrongBodyLabel("未连接", self)
        layout.addWidget(self.dot)
        layout.addWidget(self.label)
        self.setOnline(False)

    def setOnline(self, online: bool) -> None:
        dark = isDarkTheme()
        if online:
            bg = "rgba(34, 197, 94, 0.18)"
            fg = "#22C55E" if dark else "#15803D"
            border = "rgba(34, 197, 94, 0.34)"
            text = "已连接"
        else:
            bg = "rgba(148, 163, 184, 0.18)"
            fg = "#CBD5E1" if dark else "#475569"
            border = "rgba(148, 163, 184, 0.30)"
            text = "未连接"
        self.label.setText(text)
        self.dot.setStyleSheet(f"color: {fg}; font-size: 13px;")
        self.label.setStyleSheet(f"color: {fg}; font-weight: 700;")
        self.setStyleSheet(
            f"QFrame#SerialStatusPill {{ background: {bg}; border: 1px solid {border}; border-radius: 16px; }}"
        )


class BluetoothSession(QObject):
    def __init__(self, name: str, address: str, _event_receiver: Optional[QObject] = None):
        super().__init__()
        self.name = name
        self.address = address
        self._event_receiver = _event_receiver
        self._socket = None

    def set_event_receiver(self, receiver: Optional[QObject]) -> None:
        self._event_receiver = receiver

    @property
    def is_open(self) -> bool:
        return bool(self._socket) and self._socket.isOpen()

    def open(self):
        if self.is_open:
            return
        if (
            QBluetoothSocket is None
            or QBluetoothAddress is None
            or QBluetoothUuid is None
            or QBluetoothServiceInfo is None
        ):
            message = "当前环境不支持 Qt Bluetooth"
            logger.error(f"{self.__class__.__name__}: {message}")
            raise RuntimeError(message)

        self._post_event(StateEvent(SerialState.OPENING))
        self._socket = QBluetoothSocket(QBluetoothServiceInfo.RfcommProtocol)
        self._socket.readyRead.connect(self._on_ready_read)
        self._socket.error.connect(self._on_error)
        self._socket.connected.connect(lambda: self._post_event(StateEvent(SerialState.OPEN)))
        self._socket.disconnected.connect(lambda: self._post_event(StateEvent(SerialState.CLOSED)))
        self._socket.connectToService(
            QBluetoothAddress(self.address),
            QBluetoothUuid(QBluetoothUuid.SerialPort),
            QIODevice.OpenModeFlag.ReadWrite,
        )

    def close(self):
        if self._socket:
            self._socket.close()
            self._socket.deleteLater()
            self._socket = None
        self._post_event(StateEvent(SerialState.CLOSED))

    def write(self, data: bytes) -> int:
        if not self.is_open:
            message = "蓝牙设备未连接"
            logger.error(f"{self.__class__.__name__}: {message}")
            raise RuntimeError(message)
        written = int(self._socket.write(data))
        self._post_event(TxEvent(data))
        return written

    def _post_event(self, evt) -> None:
        if self._event_receiver is not None:
            QCoreApplication.postEvent(self._event_receiver, evt)

    def _on_ready_read(self):
        if not self._socket:
            return
        raw = self._socket.readAll()
        data = raw.data() if hasattr(raw, "data") else bytes(raw)
        if data:
            self._post_event(RxEvent(data))

    def _on_error(self, error):
        msg = self._socket.errorString() if self._socket else str(error)
        self._post_event(ErrorEvent(code=int(error), message=msg, fatal=True))
        self._post_event(StateEvent(SerialState.ERROR, info=msg))


class DevicePage(ScrollArea):
    rxEventSignal = pyqtSignal(str)
    stateSignal = pyqtSignal(bool)
    errSignal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session: Optional[DeviceTransport] = None
        self._bluetoothDevices: dict[str, str] = {}
        self._bluetoothDiscoveryAgent = None
        self._v2Parser: Optional[V2FrameParser] = None
        self._v2Dispatcher: Optional[V2Dispatcher] = None
        self._v2Seq = 0
        self._rxBuf = bytearray()
        self._rxBytes = 0
        self._txBytes = 0

        self._rxTimer = QTimer(self)
        self._rxTimer.setInterval(60)
        self._rxTimer.timeout.connect(self._flushRx)
        self._rxTimer.start()

        self.setObjectName("DevicePage")
        self.scrollWidget = QWidget(self)
        self.scrollWidget.setObjectName("deviceScrollWidget")
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.vBoxLayout.setSpacing(16)

        self._initHeader()
        self._initConnectionCard()
        self._initSendCard()
        self._initTlvCard()
        self._initConsoleCard()

        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        StyleSheet.DEVICE_PAGE.apply(self)
        self._applyLocalStyle()

        cfg.themeChanged.connect(self._onThemeChanged)
        self.refreshButton.clicked.connect(self.refreshCurrentConnectionTargets)
        self.connectButton.clicked.connect(self.toggleConnection)
        self.connectionTypeCombo.currentTextChanged.connect(self._onConnectionTypeChanged)
        self.sendButton.clicked.connect(self.onSend)
        self.clearButton.clicked.connect(lambda: self.logEdit.setPlainText(""))
        self.modeCombo.currentIndexChanged.connect(self._applyMode)
        self.addTlvBtn.clicked.connect(self._addDefaultTlvRow)
        self.delTlvBtn.clicked.connect(self._deleteSelectedTlvRows)
        self.exportTlvBtn.clicked.connect(self._exportTlvJsonToTx)
        self.importTlvBtn.clicked.connect(self._importTlvJsonFromTx)
        self.rxEventSignal.connect(self._appendLog)
        self.stateSignal.connect(self._onState)
        self.errSignal.connect(self._onError)

        self._applyTexts()
        self.refreshPorts()
        self._applyMode()

    def _initHeader(self):
        header = QWidget(self.scrollWidget)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        titleBox = QWidget(header)
        titleLayout = QVBoxLayout(titleBox)
        titleLayout.setContentsMargins(0, 0, 0, 0)
        titleLayout.setSpacing(2)
        self.titleLabel = TitleLabel("串口与 TVLCOM 调试", titleBox)
        self.subtitleLabel = BodyLabel("面向 UF4 数字电源的串口连接、Raw 收发和 TVLCOM V2 组包调试。", titleBox)
        titleLayout.addWidget(self.titleLabel)
        titleLayout.addWidget(self.subtitleLabel)

        self.statusPill = StatusPill(header)
        layout.addWidget(titleBox, 1)
        layout.addWidget(self.statusPill, 0, Qt.AlignTop)
        self.vBoxLayout.addWidget(header)

    def _initConnectionCard(self):
        self.connectionCard = PageCard("连接", "选择串口或蓝牙目标，连接状态会实时同步到右侧。", self.scrollWidget)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        self.connectionTypeLabel = BodyLabel("连接方式", self.connectionCard)
        self.connectionTypeCombo = ComboBox(self.connectionCard)
        self.connectionTypeCombo.addItems(["串口", "蓝牙"])

        self.portLabel = BodyLabel("串口", self.connectionCard)
        self.portCombo = ComboBox(self.connectionCard)
        self.portCombo.setMinimumWidth(180)

        self.bluetoothLabel = BodyLabel("蓝牙", self.connectionCard)
        self.bluetoothCombo = ComboBox(self.connectionCard)
        self.bluetoothCombo.setMinimumWidth(220)

        self.baudLabel = BodyLabel("波特率", self.connectionCard)
        self.baudCombo = ComboBox(self.connectionCard)
        self.baudCombo.addItems(list(SESSION_PAGE_BAUD_RATES))
        self.baudCombo.setCurrentText("921600")

        self.parseLabel = BodyLabel("解析", self.connectionCard)
        self.parseSwitch = SwitchButton(self.connectionCard)
        self.parseSwitch.setChecked(True)

        self.stateLabel = BodyLabel("未连接", self.connectionCard)
        self.refreshButton = PushButton("刷新设备", self.connectionCard)
        self.connectButton = PrimaryPushButton("连接", self.connectionCard)

        grid.addWidget(self.connectionTypeLabel, 0, 0)
        grid.addWidget(self.connectionTypeCombo, 0, 1)
        grid.addWidget(self.baudLabel, 0, 2)
        grid.addWidget(self.baudCombo, 0, 3)
        grid.addWidget(self.portLabel, 1, 0)
        grid.addWidget(self.portCombo, 1, 1)
        grid.addWidget(self.bluetoothLabel, 1, 0)
        grid.addWidget(self.bluetoothCombo, 1, 1)
        grid.addWidget(self.parseLabel, 1, 2)
        grid.addWidget(self.parseSwitch, 1, 3)
        grid.addWidget(self.stateLabel, 2, 0, 1, 2)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)
        buttons.addStretch(1)
        buttons.addWidget(self.refreshButton)
        buttons.addWidget(self.connectButton)
        grid.addLayout(buttons, 2, 2, 1, 2)

        self.connectionCard.addLayout(grid)
        self.vBoxLayout.addWidget(self.connectionCard)

    def _initSendCard(self):
        self.sendCard = PageCard("发送", "Raw 模式直接发送 HEX / ASCII；TVLCOM V2 模式会根据 TLV 表自动组帧。", self.scrollWidget)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        self.modeLabel = BodyLabel("发送模式", self.sendCard)
        self.modeCombo = ComboBox(self.sendCard)
        self.modeCombo.addItems(list(SESSION_PAGE_SEND_MODES))
        self.rawFmtCombo = ComboBox(self.sendCard)
        self.rawFmtCombo.addItems(list(SESSION_PAGE_RAW_FORMATS))

        self.cmdLabel = BodyLabel("CMD", self.sendCard)
        self.cmdSpin = SpinBox(self.sendCard)
        self.cmdSpin.setRange(0, 255)
        self.cmdSpin.setValue(SESSION_PAGE_V2_DEFAULT_CMD)
        self.cmdSpin.setDisplayIntegerBase(16)

        self.repeatLabel = BodyLabel("重复", self.sendCard)
        self.repeatSpin = SpinBox(self.sendCard)
        self.repeatSpin.setRange(1, 999)
        self.repeatSpin.setValue(1)
        self.repeatSpin.setFixedWidth(90)

        top.addWidget(self.modeLabel)
        top.addWidget(self.modeCombo)
        top.addWidget(self.rawFmtCombo)
        top.addSpacing(8)
        top.addWidget(self.cmdLabel)
        top.addWidget(self.cmdSpin)
        top.addWidget(self.repeatLabel)
        top.addWidget(self.repeatSpin)
        top.addStretch(1)
        self.sendCard.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(8)
        self.txEdit = LineEdit(self.sendCard)
        self.txEdit.setClearButtonEnabled(True)
        self.sendButton = PrimaryPushButton("发送", self.sendCard)
        bottom.addWidget(self.txEdit, 1)
        bottom.addWidget(self.sendButton)
        self.sendCard.addLayout(bottom)
        self.vBoxLayout.addWidget(self.sendCard)

    def _initTlvCard(self):
        self.tlvCard = PageCard("TVLCOM V2 Payload", "每一行对应一个 TLV 数据项，启用后参与组包。", self.scrollWidget)
        self.tlvTable = TableWidget(self.tlvCard)
        self.tlvTable.setColumnCount(4)
        self.tlvTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tlvTable.setColumnHidden(0, True)
        self.tlvTable.setMinimumHeight(170)
        self.tlvCard.addWidget(self.tlvTable)

        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(8)
        self.addTlvBtn = PushButton("新增 TLV", self.tlvCard)
        self.delTlvBtn = PushButton("删除选中", self.tlvCard)
        self.exportTlvBtn = PushButton("导出 JSON", self.tlvCard)
        self.importTlvBtn = PushButton("导入 JSON", self.tlvCard)
        bar.addWidget(self.addTlvBtn)
        bar.addWidget(self.delTlvBtn)
        bar.addStretch(1)
        bar.addWidget(self.importTlvBtn)
        bar.addWidget(self.exportTlvBtn)
        self.tlvCard.addLayout(bar)
        self.vBoxLayout.addWidget(self.tlvCard)

    def _initConsoleCard(self):
        self.consoleCard = PageCard("日志", "蓝色为接收，绿色为发送/ACK，红色为错误。", self.scrollWidget)
        stats = QHBoxLayout()
        stats.setContentsMargins(0, 0, 0, 0)
        stats.setSpacing(16)
        self.rxStatLabel = CaptionLabel("RX 0 B", self.consoleCard)
        self.txStatLabel = CaptionLabel("TX 0 B", self.consoleCard)
        self.clearButton = PushButton("清空日志", self.consoleCard)
        stats.addWidget(self.rxStatLabel)
        stats.addWidget(self.txStatLabel)
        stats.addStretch(1)
        stats.addWidget(self.clearButton)
        self.consoleCard.addLayout(stats)

        self.logEdit = TextEdit(self.consoleCard)
        self.logEdit.setReadOnly(True)
        self.logEdit.document().setMaximumBlockCount(500)
        self.logEdit.setMinimumHeight(260)
        self.logEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.consoleCard.addWidget(self.logEdit, 1)
        self.vBoxLayout.addWidget(self.consoleCard, 1)

    def _applyLocalStyle(self):
        dark = isDarkTheme()
        border = "rgba(255, 255, 255, 0.10)" if dark else "rgba(15, 23, 42, 0.08)"
        sub = "rgba(226, 232, 240, 0.72)" if dark else "rgba(71, 85, 105, 0.78)"
        console = "#0B1020" if dark else "#F8FAFC"
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QWidget#deviceScrollWidget {{ background: transparent; }}
            CaptionLabel {{ color: {sub}; }}
            TextEdit {{
                background: {console};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 8px;
            }}
            """
        )
        self.statusPill.setOnline(bool(self._session and self._session.is_open))
        self._refreshTexteditColor()

    def _applyTexts(self):
        self.parseSwitch.setOnText("解析 TVLCOM")
        self.parseSwitch.setOffText("解析 TVLCOM")
        self.stateLabel.setText("未连接" if not self._session or not self._session.is_open else "已连接")
        self.connectButton.setText("连接" if not self._session or not self._session.is_open else "断开")
        self.logEdit.setPlaceholderText("设备日志 / 返回数据…")
        self.txEdit.setPlaceholderText("Raw：输入 HEX（例如 01 0A FF）；TVLCOM V2 可留空，使用下方 TLV 表组包")
        self._onConnectionTypeChanged(self.connectionTypeCombo.currentText())
        self._applyMode()

    def event(self, e):
        if e.type() == SerialEventType.RX:
            data = e.payload.data
            if data:
                try:
                    self._onRxRaw(data)
                except Exception as exc:
                    logger.error(exc)
            return True
        if e.type() == SerialEventType.TX:
            data = e.payload.data
            self._txBytes += len(data)
            self._updateStats()
            self._appendLog(f'TX({len(data)}): {data.hex(" ")}')
            return True
        if e.type() == SerialEventType.ERROR:
            self._onError(e.payload.message)
            return True
        if e.type() == SerialEventType.STATE:
            self._onState(e.payload.state == SerialState.OPEN)
            if e.payload.info:
                self._appendLog(e.payload.info)
            return True
        return super().event(e)

    def _isV2Mode(self) -> bool:
        return self.modeCombo.currentIndex() == 1

    def _applyMode(self):
        isV2 = self._isV2Mode()
        self.tlvCard.setVisible(isV2)
        self.rawFmtCombo.setVisible(not isV2)
        self.cmdLabel.setVisible(isV2)
        self.cmdSpin.setVisible(isV2)
        self.tlvTable.setHorizontalHeaderLabels(["类型 ID", "类型", "值", "启用"])
        self._refreshTlvRowEditorsForMode()

    def _appendLog(self, text: str):
        ts = time.strftime("%H:%M:%S")
        msg = f"[{ts}] {text}"
        if not (
            text.startswith("RX(")
            or text.startswith("TX(")
            or text.startswith("V2 RX")
            or text.startswith("V2 ACK")
            or text.startswith("V2 NACK")
        ):
            logger.info(text)

        lc = text.strip()
        dark = isDarkTheme()
        if lc.startswith("ERR:") or lc.startswith("错误:"):
            color = QColor("#FF6B6B" if dark else "#B91C1C")
        elif lc.startswith("RX(") or lc.startswith("V2 RX"):
            color = QColor("#6EA8FE" if dark else "#1D4ED8")
        elif lc.startswith("V2 ACK") or lc.startswith("V2 NACK") or lc.startswith("TX v2") or lc.startswith("TX("):
            color = QColor("#8BD78F" if dark else "#166534")
        elif lc.startswith("已打开") or lc.startswith("正在连接") or lc.startswith("Disconnected"):
            color = QColor("#D6B4FF" if dark else "#7C3AED")
        else:
            color = QColor("#FFFFFF" if dark else "#0F172A")
        self._appendColored(msg + "\n", color)

    def _appendColored(self, text: str, color: QColor):
        try:
            cursor: QTextCursor = self.logEdit.textCursor()
            cursor.movePosition(QTextCursor.End)
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
            self.logEdit.setTextCursor(cursor)
            self.logEdit.ensureCursorVisible()
        except Exception:
            try:
                self.logEdit.appendPlainText(text.rstrip("\n"))
            except Exception:
                pass
        self._refreshTexteditColor()

    def _flushRx(self):
        if not self._rxBuf:
            return
        data = bytes(self._rxBuf)
        self._rxBuf.clear()
        self._appendLog(f'RX({len(data)}): {data.hex(" ")}')

    def _onThemeChanged(self, *_):
        StyleSheet.DEVICE_PAGE.apply(self)
        self._applyLocalStyle()

    def _refreshTexteditColor(self):
        try:
            palette = self.logEdit.palette()
            palette.setColor(self.logEdit.foregroundRole(), QColor("#ffffff" if isDarkTheme() else "#000000"))
            self.logEdit.setPalette(palette)
        except Exception:
            pass

    def _updateStats(self):
        self.rxStatLabel.setText(f"RX {self._rxBytes} B")
        self.txStatLabel.setText(f"TX {self._txBytes} B")

    def _addDefaultTlvRow(self):
        row = self.tlvTable.rowCount()
        self.tlvTable.insertRow(row)

        typeSpin = SpinBox(self.tlvTable)
        typeSpin.setRange(0, 255)
        typeSpin.setValue(SESSION_PAGE_V2_TYPE_ALIAS_TO_ID["string"])
        self.tlvTable.setCellWidget(row, 0, typeSpin)

        kindCombo = ComboBox(self.tlvTable)
        kindCombo.currentTextChanged.connect(lambda text, spin=typeSpin: self._syncV2TypeIdWithKind(spin, text))
        self.tlvTable.setCellWidget(row, 1, kindCombo)
        self._configureKindCombo(kindCombo, typeSpin)

        self.tlvTable.setItem(row, 2, QTableWidgetItem(""))

        enable = SwitchButton(self.tlvTable)
        enable.setOnText("启用")
        enable.setOffText("禁用")
        enable.setChecked(True)
        self.tlvTable.setCellWidget(row, 3, enable)

    def _deleteSelectedTlvRows(self):
        for row in sorted({i.row() for i in self.tlvTable.selectedIndexes()}, reverse=True):
            self.tlvTable.removeRow(row)

    def _iterTlvRows(self) -> list[_TlvRow]:
        rows: list[_TlvRow] = []
        for rowIndex in range(self.tlvTable.rowCount()):
            enable = self.tlvTable.cellWidget(rowIndex, 3)
            if isinstance(enable, SwitchButton) and not enable.isChecked():
                continue

            kindCombo = self.tlvTable.cellWidget(rowIndex, 1)
            kind = kindCombo.currentText() if isinstance(kindCombo, ComboBox) else "string"
            typeId = self._v2TypeIdFromKind(kind)
            if typeId is None:
                raise ValueError(f"V2 unsupported type: {kind}")

            valueItem = self.tlvTable.item(rowIndex, 2)
            rows.append(_TlvRow(kind=kind, value=valueItem.text() if valueItem else "", typeId=typeId))
        return rows

    def _exportTlvJsonToTx(self):
        self.txEdit.setText(json.dumps([row.__dict__ for row in self._iterTlvRows()], ensure_ascii=False))

    def _importTlvJsonFromTx(self):
        raw = self.txEdit.text().strip()
        if not raw:
            return
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("JSON must be a list")

        self.tlvTable.setRowCount(0)
        for item in data:
            typeId = int(item.get("typeId", item.get("type_id", 0)))
            kind = str(item.get("kind", "string"))
            value = str(item.get("value", ""))

            self._addDefaultTlvRow()
            row = self.tlvTable.rowCount() - 1
            typeSpin = self.tlvTable.cellWidget(row, 0)
            kindCombo = self.tlvTable.cellWidget(row, 1)
            if isinstance(kindCombo, ComboBox):
                kindCombo.setCurrentText(self._normalizeV2Kind(kind, typeId))
            if isinstance(typeSpin, SpinBox) and isinstance(kindCombo, ComboBox):
                typeSpin.setValue(self._v2TypeIdFromKind(kindCombo.currentText()) or typeId)
            self.tlvTable.setItem(row, 2, QTableWidgetItem(value))
            enable = self.tlvTable.cellWidget(row, 3)
            if isinstance(enable, SwitchButton):
                enable.setChecked(True)

    def _v2TypeIds(self) -> list[int]:
        return sorted(TYPE_REGISTRY)

    def _v2SelectorOptions(self) -> list[str]:
        return [self._v2TypeName(typeId) for typeId in self._v2TypeIds()]

    def _defaultV2Selector(self) -> str:
        options = self._v2SelectorOptions()
        return "string" if "string" in options else (options[0] if options else "")

    def _v2TypeIdFromKind(self, kind: str) -> Optional[int]:
        typeId = SESSION_PAGE_V2_TYPE_ALIAS_TO_ID.get((kind or "").strip().lower())
        return typeId if typeId in TYPE_REGISTRY else None

    def _normalizeV2Kind(self, kind: str, typeId: int = 0) -> str:
        resolvedTypeId = self._v2TypeIdFromKind(kind)
        if resolvedTypeId is None and typeId in TYPE_REGISTRY:
            resolvedTypeId = typeId
        if resolvedTypeId is None:
            raise ValueError(f"V2 unsupported type: {kind or typeId}")
        return self._v2TypeName(resolvedTypeId)

    def _configureKindCombo(self, kindCombo: ComboBox, typeSpin: SpinBox, preferredKind: str = "", preferredTypeId: int = 0):
        kindCombo.blockSignals(True)
        kindCombo.clear()
        options = self._v2SelectorOptions()
        kindCombo.addItems(options)
        selected = self._defaultV2Selector()
        if options:
            try:
                selected = self._normalizeV2Kind(preferredKind, preferredTypeId)
            except ValueError:
                pass
        if selected:
            kindCombo.setCurrentText(selected)
            self._syncV2TypeIdWithKind(typeSpin, selected)
        kindCombo.blockSignals(False)

    def _refreshTlvRowEditorsForMode(self):
        for row in range(self.tlvTable.rowCount()):
            typeSpin = self.tlvTable.cellWidget(row, 0)
            kindCombo = self.tlvTable.cellWidget(row, 1)
            if isinstance(typeSpin, SpinBox) and isinstance(kindCombo, ComboBox):
                try:
                    self._configureKindCombo(kindCombo, typeSpin, kindCombo.currentText(), typeSpin.value())
                except ValueError:
                    self._configureKindCombo(kindCombo, typeSpin)

    def _buildV2PayloadFromTable(self) -> bytes:
        payload = V2Payload()
        for row in self._iterTlvRows():
            typeObj = TYPE_REGISTRY.get(int(row.typeId) & 0xFF)
            if typeObj is None:
                raise ValueError(f"V2 unsupported type ID: 0x{row.typeId:02X}")
            payload.addData(typeObj, self._coerceV2Value(row, typeObj))
        return payload.toBytes()

    def _syncV2TypeIdWithKind(self, typeSpin: SpinBox, kind: str):
        suggested = self._v2TypeIdFromKind(kind)
        if suggested is not None:
            typeSpin.setValue(suggested)

    def _coerceV2Value(self, row: _TlvRow, typeObj: TypeBase):
        rawValue = row.value.strip()
        if isinstance(typeObj, DataString):
            return row.value
        if isinstance(typeObj, DataFloat):
            return float(rawValue or "0")
        if isinstance(typeObj, DataInt):
            return int(rawValue or "0", 0)
        raise ValueError(f"V2 unsupported value type: {row.kind}")

    def _resetV2Protocol(self):
        self._v2Parser = None
        self._v2Dispatcher = None
        self._v2Seq = 0

    def _initV2Protocol(self):
        self._v2Parser = V2FrameParser()
        self._v2Dispatcher = V2Dispatcher()
        self._v2Dispatcher.setAckHandler(lambda cmd, seq, payloadData: self.rxEventSignal.emit(f"V2 ACK cmd={cmd:02X} seq={seq} [{self._formatV2PayloadItems(payloadData)}]"))
        self._v2Dispatcher.setNackHandler(lambda cmd, seq, payloadData: self.rxEventSignal.emit(f"V2 NACK cmd={cmd:02X} seq={seq} [{self._formatV2PayloadItems(payloadData)}]"))

    def _v2TypeName(self, typeId: int) -> str:
        typeObj = TYPE_REGISTRY.get(typeId)
        if typeObj is None:
            return "bytes"
        if isinstance(typeObj, DataString):
            return "string"
        if isinstance(typeObj, DataFloat):
            return "float"
        return getattr(typeObj, "name", typeObj.__class__.__name__)

    def _formatV2PayloadItems(self, payloadData: dict[int, Any]) -> str:
        if not payloadData:
            return ""
        parts = []
        for typeId, value in payloadData.items():
            rendered = value.hex(" ") if isinstance(value, bytes) else value
            parts.append(f"T{typeId:02X}({self._v2TypeName(typeId)}):{rendered}")
        return ", ".join(parts)

    def _handleV2RxFrames(self, data: bytes):
        if self._v2Parser is None:
            return
        for frame in self._v2Parser.inputBytes(data):
            if self._v2Dispatcher is not None and self._v2Dispatcher.dispatch(frame):
                continue
            parsed = V2Payload.parse(frame["payload"])
            self.rxEventSignal.emit(f'V2 RX cmd={frame["cmd"]:02X} seq={frame["seq"]} [{self._formatV2PayloadItems(parsed)}]')

    def _parseRawInput(self, text: str, fmt: str) -> bytes:
        if (fmt or "").upper() == "ASCII":
            return text.encode("utf-8")
        normalized = text.replace("0x", "").replace(",", " ").replace("\n", " ").replace("\r", " ").replace("\t", " ")
        hexstr = "".join(ch for ch in normalized if ch != " ")
        if len(hexstr) % 2 != 0:
            raise ValueError("HEX length must be even")
        return binascii.unhexlify(hexstr)

    def refreshPorts(self):
        ports = [p.strip() for p in (listSerialPorts() or []) if p and p.strip()]
        self._appendLog(f"串口列表: {ports}")
        current = self.portCombo.currentText().strip()
        self.portCombo.clear()
        if ports:
            self.portCombo.addItems(ports)
            if current in ports:
                self.portCombo.setCurrentText(current)
        else:
            self.portCombo.addItem("未发现串口")

    def refreshBluetoothDevices(self):
        current = self.bluetoothCombo.currentText().strip()
        self._bluetoothDevices.clear()
        self.bluetoothCombo.clear()

        if QBluetoothLocalDevice is None:
            self._appendLog("错误: 当前环境不支持 Qt Bluetooth")
            return

        try:
            local_devices = QBluetoothLocalDevice.allDevices()
            for local_info in local_devices:
                local_device = QBluetoothLocalDevice(local_info.address())
                for address in local_device.connectedDevices():
                    self._addBluetoothTarget(address.toString(), address.toString())
        except Exception as exc:
            self._appendLog(f"错误: 蓝牙设备列表读取失败: {exc}")

        if current in self._bluetoothDevices:
            self.bluetoothCombo.setCurrentText(current)

        self._appendLog(f"蓝牙设备列表: {list(self._bluetoothDevices)}")
        self._startBluetoothDiscovery()

    def refreshCurrentConnectionTargets(self):
        if self._isBluetoothMode():
            self.refreshBluetoothDevices()
        else:
            self.refreshPorts()

    def _startBluetoothDiscovery(self):
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

    def _onBluetoothDeviceDiscovered(self, device_info):
        try:
            name = device_info.name().strip() or device_info.address().toString()
            address = device_info.address().toString()
        except Exception:
            return
        self._addBluetoothTarget(name, address)

    def _addBluetoothTarget(self, name: str, address: str):
        label = f"{name} ({address})" if name != address else address
        if label in self._bluetoothDevices:
            return
        self._bluetoothDevices[label] = address
        existing = [self.bluetoothCombo.itemText(i) for i in range(self.bluetoothCombo.count())]
        if label not in existing:
            self.bluetoothCombo.addItem(label)

    def _isBluetoothMode(self) -> bool:
        return self.connectionTypeCombo.currentText().strip() == "蓝牙"

    def _onConnectionTypeChanged(self, text: str):
        isBluetooth = text.strip() == "蓝牙"
        self.portLabel.setVisible(not isBluetooth)
        self.portCombo.setVisible(not isBluetooth)
        self.baudLabel.setVisible(not isBluetooth)
        self.baudCombo.setVisible(not isBluetooth)
        self.bluetoothLabel.setVisible(isBluetooth)
        self.bluetoothCombo.setVisible(isBluetooth)
        self.refreshButton.setText("扫描蓝牙" if isBluetooth else "刷新串口")

    def toggleConnection(self):
        if self._session and self._session.is_open:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        if self._isBluetoothMode():
            self._connectBluetooth()
        else:
            self._connectSerial()

    def _connectSerial(self):
        port = self.portCombo.currentText().strip()
        if not port or port == "未发现串口":
            self._appendLog("错误: 未找到串口。请先刷新并检查驱动。")
            return

        baud = int(self.baudCombo.currentText().strip())
        self._session = SerialSession(SerialConfig(port=port, baudrate=baud), _event_receiver=self)
        try:
            self._session.set_event_receiver(self)
        except Exception:
            pass
        self._session.on_tx = lambda data: self._appendLog(f'TX({len(data)}): {data.hex(" ")}')
        self._session.on_debug = lambda text: self._appendLog(f"DBG: {text}")
        self._session.on_state = lambda ok: self.stateSignal.emit(ok)
        self._initV2Protocol()

        try:
            self._session.open()
            self._appendLog(f"已打开串口: {port} @ {self.baudCombo.currentText().strip()}")
        except Exception as exc:
            self._onError(str(exc))
            self._session = None
            self._resetV2Protocol()

    def _connectBluetooth(self):
        target = self.bluetoothCombo.currentText().strip()
        address = self._bluetoothDevices.get(target, "")
        if not target or not address:
            self._appendLog("错误: 未选择蓝牙设备。请先刷新并选择设备。")
            return

        name = target.rsplit(" (", 1)[0]
        self._session = BluetoothSession(name=name, address=address, _event_receiver=self)
        try:
            self._session.set_event_receiver(self)
        except Exception:
            pass
        self._initV2Protocol()

        try:
            self._session.open()
            self._appendLog(f"正在连接蓝牙设备: {target}")
        except Exception as exc:
            self._onError(str(exc))
            self._session = None
            self._resetV2Protocol()

    def _disconnect(self):
        try:
            if self._session:
                self._session.close()
        finally:
            self._session = None
            self._resetV2Protocol()
            self._appendLog("Disconnected")
            self._applyTexts()
            self._onState(False)

    def _safeWrite(self, data: bytes):
        if not self._session or not self._session.is_open:
            return
        try:
            from session.session_serial import SendEvent
            if isinstance(self._session, SerialSession):
                QCoreApplication.postEvent(self._session, SendEvent(data))
            else:
                self._session.write(data)
        except Exception:
            try:
                self._session.write(data)
            except Exception as exc:
                self.errSignal.emit(str(exc))

    def _onState(self, ok: bool):
        self.stateLabel.setText("已连接，链路可用" if ok else "未连接")
        self.connectButton.setText("断开" if ok else "连接")
        self.statusPill.setOnline(ok)

    def _onError(self, msg: str):
        self._appendLog(f"错误: {msg}")
        logger.error(msg)

    def _onRxRaw(self, data: bytes):
        self._rxBytes += len(data)
        self._updateStats()
        self._rxBuf.extend(data)
        if self.parseSwitch.isChecked() and self._v2Parser is not None:
            try:
                self._handleV2RxFrames(data)
            except Exception as exc:
                self.errSignal.emit(f"TVLCOMV2_FULL feed failed: {exc}")

    def onSend(self):
        if not self._session or not self._session.is_open:
            self._appendLog("错误: 设备未连接")
            return

        repeat = int(self.repeatSpin.value())
        if not self._isV2Mode():
            raw = self.txEdit.text().strip()
            if not raw:
                return
            try:
                data = self._parseRawInput(raw, self.rawFmtCombo.currentText())
            except Exception as exc:
                self._appendLog(f"错误: Raw 解析失败: {exc}")
                return
            for _ in range(repeat):
                self._safeWrite(data)
                self._txBytes += len(data)
            self._updateStats()
            self._appendLog(f'发送 Raw: ({len(data)}): {data.hex(" ")}')
            return

        try:
            payload = self._buildV2PayloadFromTable()
        except Exception as exc:
            self._appendLog(f"错误: TVLCOM_V2 组包失败: {exc}")
            return

        cmd = self.cmdSpin.value()
        seqs: list[int] = []
        total = 0
        for _ in range(repeat):
            self._v2Seq = (self._v2Seq + 1) % 256
            frame = V2FrameBuilder.buildFrame(cmd, self._v2Seq, payload)
            self._safeWrite(frame)
            total += len(frame)
            seqs.append(self._v2Seq)
        self._txBytes += total
        self._updateStats()

        seqText = str(seqs[0]) if len(seqs) == 1 else ",".join(str(seq) for seq in seqs)
        self._appendLog(f'TX v2: CMD={cmd:02X} seq={seqText} payload=({len(payload)}) {payload.hex(" ")}')
