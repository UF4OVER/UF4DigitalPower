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
    QHeaderView,
    QHBoxLayout,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
try:
    from PyQt5.QtBluetooth import (
        QBluetoothAddress,
        QBluetoothDeviceDiscoveryAgent,
        QBluetoothLocalDevice,
        QBluetoothSocket,
        QBluetoothUuid,
    )
except Exception:
    QBluetoothAddress = None
    QBluetoothDeviceDiscoveryAgent = None
    QBluetoothLocalDevice = None
    QBluetoothSocket = None
    QBluetoothUuid = None

from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SpinBox,
    SwitchButton,
    TableWidget,
    TextEdit,
    TitleLabel,
    isDarkTheme, ScrollArea,
)

from Config import cfg
from App.Core import (
    SESSION_PAGE_BAUD_RATES,
    SESSION_PAGE_RAW_FORMATS,
    SESSION_PAGE_SEND_MODES,
    SESSION_PAGE_V2_DEFAULT_CMD,
    SESSION_PAGE_V2_TYPE_ALIAS_TO_ID,
    ErrorEvent,
    RxEvent,
    SerialConfig,
    SerialEventType,
    SerialSession,
    SerialState,
    StateEvent,
    StyleSheet,
    TxEvent,
    listSerialPorts,
    logger,
)
from App.Core.TVLCOMV2_FULL import (
    Dispatcher as V2Dispatcher,
    FrameBuilder as V2FrameBuilder,
    FrameParser as V2FrameParser,
)
from App.Core.TVLCOMV2_FULL import Payload as V2Payload, TYPE_REGISTRY
from App.Core.TVLCOMV2_FULL.dataType import DataFloat, DataInt, DataString, TypeBase


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


