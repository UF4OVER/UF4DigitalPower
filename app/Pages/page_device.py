# -*- coding: utf-8 -*-
from __future__ import annotations

import binascii
import json
import time
from dataclasses import dataclass
from typing import Any, Optional

from PyQt5.QtCore import QCoreApplication, QEvent, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt5.QtSerialPort import QSerialPort
from PyQt5.QtWidgets import QHeaderView, QHBoxLayout, QTableWidgetItem, QVBoxLayout, QWidget
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
from app.TVLCOMV2_FULL import Dispatcher as V2Dispatcher, FrameBuilder as V2FrameBuilder, FrameParser as V2FrameParser
from app.TVLCOMV2_FULL import Payload as V2Payload, TYPE_REGISTRY
from app.TVLCOMV2_FULL.dataType import DataFloat, DataInt, DataString, TypeBase


@dataclass
class _TlvRow:
    kind: str
    value: str
    type_id: int = 0


class DevicePage(QWidget):
    rxEventSignal = pyqtSignal(str)
    stateSignal = pyqtSignal(bool)
    errSignal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session: Optional[SerialSession] = None
        self._v2_parser: Optional[V2FrameParser] = None
        self._v2_dispatcher: Optional[V2Dispatcher] = None
        self._v2_seq = 0
        self._rx_buf = bytearray()

        self._rx_timer = QTimer(self)
        self._rx_timer.setInterval(60)
        self._rx_timer.timeout.connect(self._flush_rx)
        self._rx_timer.start()

        self.setObjectName("DevicePage")

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.vBoxLayout.setSpacing(12)

        self.titleLabel = TitleLabel("TVL COM", self)
        self.vBoxLayout.addWidget(self.titleLabel)

        cfg.themeChanged.connect(self._on_theme_changed)

        self._init_connection_bar()
        self._init_log_console()
        self._init_mode_bar()
        self._init_tlv_table()
        self._init_send_bar()

        self.setStyleSheet("QWidget {background:transparent}")

        self.refreshButton.clicked.connect(self.refresh_ports)
        self.connectButton.clicked.connect(self.toggle_connection)
        self.sendButton.clicked.connect(self.on_send)
        self.clearButton.clicked.connect(lambda: self.logEdit.setPlainText(""))
        self.modeCombo.currentIndexChanged.connect(self._apply_mode)
        self.addTlvBtn.clicked.connect(self._add_default_tlv_row)
        self.delTlvBtn.clicked.connect(self._delete_selected_tlv_rows)
        self.exportTlvBtn.clicked.connect(self._export_tlv_json_to_tx)
        self.importTlvBtn.clicked.connect(self._import_tlv_json_from_tx)
        self.rxEventSignal.connect(self._append_log)
        self.stateSignal.connect(self._on_state)
        self.errSignal.connect(self._on_error)

        self._retranslate_ui()
        self.refresh_ports()
        self._apply_mode()

    def _init_connection_bar(self):
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

    def _init_log_console(self):
        self.logEdit = TextEdit(self)
        self.logEdit.setReadOnly(True)
        self.logEdit.document().setMaximumBlockCount(400)
        self.vBoxLayout.addWidget(self.logEdit, 1)

    def _init_mode_bar(self):
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

    def _init_tlv_table(self):
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

    def _init_send_bar(self):
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

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.LanguageChange:
            self._retranslate_ui()

    def _retranslate_ui(self):
        self.portLabel.setText(self.tr("Port"))
        self.baudLabel.setText(self.tr("Baud rate"))
        self.refreshButton.setText(self.tr("Refresh"))
        self.connectButton.setText(self.tr("Connect") if not self._session or not self._session.is_open else self.tr("Close"))
        self.parseSwitch.setOnText(self.tr("Parse TVLCOM"))
        self.parseSwitch.setOffText(self.tr("Parse TVLCOM"))
        self.stateLabel.setText(self.tr("Disconnected") if not self._session or not self._session.is_open else self.tr("Connected"))
        self.logEdit.setPlaceholderText(self.tr("Device log / returned data..."))
        self.modeLabel.setText(self.tr("Send mode"))
        self.addTlvBtn.setText(self.tr("Add TLV"))
        self.delTlvBtn.setText(self.tr("Delete TLV"))
        self.exportTlvBtn.setText(self.tr("Export JSON"))
        self.importTlvBtn.setText(self.tr("Import JSON"))
        self.txEdit.setPlaceholderText(self.tr("Raw: enter HEX (for example 01 0A FF); V2 can be left empty after composing TLV"))
        self.repeatLabel.setText(self.tr("Repeat"))
        self.sendButton.setText(self.tr("Send"))
        self.clearButton.setText(self.tr("Clear"))
        self._apply_mode()

    def event(self, e):
        if e.type() == SerialEventType.RX:
            data = e.payload.data
            if data:
                try:
                    self._on_rx_raw(data)
                except Exception as exc:
                    logger.error(exc)
            return True
        return super().event(e)

    def _is_v2_mode(self) -> bool:
        return self.modeCombo.currentIndex() == 1

    def _apply_mode(self):
        is_v2 = self._is_v2_mode()
        self.tlvTable.setVisible(is_v2)
        self.addTlvBtn.setVisible(is_v2)
        self.delTlvBtn.setVisible(is_v2)
        self.exportTlvBtn.setVisible(is_v2)
        self.importTlvBtn.setVisible(is_v2)
        self.rawFmtCombo.setVisible(not is_v2)
        self.tlvTable.setHorizontalHeaderLabels([self.tr("Type ID"), self.tr("Type"), self.tr("Value"), self.tr("Enable")])
        self.cmdLabel.setVisible(is_v2)
        self.cmdSpin.setVisible(is_v2)
        self._refresh_tlv_row_editors_for_mode()

    def _append_log(self, text: str):
        ts = time.strftime("%H:%M:%S")
        msg = f"[{ts}] {text}"
        if not (text.startswith("RX(") or text.startswith("TX(") or text.startswith("V2 RX") or text.startswith("V2 ACK") or text.startswith("V2 NACK")):
            logger.info(text)

        lc = text.strip()
        dark = isDarkTheme()
        if lc.startswith("ERR:"):
            color = QColor("red")
        elif lc.startswith("RX(") or lc.startswith("V2 RX"):
            color = QColor("#6ea8fe") if dark else QColor("darkBlue")
        elif lc.startswith("V2 ACK") or lc.startswith("V2 NACK") or lc.startswith("TX v2"):
            color = QColor("#8bd78f") if dark else QColor("darkGreen")
        elif lc.startswith("Opened") or "Connected" in lc or "Disconnected" in lc:
            color = QColor("#d6b4ff") if dark else QColor("darkMagenta")
        else:
            color = QColor("#ffffff" if dark else "#000000")

        self._append_colored(msg + "\n", color)

    def _append_colored(self, text: str, color: QColor):
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
        self._refresh_textedit_color()

    def _flush_rx(self):
        if not self._rx_buf:
            return
        data = bytes(self._rx_buf)
        self._rx_buf.clear()
        self._append_log(f'RX({len(data)}): {data.hex(" ")}')

    def _on_theme_changed(self, *_):
        self._refresh_textedit_color()

    def _refresh_textedit_color(self):
        palette = self.logEdit.palette()
        palette.setColor(self.logEdit.foregroundRole(), QColor("#ffffff" if isDarkTheme() else "#000000"))
        self.logEdit.setPalette(palette)

    def _add_default_tlv_row(self):
        row = self.tlvTable.rowCount()
        self.tlvTable.insertRow(row)

        typeSpin = SpinBox(self.tlvTable)
        typeSpin.setRange(0, 255)
        typeSpin.setValue(SESSION_PAGE_V2_TYPE_ALIAS_TO_ID["string"])
        self.tlvTable.setCellWidget(row, 0, typeSpin)

        kindCombo = ComboBox(self.tlvTable)
        kindCombo.currentTextChanged.connect(lambda text, spin=typeSpin: self._sync_v2_type_id_with_kind(spin, text))
        self.tlvTable.setCellWidget(row, 1, kindCombo)
        self._configure_kind_combo(kindCombo, typeSpin)

        self.tlvTable.setItem(row, 2, QTableWidgetItem(""))

        enable = SwitchButton(self.tlvTable)
        enable.setOnText("ON")
        enable.setOffText("OFF")
        enable.setChecked(True)
        self.tlvTable.setCellWidget(row, 3, enable)

    def _delete_selected_tlv_rows(self):
        for row in sorted({i.row() for i in self.tlvTable.selectedIndexes()}, reverse=True):
            self.tlvTable.removeRow(row)

    def _iter_tlv_rows(self) -> list[_TlvRow]:
        rows: list[_TlvRow] = []
        for row_index in range(self.tlvTable.rowCount()):
            enable = self.tlvTable.cellWidget(row_index, 3)
            if isinstance(enable, SwitchButton) and not enable.isChecked():
                continue

            kind_combo = self.tlvTable.cellWidget(row_index, 1)
            kind = kind_combo.currentText() if isinstance(kind_combo, ComboBox) else "string"
            type_id = self._v2_type_id_from_kind(kind)
            if type_id is None:
                raise ValueError(f"V2 unsupported type: {kind}")

            value_item = self.tlvTable.item(row_index, 2)
            rows.append(_TlvRow(kind=kind, value=value_item.text() if value_item else "", type_id=type_id))
        return rows

    def _export_tlv_json_to_tx(self):
        self.txEdit.setText(json.dumps([row.__dict__ for row in self._iter_tlv_rows()], ensure_ascii=False))

    def _import_tlv_json_from_tx(self):
        raw = self.txEdit.text().strip()
        if not raw:
            return

        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("JSON must be a list")

        self.tlvTable.setRowCount(0)
        for item in data:
            type_id = int(item.get("type_id", 0))
            kind = str(item.get("kind", "string"))
            value = str(item.get("value", ""))

            self._add_default_tlv_row()
            row = self.tlvTable.rowCount() - 1
            type_spin = self.tlvTable.cellWidget(row, 0)
            kind_combo = self.tlvTable.cellWidget(row, 1)

            if isinstance(kind_combo, ComboBox):
                kind_combo.setCurrentText(self._normalize_v2_kind(kind, type_id))
            if isinstance(type_spin, SpinBox):
                type_spin.setValue(self._v2_type_id_from_kind(kind_combo.currentText()) or type_id)

            self.tlvTable.setItem(row, 2, QTableWidgetItem(value))
            enable = self.tlvTable.cellWidget(row, 3)
            if isinstance(enable, SwitchButton):
                enable.setChecked(True)

    def _v2_type_ids(self) -> list[int]:
        return sorted(TYPE_REGISTRY)

    def _v2_selector_options(self) -> list[str]:
        return [self._v2_type_name(type_id) for type_id in self._v2_type_ids()]

    def _default_v2_selector(self) -> str:
        options = self._v2_selector_options()
        return "string" if "string" in options else (options[0] if options else "")

    def _v2_type_id_from_kind(self, kind: str) -> Optional[int]:
        type_id = SESSION_PAGE_V2_TYPE_ALIAS_TO_ID.get((kind or "").strip().lower())
        return type_id if type_id in TYPE_REGISTRY else None

    def _normalize_v2_kind(self, kind: str, type_id: int = 0) -> str:
        resolved_type_id = self._v2_type_id_from_kind(kind)
        if resolved_type_id is None and type_id in TYPE_REGISTRY:
            resolved_type_id = type_id
        if resolved_type_id is None:
            raise ValueError(f"V2 unsupported type: {kind or type_id}")
        return self._v2_type_name(resolved_type_id)

    def _configure_kind_combo(self, kind_combo: ComboBox, type_spin: SpinBox, preferred_kind: str = "", preferred_type_id: int = 0):
        kind_combo.blockSignals(True)
        kind_combo.clear()
        options = self._v2_selector_options()
        kind_combo.addItems(options)

        selected = self._default_v2_selector()
        if options:
            try:
                selected = self._normalize_v2_kind(preferred_kind, preferred_type_id)
            except ValueError:
                pass

        if selected:
            kind_combo.setCurrentText(selected)
            self._sync_v2_type_id_with_kind(type_spin, selected)

        kind_combo.blockSignals(False)

    def _refresh_tlv_row_editors_for_mode(self):
        for row in range(self.tlvTable.rowCount()):
            type_spin = self.tlvTable.cellWidget(row, 0)
            kind_combo = self.tlvTable.cellWidget(row, 1)
            if isinstance(type_spin, SpinBox) and isinstance(kind_combo, ComboBox):
                try:
                    self._configure_kind_combo(kind_combo, type_spin, kind_combo.currentText(), type_spin.value())
                except ValueError:
                    self._configure_kind_combo(kind_combo, type_spin)

    def _build_v2_payload_from_table(self) -> bytes:
        payload = V2Payload()
        for row in self._iter_tlv_rows():
            type_obj = TYPE_REGISTRY.get(int(row.type_id) & 0xFF)
            if type_obj is None:
                raise ValueError(f"V2 unsupported type ID: 0x{row.type_id:02X}")
            payload.addData(type_obj, self._coerce_v2_value(row, type_obj))
        return payload.toBytes()

    def _sync_v2_type_id_with_kind(self, type_spin: SpinBox, kind: str):
        suggested = self._v2_type_id_from_kind(kind)
        if suggested is not None:
            type_spin.setValue(suggested)

    def _coerce_v2_value(self, row: _TlvRow, type_obj: TypeBase):
        raw_value = row.value.strip()
        if isinstance(type_obj, DataString):
            return row.value
        if isinstance(type_obj, DataFloat):
            return float(raw_value or "0")
        if isinstance(type_obj, DataInt):
            return int(raw_value or "0", 0)
        raise ValueError(f"V2 unsupported value type: {row.kind}")

    def _reset_v2_protocol(self):
        self._v2_parser = None
        self._v2_dispatcher = None
        self._v2_seq = 0

    def _init_v2_protocol(self):
        self._v2_parser = V2FrameParser()
        self._v2_dispatcher = V2Dispatcher()
        self._v2_dispatcher.setAckHandler(
            lambda cmd, seq, payload_data: self.rxEventSignal.emit(
                f"V2 ACK cmd={cmd:02X} seq={seq} [{self._format_v2_payload_items(payload_data)}]"
            )
        )
        self._v2_dispatcher.setNackHandler(
            lambda cmd, seq, payload_data: self.rxEventSignal.emit(
                f"V2 NACK cmd={cmd:02X} seq={seq} [{self._format_v2_payload_items(payload_data)}]"
            )
        )

    def _v2_type_name(self, type_id: int) -> str:
        type_obj = TYPE_REGISTRY.get(type_id)
        if type_obj is None:
            return "bytes"
        if isinstance(type_obj, DataString):
            return "string"
        if isinstance(type_obj, DataFloat):
            return "float"
        return getattr(type_obj, "name", type_obj.__class__.__name__)

    def _format_v2_payload_items(self, payload_data: dict[int, Any]) -> str:
        if not payload_data:
            return ""
        parts = []
        for type_id, value in payload_data.items():
            rendered = value.hex(" ") if isinstance(value, bytes) else value
            parts.append(f"T{type_id:02X}({self._v2_type_name(type_id)}):{rendered}")
        return ", ".join(parts)

    def _handle_v2_rx_frames(self, data: bytes):
        if self._v2_parser is None:
            return
        for frame in self._v2_parser.inputBytes(data):
            if self._v2_dispatcher is not None and self._v2_dispatcher.dispatch(frame):
                continue
            parsed = V2Payload.parse(frame["payload"])
            self.rxEventSignal.emit(
                f'V2 RX cmd={frame["cmd"]:02X} seq={frame["seq"]} [{self._format_v2_payload_items(parsed)}]'
            )

    def _parse_raw_input(self, text: str, fmt: str) -> bytes:
        if (fmt or "").upper() == "ASCII":
            return text.encode("utf-8")
        normalized = text.replace("0x", "").replace(",", " ").replace("\n", " ").replace("\r", " ").replace("\t", " ")
        hexstr = "".join(ch for ch in normalized if ch != " ")
        if len(hexstr) % 2 != 0:
            raise ValueError("HEX length must be even")
        return binascii.unhexlify(hexstr)

    def refresh_ports(self):
        ports = [p.strip() for p in (listSerialPorts() or []) if p and p.strip()]
        self._append_log(f"Ports: {ports}")
        current = self.portCombo.currentText().strip()
        self.portCombo.clear()
        if ports:
            self.portCombo.addItems(ports)
            if current in ports:
                self.portCombo.setCurrentText(current)

    def toggle_connection(self):
        if self._session and self._session.is_open:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        port = self.portCombo.currentText().strip()
        if not port:
            self._append_log("ERR: No serial port found. Refresh first and check the driver.")
            return

        baud_map = {
            9600: QSerialPort.BaudRate.Baud9600,
            19200: QSerialPort.BaudRate.Baud19200,
            38400: QSerialPort.BaudRate.Baud38400,
            57600: QSerialPort.BaudRate.Baud57600,
            115200: QSerialPort.BaudRate.Baud115200,
        }
        baud = baud_map.get(int(self.baudCombo.currentText().strip()), QSerialPort.BaudRate.Baud9600)
        self._session = SerialSession(SerialConfig(port=port, baudrate=baud), _event_receiver=self)

        try:
            self._session.set_event_receiver(self)
        except Exception:
            pass

        self._session.on_tx = lambda data: self._append_log(f'TX({len(data)}): {data.hex(" ")}')
        self._session.on_debug = lambda text: self._append_log(f"DBG: {text}")
        self._session.on_state = lambda ok: self.stateSignal.emit(ok)

        self._init_v2_protocol()

        try:
            self._session.open()
            self._append_log(f"Opened serial port: {port} @ {self.baudCombo.currentText().strip()}")
        except Exception as exc:
            self._on_error(str(exc))
            self._session = None
            self._reset_v2_protocol()

    def _disconnect(self):
        try:
            if self._session:
                self._session.close()
        finally:
            self._session = None
            self._reset_v2_protocol()
            self._append_log("Disconnected")
            self._retranslate_ui()

    def _safe_write(self, data: bytes):
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

    def _on_state(self, ok: bool):
        self.stateLabel.setText(self.tr("Connected") if ok else self.tr("Disconnected"))
        self.connectButton.setText(self.tr("Close") if ok else self.tr("Connect"))

    def _on_error(self, msg: str):
        self._append_log(f"ERR: {msg}")
        logger.error(msg)

    def _on_rx_raw(self, data: bytes):
        self._rx_buf.extend(data)
        if self.parseSwitch.isChecked() and self._v2_parser is not None:
            try:
                self._handle_v2_rx_frames(data)
            except Exception as exc:
                self.errSignal.emit(f"TVLCOMV2_FULL feed failed: {exc}")

    def on_send(self):
        if not self._session or not self._session.is_open:
            self._append_log("ERR: Serial port is not connected")
            return

        repeat = int(self.repeatSpin.value())
        if not self._is_v2_mode():
            raw = self.txEdit.text().strip()
            if not raw:
                return
            try:
                data = self._parse_raw_input(raw, self.rawFmtCombo.currentText())
            except Exception as exc:
                self._append_log(f"ERR: Raw parse failed: {exc}")
                return
            for _ in range(repeat):
                self._safe_write(data)
            self._append_log(f'TX raw: ({len(data)}): {data.hex(" ")}')
            return

        try:
            payload = self._build_v2_payload_from_table()
        except Exception as exc:
            self._append_log(f"ERR: V2 build failed: {exc}")
            return

        cmd = self.cmdSpin.value()
        seqs: list[int] = []
        for _ in range(repeat):
            self._v2_seq = (self._v2_seq + 1) % 256
            frame = V2FrameBuilder.buildFrame(cmd, self._v2_seq, payload)
            self._safe_write(frame)
            seqs.append(self._v2_seq)

        seq_text = str(seqs[0]) if len(seqs) == 1 else ",".join(str(seq) for seq in seqs)
        self._append_log(f'TX v2: CMD={cmd:02X} seq={seq_text} payload=({len(payload)}) {payload.hex(" ")}')
