# -*- coding: utf-8 -*-
from __future__ import annotations

import binascii
import json
import time
from dataclasses import dataclass
from typing import Any, Optional

from PyQt5.QtCore import QCoreApplication, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt5.QtSerialPort import QSerialPort
from PyQt5.QtWidgets import (
    QHeaderView,
    QHBoxLayout,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
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
    isDarkTheme,
)

from Config import cfg
from app.Core import (
    SESSION_PAGE_BAUD_RATES,
    SESSION_PAGE_RAW_FORMATS,
    SESSION_PAGE_SEND_MODES,
    SESSION_PAGE_V2_DEFAULT_CMD,
    SESSION_PAGE_V2_TYPE_ALIAS_TO_ID,
    SerialConfig,
    SerialEventType,
    SerialSession,
    listSerialPorts,
    logger,
)
from app.TVLCOMV2_FULL import (
    Dispatcher as V2Dispatcher,
    FrameBuilder as V2FrameBuilder,
    FrameParser as V2FrameParser,
)
from app.TVLCOMV2_FULL import Payload as V2Payload, TYPE_REGISTRY
from app.TVLCOMV2_FULL.dataType import DataFloat, DataInt, DataString, TypeBase


@dataclass
class _TlvRow:
    kind: str
    value: str
    typeId: int = 0