class BluetoothSession(QObject):
    def __init__(self, name: str, address: str, _event_receiver: Optional[QObject] = None):
        super().__init__()
        self.name = name
        self.address = address
        self._event_receiver = _event_receiver
        self._socket = None

    def set_event_receiver(self, receiver: Optional[QObject]) -> None:
        self._event_receiver = receiver

    def open(self):
        if self.is_open:
            return
        if QBluetoothSocket is None or QBluetoothAddress is None or QBluetoothUuid is None:
            raise RuntimeError("当前环境不支持 Qt Bluetooth")

        self._post_event(StateEvent(SerialState.OPENING))
        self._socket = QBluetoothSocket(QBluetoothSocket.RfcommProtocol)
        self._socket.readyRead.connect(self._on_ready_read)
        self._socket.error.connect(self._on_error)
        self._socket.connected.connect(lambda: self._post_event(StateEvent(SerialState.OPEN)))
        self._socket.disconnected.connect(lambda: self._post_event(StateEvent(SerialState.CLOSED)))
        self._socket.connectToService(
            QBluetoothAddress(self.address),
            QBluetoothUuid(QBluetoothUuid.SerialPort),
            QIODevice.OpenModeFlag.ReadWrite,
        )

    @property
    def is_open(self) -> bool:
        return bool(self._socket) and self._socket.isOpen()

    def close(self):
        if self._socket:
            self._socket.close()
            self._socket.deleteLater()
            self._socket = None
        self._post_event(StateEvent(SerialState.CLOSED))

    def write(self, data: bytes) -> int:
        if not self.is_open:
            raise RuntimeError("蓝牙设备未连接")
        written = int(self._socket.write(data))
        self._post_event(TxEvent(data))
        return written

    def _post_event(self, evt):
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

        self._rxTimer = QTimer(self)
        self._rxTimer.setInterval(60)
        self._rxTimer.timeout.connect(self._flushRx)
        self._rxTimer.start()

        self.setObjectName("DevicePage")

        self.scrollWidget = QWidget(self)
        self.scrollWidget.setObjectName("deviceScrollWidget")
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.vBoxLayout.setSpacing(12)

        self.titleLabel = TitleLabel("TVL COM", self.scrollWidget)
        self.vBoxLayout.addWidget(self.titleLabel)

        cfg.themeChanged.connect(self._onThemeChanged)

        self._initConnectionBar()
        self._initLogConsole()
        self._initModeBar()
        self._initTlvTable()
        self._initSendBar()

        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        StyleSheet.DEVICE_PAGE.apply(self)

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

    def _initConnectionBar(self):
        connBar = QWidget(self.scrollWidget)
        connLayout = QHBoxLayout(connBar)
        connLayout.setContentsMargins(0, 0, 0, 0)
        connLayout.setSpacing(8)

        self.connectionTypeLabel = BodyLabel(connBar)
        connLayout.addWidget(self.connectionTypeLabel)
        self.connectionTypeCombo = ComboBox(connBar)
        self.connectionTypeCombo.addItems(["串口", "蓝牙"])
        self.connectionTypeCombo.setMinimumWidth(96)
        connLayout.addWidget(self.connectionTypeCombo)

        self.portLabel = BodyLabel(connBar)
        connLayout.addWidget(self.portLabel)
        self.portCombo = ComboBox(connBar)
        self.portCombo.setMinimumWidth(160)
        connLayout.addWidget(self.portCombo)

        self.bluetoothLabel = BodyLabel(connBar)
        connLayout.addWidget(self.bluetoothLabel)
        self.bluetoothCombo = ComboBox(connBar)
        self.bluetoothCombo.setMinimumWidth(180)
        connLayout.addWidget(self.bluetoothCombo)

        self.baudLabel = BodyLabel(connBar)
        connLayout.addWidget(self.baudLabel)
        self.baudCombo = ComboBox(connBar)
        self.baudCombo.setMinimumWidth(140)
        self.baudCombo.addItems(list(SESSION_PAGE_BAUD_RATES))
        self.baudCombo.setCurrentText("921600")
        connLayout.addWidget(self.baudCombo)

        self.refreshButton = PushButton("", connBar)
        connLayout.addWidget(self.refreshButton)
        self.connectButton = PrimaryPushButton("", connBar)
        connLayout.addWidget(self.connectButton)

        self.parseSwitch = SwitchButton(connBar)
        self.parseSwitch.setChecked(True)
        connLayout.addWidget(self.parseSwitch)

        self.stateLabel = BodyLabel(connBar)
        connLayout.addWidget(self.stateLabel)
        connLayout.addStretch(1)
        self.vBoxLayout.addWidget(connBar)

    def _initLogConsole(self):
        self.logEdit = TextEdit(self.scrollWidget)
        self.logEdit.setReadOnly(True)
        self.logEdit.document().setMaximumBlockCount(400)
        self.vBoxLayout.addWidget(self.logEdit, 1)

    def _initModeBar(self):
        modeBar = QWidget(self.scrollWidget)
        modeLayout = QHBoxLayout(modeBar)
        modeLayout.setContentsMargins(0, 0, 0, 0)
        modeLayout.setSpacing(8)

        self.modeLabel = BodyLabel(modeBar)
        modeLayout.addWidget(self.modeLabel)
        self.modeCombo = ComboBox(modeBar)
        self.modeCombo.addItems(list(SESSION_PAGE_SEND_MODES))
        modeLayout.addWidget(self.modeCombo)

        self.rawFmtCombo = ComboBox(modeBar)
        self.rawFmtCombo.addItems(list(SESSION_PAGE_RAW_FORMATS))
        modeLayout.addWidget(self.rawFmtCombo)

        modeLayout.addStretch(1)
        self.vBoxLayout.addWidget(modeBar)

    def _initTlvTable(self):
        self.tlvTable = TableWidget(self.scrollWidget)
        self.tlvTable.setColumnCount(4)
        self.tlvTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tlvTable.setColumnHidden(0, True)
        self.tlvTable.setMinimumHeight(160)
        self.vBoxLayout.addWidget(self.tlvTable)

        tlvBtnBar = QWidget(self.scrollWidget)
        tlvBtnLayout = QHBoxLayout(tlvBtnBar)
        tlvBtnLayout.setContentsMargins(0, 0, 0, 0)
        tlvBtnLayout.setSpacing(8)

        self.addTlvBtn = PushButton("", tlvBtnBar)
        tlvBtnLayout.addWidget(self.addTlvBtn)
        self.delTlvBtn = PushButton("", tlvBtnBar)
        tlvBtnLayout.addWidget(self.delTlvBtn)
        self.exportTlvBtn = PushButton("", tlvBtnBar)
        tlvBtnLayout.addWidget(self.exportTlvBtn)
        self.importTlvBtn = PushButton("", tlvBtnBar)
        tlvBtnLayout.addWidget(self.importTlvBtn)
        tlvBtnLayout.addStretch(1)
        self.vBoxLayout.addWidget(tlvBtnBar)

    def _initSendBar(self):
        sendBar = QWidget(self.scrollWidget)
        sendLayout = QHBoxLayout(sendBar)
        sendLayout.setContentsMargins(0, 0, 0, 0)
        sendLayout.setSpacing(8)

        self.txEdit = LineEdit(sendBar)
        sendLayout.addWidget(self.txEdit, 1)

        self.cmdLabel = BodyLabel("CMD", sendBar)
        sendLayout.addWidget(self.cmdLabel)
        self.cmdSpin = SpinBox(sendBar)
        self.cmdSpin.setRange(0, 255)
        self.cmdSpin.setValue(SESSION_PAGE_V2_DEFAULT_CMD)
        self.cmdSpin.setDisplayIntegerBase(16)
        sendLayout.addWidget(self.cmdSpin)

        self.repeatLabel = BodyLabel(sendBar)
        sendLayout.addWidget(self.repeatLabel)
        self.repeatSpin = SpinBox(sendBar)
        self.repeatSpin.setRange(1, 999)
        self.repeatSpin.setValue(1)
        self.repeatSpin.setFixedWidth(90)
        sendLayout.addWidget(self.repeatSpin)

        self.sendButton = PrimaryPushButton("", sendBar)
        sendLayout.addWidget(self.sendButton)
        self.clearButton = PushButton("", sendBar)
        sendLayout.addWidget(self.clearButton)
        self.vBoxLayout.addWidget(sendBar)

    def _applyTexts(self):
        self.connectionTypeLabel.setText('连接方式')
        self.portLabel.setText('串口')
        self.bluetoothLabel.setText('蓝牙')
        self.baudLabel.setText('波特率')
        self.refreshButton.setText('刷新')
        self.connectButton.setText(
            '连接'
            if not self._session or not self._session.is_open
            else '断开'
        )
        self.parseSwitch.setOnText('解析 TVLCOM')
        self.parseSwitch.setOffText('解析 TVLCOM')
        self.stateLabel.setText(
            '未连接'
            if not self._session or not self._session.is_open
            else '已连接'
        )
        self.logEdit.setPlaceholderText('设备日志 / 返回数据…')
        self.modeLabel.setText('发送模式')
        self.addTlvBtn.setText('新增 TLV')
        self.delTlvBtn.setText('删除 TLV')
        self.exportTlvBtn.setText('导出 JSON')
        self.importTlvBtn.setText('导入 JSON')
        self.txEdit.setPlaceholderText(
            "Raw：输入 HEX（例如 01 0A FF）；TVLCOM_V2 组包后可留空"
        )
        self.repeatLabel.setText('重复')
        self.sendButton.setText('发送')
        self.clearButton.setText('清空')
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
        self.tlvTable.setVisible(isV2)
        self.addTlvBtn.setVisible(isV2)
        self.delTlvBtn.setVisible(isV2)
        self.exportTlvBtn.setVisible(isV2)
        self.importTlvBtn.setVisible(isV2)
        self.rawFmtCombo.setVisible(not isV2)
        self.tlvTable.setHorizontalHeaderLabels(
            ['类型 ID', '类型', '值', '启用']
        )
        self.cmdLabel.setVisible(isV2)
        self.cmdSpin.setVisible(isV2)
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
            color = QColor("red")
        elif lc.startswith("RX(") or lc.startswith("V2 RX"):
            color = QColor("#6ea8fe") if dark else QColor("darkBlue")
        elif (
            lc.startswith("V2 ACK")
            or lc.startswith("V2 NACK")
            or lc.startswith("TX v2")
        ):
            color = QColor("#8bd78f") if dark else QColor("darkGreen")
        elif lc.startswith("Opened") or "Connected" in lc or "Disconnected" in lc:
            color = QColor("#d6b4ff") if dark else QColor("darkMagenta")
        else:
            color = QColor("#ffffff" if dark else "#000000")

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
            try:
                self.logEdit.ensureCursorVisible()
            except Exception:
                pass
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
        self._refreshTexteditColor()

    def _refreshTexteditColor(self):
        palette = self.logEdit.palette()
        palette.setColor(
            self.logEdit.foregroundRole(),
            QColor("#ffffff" if isDarkTheme() else "#000000"),
        )
        self.logEdit.setPalette(palette)

    def _addDefaultTlvRow(self):
        row = self.tlvTable.rowCount()
        self.tlvTable.insertRow(row)

        typeSpin = SpinBox(self.tlvTable)
        typeSpin.setRange(0, 255)
        typeSpin.setValue(SESSION_PAGE_V2_TYPE_ALIAS_TO_ID["string"])
        self.tlvTable.setCellWidget(row, 0, typeSpin)

        kindCombo = ComboBox(self.tlvTable)
        kindCombo.currentTextChanged.connect(
            lambda text, spin=typeSpin: self._syncV2TypeIdWithKind(spin, text)
        )
        self.tlvTable.setCellWidget(row, 1, kindCombo)
        self._configureKindCombo(kindCombo, typeSpin)

        self.tlvTable.setItem(row, 2, QTableWidgetItem(""))

        enable = SwitchButton(self.tlvTable)
        enable.setOnText("启用")
        enable.setOffText("禁用")
        enable.setChecked(True)
        self.tlvTable.setCellWidget(row, 3, enable)

    def _deleteSelectedTlvRows(self):
        for row in sorted(
            {i.row() for i in self.tlvTable.selectedIndexes()}, reverse=True
        ):
            self.tlvTable.removeRow(row)

    def _iterTlvRows(self) -> list[_TlvRow]:
        rows: list[_TlvRow] = []
        for rowIndex in range(self.tlvTable.rowCount()):
            enable = self.tlvTable.cellWidget(rowIndex, 3)
            if isinstance(enable, SwitchButton) and not enable.isChecked():
                continue

            kindCombo = self.tlvTable.cellWidget(rowIndex, 1)
            kind = (
                kindCombo.currentText() if isinstance(kindCombo, ComboBox) else "string"
            )
            typeId = self._v2TypeIdFromKind(kind)
            if typeId is None:
                raise ValueError(f"V2 unsupported type: {kind}")

            valueItem = self.tlvTable.item(rowIndex, 2)
            rows.append(
                _TlvRow(
                    kind=kind,
                    value=valueItem.text() if valueItem else "",
                    typeId=typeId,
                )
            )
        return rows

    def _exportTlvJsonToTx(self):
        self.txEdit.setText(
            json.dumps(
                [row.__dict__ for row in self._iterTlvRows()], ensure_ascii=False
            )
        )

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
            if isinstance(typeSpin, SpinBox):
                typeSpin.setValue(
                    self._v2TypeIdFromKind(kindCombo.currentText()) or typeId
                )

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

    def _configureKindCombo(
        self,
        kindCombo: ComboBox,
        typeSpin: SpinBox,
        preferredKind: str = "",
        preferredTypeId: int = 0,
    ):
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
                    self._configureKindCombo(
                        kindCombo,
                        typeSpin,
                        kindCombo.currentText(),
                        typeSpin.value(),
                    )
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
        self._v2Dispatcher.setAckHandler(
            lambda cmd, seq, payloadData: self.rxEventSignal.emit(
                f"V2 ACK cmd={cmd:02X} seq={seq} [{self._formatV2PayloadItems(payloadData)}]"
            )
        )
        self._v2Dispatcher.setNackHandler(
            lambda cmd, seq, payloadData: self.rxEventSignal.emit(
                f"V2 NACK cmd={cmd:02X} seq={seq} [{self._formatV2PayloadItems(payloadData)}]"
            )
        )

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
            self.rxEventSignal.emit(
                f'V2 RX cmd={frame["cmd"]:02X} seq={frame["seq"]} [{self._formatV2PayloadItems(parsed)}]'
            )

    def _parseRawInput(self, text: str, fmt: str) -> bytes:
        if (fmt or "").upper() == "ASCII":
            return text.encode("utf-8")
        normalized = (
            text.replace("0x", "")
            .replace(",", " ")
            .replace("\n", " ")
            .replace("\r", " ")
            .replace("\t", " ")
        )
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
        if not port:
            self._appendLog(
                "错误: 未找到串口。请先刷新并检查驱动。"
            )
            return

        baud = int(self.baudCombo.currentText().strip())
        self._session = SerialSession(
            SerialConfig(port=port, baudrate=baud), _event_receiver=self
        )

        try:
            self._session.set_event_receiver(self)
        except Exception:
            pass

        self._session.on_tx = lambda data: self._appendLog(
            f'TX({len(data)}): {data.hex(" ")}'
        )
        self._session.on_debug = lambda text: self._appendLog(f"DBG: {text}")
        self._session.on_state = lambda ok: self.stateSignal.emit(ok)

        self._initV2Protocol()

        try:
            self._session.open()
            self._appendLog(
                f"已打开串口: {port} @ {self.baudCombo.currentText().strip()}"
            )
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

    def _safeWrite(self, data: bytes):
        if not self._session or not self._session.is_open:
            return
        try:
            from App.Core.Session.session_serial import SendEvent

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
        self.stateLabel.setText('已连接' if ok else '未连接')
        self.connectButton.setText('断开' if ok else '连接')

    def _onError(self, msg: str):
        self._appendLog(f"错误: {msg}")
        logger.error(msg)

    def _onRxRaw(self, data: bytes):
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
            self._appendLog(f'发送 Raw: ({len(data)}): {data.hex(" ")}')
            return

        try:
            payload = self._buildV2PayloadFromTable()
        except Exception as exc:
            self._appendLog(f"错误: TVLCOM_V2 组包失败: {exc}")
            return

        cmd = self.cmdSpin.value()
        seqs: list[int] = []
        for _ in range(repeat):
            self._v2Seq = (self._v2Seq + 1) % 256
            frame = V2FrameBuilder.buildFrame(cmd, self._v2Seq, payload)
            self._safeWrite(frame)
            seqs.append(self._v2Seq)

        seqText = str(seqs[0]) if len(seqs) == 1 else ",".join(str(seq) for seq in seqs)
        self._appendLog(
            f'TX v2: CMD={cmd:02X} seq={seqText} payload=({len(payload)}) {payload.hex(" ")}'
        )