class DevicePage(QWidget):
    rxEventSignal = pyqtSignal(str)
    stateSignal = pyqtSignal(bool)
    errSignal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session: Optional[SerialSession] = None
        self._v2Parser: Optional[V2FrameParser] = None
        self._v2Dispatcher: Optional[V2Dispatcher] = None
        self._v2Seq = 0
        self._rxBuf = bytearray()

        self._rxTimer = QTimer(self)
        self._rxTimer.setInterval(60)
        self._rxTimer.timeout.connect(self._flushRx)
        self._rxTimer.start()

        self.setObjectName("DevicePage")

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.vBoxLayout.setSpacing(12)

        self.titleLabel = TitleLabel("TVL COM", self)
        self.vBoxLayout.addWidget(self.titleLabel)

        cfg.themeChanged.connect(self._onThemeChanged)

        self._initConnectionBar()
        self._initLogConsole()
        self._initModeBar()
        self._initTlvTable()
        self._initSendBar()

        self.setStyleSheet("QWidget {background:transparent}")

        self.refreshButton.clicked.connect(self.refreshPorts)
        self.connectButton.clicked.connect(self.toggleConnection)
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
        connBar = QWidget(self)
        connLayout = QHBoxLayout(connBar)
        connLayout.setContentsMargins(0, 0, 0, 0)
        connLayout.setSpacing(8)

        self.portLabel = BodyLabel(connBar)
        connLayout.addWidget(self.portLabel)
        self.portCombo = ComboBox(connBar)
        self.portCombo.setMinimumWidth(160)
        connLayout.addWidget(self.portCombo)

        self.baudLabel = BodyLabel(connBar)
        connLayout.addWidget(self.baudLabel)
        self.baudCombo = ComboBox(connBar)
        self.baudCombo.setMinimumWidth(140)
        self.baudCombo.addItems(list(SESSION_PAGE_BAUD_RATES))
        self.baudCombo.setCurrentText("115200")
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
        self.logEdit = TextEdit(self)
        self.logEdit.setReadOnly(True)
        self.logEdit.document().setMaximumBlockCount(400)
        self.vBoxLayout.addWidget(self.logEdit, 1)

    def _initModeBar(self):
        modeBar = QWidget(self)
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
        self.tlvTable = TableWidget(self)
        self.tlvTable.setColumnCount(4)
        self.tlvTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tlvTable.setColumnHidden(0, True)
        self.tlvTable.setMinimumHeight(160)
        self.vBoxLayout.addWidget(self.tlvTable)

        tlvBtnBar = QWidget(self)
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
        sendBar = QWidget(self)
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
        self.portLabel.setText(self.tr("Port"))
        self.baudLabel.setText(self.tr("Baud rate"))
        self.refreshButton.setText(self.tr("Refresh"))
        self.connectButton.setText(
            self.tr("Connect")
            if not self._session or not self._session.is_open
            else self.tr("Close")
        )
        self.parseSwitch.setOnText(self.tr("Parse TVLCOM"))
        self.parseSwitch.setOffText(self.tr("Parse TVLCOM"))
        self.stateLabel.setText(
            self.tr("Disconnected")
            if not self._session or not self._session.is_open
            else self.tr("Connected")
        )
        self.logEdit.setPlaceholderText(self.tr("Device log / returned data..."))
        self.modeLabel.setText(self.tr("Send mode"))
        self.addTlvBtn.setText(self.tr("Add TLV"))
        self.delTlvBtn.setText(self.tr("Delete TLV"))
        self.exportTlvBtn.setText(self.tr("Export JSON"))
        self.importTlvBtn.setText(self.tr("Import JSON"))
        self.txEdit.setPlaceholderText(
            self.tr(
                "Raw: enter HEX (for example 01 0A FF); V2 can be left empty after composing TLV"
            )
        )
        self.repeatLabel.setText(self.tr("Repeat"))
        self.sendButton.setText(self.tr("Send"))
        self.clearButton.setText(self.tr("Clear"))
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
            [self.tr("Type ID"), self.tr("Type"), self.tr("Value"), self.tr("Enable")]
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
        if lc.startswith("ERR:"):
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
        enable.setOnText("ON")
        enable.setOffText("OFF")
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
        self._appendLog(f"Ports: {ports}")
        current = self.portCombo.currentText().strip()
        self.portCombo.clear()
        if ports:
            self.portCombo.addItems(ports)
            if current in ports:
                self.portCombo.setCurrentText(current)

    def toggleConnection(self):
        if self._session and self._session.is_open:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        port = self.portCombo.currentText().strip()
        if not port:
            self._appendLog(
                "ERR: No serial port found. Refresh first and check the driver."
            )
            return

        baudMap = {
            9600: QSerialPort.BaudRate.Baud9600,
            19200: QSerialPort.BaudRate.Baud19200,
            38400: QSerialPort.BaudRate.Baud38400,
            57600: QSerialPort.BaudRate.Baud57600,
            115200: QSerialPort.BaudRate.Baud115200,
        }
        baud = baudMap.get(
            int(self.baudCombo.currentText().strip()), QSerialPort.BaudRate.Baud9600
        )
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
                f"Opened serial port: {port} @ {self.baudCombo.currentText().strip()}"
            )
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
            from app.Core.Session.session_serial import SendEvent

            QCoreApplication.postEvent(self._session, SendEvent(data))
        except Exception:
            try:
                self._session.write(data)
            except Exception as exc:
                self.errSignal.emit(str(exc))

    def _onState(self, ok: bool):
        self.stateLabel.setText(self.tr("Connected") if ok else self.tr("Disconnected"))
        self.connectButton.setText(self.tr("Close") if ok else self.tr("Connect"))

    def _onError(self, msg: str):
        self._appendLog(f"ERR: {msg}")
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
            self._appendLog("ERR: Serial port is not connected")
            return

        repeat = int(self.repeatSpin.value())
        if not self._isV2Mode():
            raw = self.txEdit.text().strip()
            if not raw:
                return
            try:
                data = self._parseRawInput(raw, self.rawFmtCombo.currentText())
            except Exception as exc:
                self._appendLog(f"ERR: Raw parse failed: {exc}")
                return
            for _ in range(repeat):
                self._safeWrite(data)
            self._appendLog(f'TX raw: ({len(data)}): {data.hex(" ")}')
            return

        try:
            payload = self._buildV2PayloadFromTable()
        except Exception as exc:
            self._appendLog(f"ERR: V2 build failed: {exc}")
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
