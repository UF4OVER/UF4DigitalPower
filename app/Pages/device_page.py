# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 04-12 13:15
#  @FileName: device_page.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : Powered By GPT-5.4
#  @Python  :
# -------------------------------


"""Device page (下位机界面)

Serial console for device connection/control.

Features:
- Serial port scan / connect / disconnect (pyserial)
- RX display (raw bytes), optional TVLCOMV1_FULL parsing events
- TX modes:
  - Raw: HEX/ASCII
  - TVLCOMV1_FULL: compose payload from TLV fields then Protocol.send_payload()
  - TVLCOMV2_FULL: compose payload from TLV fields with CMD header then send as frame
"""

from __future__ import annotations

import binascii
import json
import struct
import time
from dataclasses import dataclass
from typing import Any, Optional

from PyQt5.QtCore import QTimer, pyqtSignal, QCoreApplication
from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt5.QtSerialPort import QSerialPort
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidgetItem,
    QHeaderView,
)

from app import StyleSheet
from app.Core import SerialConfig, SerialSession, SerialEventType, listSerialPorts
from app.Core import logger

from app.TVLCOMV1_FULL import const as tvl_const
from app.TVLCOMV1_FULL.protocol import Protocol
from app.TVLCOMV1_FULL.tlv import tlv_encode

from app.TVLCOMV2_FULL import Dispatcher as V2Dispatcher, FrameBuilder as V2FrameBuilder, FrameParser as V2FrameParser
from app.TVLCOMV2_FULL import Payload as V2Payload, TYPE_REGISTRY
from app.TVLCOMV2_FULL.dataType import DataFloat, DataInt, DataString, TypeBase

from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    LineEdit,
    TextEdit,
    PrimaryPushButton,
    PushButton,
    SpinBox,
    SwitchButton,
    TitleLabel,
    TableWidget
)
from qfluentwidgets import isDarkTheme

from Config import AppIconPath, cfg

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
        self._proto: Optional[Protocol] = None
        self._v2_parser: Optional[V2FrameParser] = None
        self._v2_dispatcher: Optional[V2Dispatcher] = None
        self._v2_seq = 0

        self._rx_buf = bytearray()
        self._rx_timer = QTimer(self)
        self._rx_timer.setInterval(60)
        self._rx_timer.timeout.connect(self._flush_rx)
        self._rx_timer.start()

        self.setObjectName("DevicePage")  # 主题设置
        # StyleSheet.DEVICE_PAGE.apply(self)

        self.vBoxLayout = QVBoxLayout(self)
        m = 24
        self.vBoxLayout.setContentsMargins(m, m, m, m)
        self.vBoxLayout.setSpacing(12)

        self.titleLabel = TitleLabel('TVL COM', self)
        self.vBoxLayout.addWidget(self.titleLabel)

        cfg.themeChanged.connect(self._on_theme_changed)
        # ---- Connection bar ----
        connBar = QWidget(self)  # NOQA 变量名不规范，但符合语义
        connLayout = QHBoxLayout(connBar)  # NOQA 变量名不规范，但符合语义
        connLayout.setContentsMargins(0, 0, 0, 0)
        connLayout.setSpacing(8)

        portLabel = BodyLabel('端口', connBar)  # NOQA 变量名不规范，但符合语义
        connLayout.addWidget(portLabel)
        self.portCombo = ComboBox(connBar)
        self.portCombo.setMinimumWidth(160)
        connLayout.addWidget(self.portCombo)

        baudLabel = BodyLabel('波特率', connBar)  # NOQA 变量名不规范，但符合语义
        connLayout.addWidget(baudLabel)
        self.baudCombo = ComboBox(connBar)
        self.baudCombo.setMinimumWidth(140)
        self.baudCombo.addItems(['9600', '19200', '38400', '57600', '115200'])
        self.baudCombo.setCurrentText('115200')
        connLayout.addWidget(self.baudCombo)

        self.refreshButton = PushButton('刷新', connBar)
        connLayout.addWidget(self.refreshButton)

        self.connectButton = PrimaryPushButton('连接', connBar)
        connLayout.addWidget(self.connectButton)

        self.parseSwitch = SwitchButton(connBar)
        self.parseSwitch.setOnText('解析TVLCOM')
        self.parseSwitch.setOffText('解析TVLCOM')
        self.parseSwitch.setChecked(True)
        connLayout.addWidget(self.parseSwitch)

        self.stateLabel = BodyLabel('未连接', connBar)
        connLayout.addWidget(self.stateLabel)

        connLayout.addStretch(1)
        self.vBoxLayout.addWidget(connBar)

        # ---- Log console ----
        self.logEdit = TextEdit(self)
        self.logEdit.setPlaceholderText('设备日志/返回数据…')
        self.logEdit.setReadOnly(True)
        self.vBoxLayout.addWidget(self.logEdit, 1)

        # ---- Send mode bar ----
        modeBar = QWidget(self)  # NOQA 变量名不规范，但符合语义
        modeLayout = QHBoxLayout(modeBar)  # NOQA 变量名不规范，但符合语义
        modeLayout.setContentsMargins(0, 0, 0, 0)
        modeLayout.setSpacing(8)

        modeLabel = BodyLabel('发送模式', modeBar)  # NOQA 函数中的变量应小写
        modeLayout.addWidget(modeLabel)
        self.modeCombo = ComboBox(modeBar)
        self.modeCombo.addItems(['Raw(HEX/ASCII)', 'TVLCOM_V1', 'TVLCOM_V2'])  # NOQA
        modeLayout.addWidget(self.modeCombo)

        self.rawFmtCombo = ComboBox(modeBar)
        self.rawFmtCombo.addItems(['HEX', 'ASCII'])
        modeLayout.addWidget(self.rawFmtCombo)

        self.ackSwitch = SwitchButton(modeBar)
        self.ackSwitch.setOnText('应答')
        self.ackSwitch.setOffText('应答')
        self.ackSwitch.setChecked(True)
        modeLayout.addWidget(self.ackSwitch)

        modeLayout.addStretch(1)
        self.vBoxLayout.addWidget(modeBar)

        # ---- TLV table ----
        self.tlvTable = TableWidget(self)
        self.tlvTable.setColumnCount(4)
        self.tlvTable.setHorizontalHeaderLabels(['Type ID', 'Kind', 'Value', 'Enable'])
        self.tlvTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tlvTable.setColumnHidden(0, True)
        self.tlvTable.setMinimumHeight(160)
        self.vBoxLayout.addWidget(self.tlvTable)

        tlvBtnBar = QWidget(self)  # NOQA 变量名不规范，但符合语义
        tlvBtnLayout = QHBoxLayout(tlvBtnBar)  # NOQA 变量名不规范，但符合语义
        tlvBtnLayout.setContentsMargins(0, 0, 0, 0)
        tlvBtnLayout.setSpacing(8)

        self.addTlvBtn = PushButton('新增TLV', tlvBtnBar)
        tlvBtnLayout.addWidget(self.addTlvBtn)
        self.delTlvBtn = PushButton('删除TLV', tlvBtnBar)
        tlvBtnLayout.addWidget(self.delTlvBtn)
        self.exportTlvBtn = PushButton('导出JSON', tlvBtnBar)
        tlvBtnLayout.addWidget(self.exportTlvBtn)
        self.importTlvBtn = PushButton('导入JSON', tlvBtnBar)
        tlvBtnLayout.addWidget(self.importTlvBtn)
        tlvBtnLayout.addStretch(1)
        self.vBoxLayout.addWidget(tlvBtnBar)

        # ---- Send bar ----
        sendBar = QWidget(self)  # NOQA 名称不规范
        sendLayout = QHBoxLayout(sendBar)  # NOQA 名称不规范
        sendLayout.setContentsMargins(0, 0, 0, 0)
        sendLayout.setSpacing(8)

        self.txEdit = LineEdit(sendBar)
        self.txEdit.setPlaceholderText('Raw: 输入HEX(如 01 0A FF); V1/V2: 组包可留空')
        sendLayout.addWidget(self.txEdit, 1)

        self.cmdLabel = BodyLabel('CMD', sendBar)
        sendLayout.addWidget(self.cmdLabel)

        self.cmdSpin = SpinBox(sendBar)
        self.cmdSpin.setRange(0, 255)
        self.cmdSpin.setValue(0x01)
        self.cmdSpin.setDisplayIntegerBase(16)
        sendLayout.addWidget(self.cmdSpin)

        repeatLabel = BodyLabel('重复', sendBar)  # NOQA 名称不规范
        sendLayout.addWidget(repeatLabel)

        self.repeatSpin = SpinBox(sendBar)
        self.repeatSpin.setRange(1, 999)
        self.repeatSpin.setValue(1)
        self.repeatSpin.setFixedWidth(90)
        sendLayout.addWidget(self.repeatSpin)

        self.sendButton = PrimaryPushButton('发送', sendBar)
        sendLayout.addWidget(self.sendButton)

        self.clearButton = PushButton('清空', sendBar)
        sendLayout.addWidget(self.clearButton)

        self.vBoxLayout.addWidget(sendBar)

        self.setStyleSheet('QWidget {background:transparent}')
        self.setObjectName('DevicePage')
        # StyleSheet.DEVICE_PAGE.apply(self)

        # signals
        self.refreshButton.clicked.connect(self.refresh_ports)
        self.connectButton.clicked.connect(self.toggle_connection)
        self.sendButton.clicked.connect(self.on_send)
        self.clearButton.clicked.connect(lambda: self.logEdit.setPlainText(''))

        self.modeCombo.currentIndexChanged.connect(self._apply_mode)
        # 将 TLV 按钮连接到其处理程序
        self.addTlvBtn.clicked.connect(self._add_default_tlv_row)
        self.delTlvBtn.clicked.connect(self._delete_selected_tlv_rows)
        self.exportTlvBtn.clicked.connect(self._export_tlv_json_to_tx)
        self.importTlvBtn.clicked.connect(self._import_tlv_json_from_tx)

        self.rxEventSignal.connect(self._append_log)
        self.stateSignal.connect(self._on_state)
        self.errSignal.connect(self._on_error)

        self.refresh_ports()
        self._apply_mode()

    def event(self, e):
        # 处理从 SerialSession 发布的 RxEvent
        match e.type():
            case SerialEventType.RX:
                data = e.payload.data
                if data:
                    try:
                        self._on_rx_raw(data)
                    except Exception as e:
                        logger.error(e)
                return True

        return super().event(e)

    # ---------------- UI helpers ----------------
    def _apply_mode(self):
        idx = self.modeCombo.currentIndex()
        is_tvl = idx in [1, 2]
        is_v2 = idx == 2
        self.tlvTable.setVisible(is_tvl)
        self.addTlvBtn.setVisible(is_tvl)
        self.delTlvBtn.setVisible(is_tvl)
        self.exportTlvBtn.setVisible(is_tvl)
        self.importTlvBtn.setVisible(is_tvl)
        self.rawFmtCombo.setVisible(not is_tvl)
        self.ackSwitch.setVisible(idx == 1)

        self.tlvTable.setHorizontalHeaderLabels(['Type ID', 'Type' if is_v2 else 'Kind', 'Value', 'Enable'])
        self.tlvTable.setColumnHidden(0, True)
        if hasattr(self, 'cmdLabel'):
            self.cmdLabel.setVisible(is_v2)
        if hasattr(self, 'cmdSpin'):
            self.cmdSpin.setVisible(is_v2)
        self._refresh_tlv_row_editors_for_mode()

    def _append_log(self, text: str):
        ts = time.strftime('%H:%M:%S')
        msg = f'[{ts}] {text}'

        logger.info(text)

        # choose color based on message content/type
        lc = text.strip()
        # Theme-aware color defaults: pick readable colors depending on theme
        dark = isDarkTheme()
        if lc.startswith('ERR:'):
            color = QColor('red')
        elif lc.startswith('RX(') or lc.startswith('V2 RX'):
            color = QColor('#6ea8fe') if dark else QColor('darkBlue')
        elif lc.startswith('TLV') or 'TLV seq=' in lc or lc.startswith('TX tvl') or lc.startswith('TX v2'):
            color = QColor('#8bd78f') if dark else QColor('darkGreen')
        elif lc.startswith('Opened') or 'Connected' in lc or 'Disconnected' in lc:
            color = QColor('#d6b4ff') if dark else QColor('darkMagenta')
        else:
            color = QColor('#ffffff' if dark else '#000000')

        self._append_colored(msg + '\n', color)

    def _append_colored(self, text: str, color: QColor):
        """Append text to the PlainTextEdit with the given color using QTextCursor.

        这适用于 QTextEdit 和 QPlainTextEdit 支持的公开的小部件
        textCursor()/setTextCursor()/ensureCursorVisible()。
        纯文本编辑自QFluentwidgets 是一个薄包装器并支持这些方法。
        """
        try:
            cursor: QTextCursor = self.logEdit.textCursor()
            cursor.movePosition(QTextCursor.End)
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
            # keep caret at end and ensure visible
            self.logEdit.setTextCursor(cursor)
            try:
                self.logEdit.ensureCursorVisible()
            except Exception:  # NOQA 异常子句过于宽泛
                # Some plain wrappers might not implement ensureCursorVisible
                pass
        except Exception:  # NOQA 异常子句过于宽泛
            # fallback to plain append if anything goes wrong
            try:
                self.logEdit.appendPlainText(text.rstrip('\n'))
            except Exception:  # NOQA 异常子句过于宽泛
                pass
        # 每次插入时刷新颜色，防止主题切换后残留
        self._refresh_textedit_color()

    def _flush_rx(self):
        if not self._rx_buf:
            return
        data = bytes(self._rx_buf)
        self._rx_buf.clear()
        self._append_log(f'RX({len(data)}): {data.hex(" ")}')

    def _on_theme_changed(self, theme):
        self._refresh_textedit_color()

    def _refresh_textedit_color(self):
        # 根据当前主题设置logEdit文字颜色
        from qfluentwidgets import isDarkTheme
        dark = isDarkTheme()
        palette = self.logEdit.palette()
        palette.setColor(self.logEdit.foregroundRole(), QColor('#ffffff' if dark else '#000000'))
        self.logEdit.setPalette(palette)

    # ---------------- TLV table helpers ----------------
    def _add_default_tlv_row(self):
        row = self.tlvTable.rowCount()
        self.tlvTable.insertRow(row)

        # Type ID
        typeSpin = SpinBox(self.tlvTable)
        typeSpin.setRange(0, 255)
        typeSpin.setValue(row + 1)
        self.tlvTable.setCellWidget(row, 0, typeSpin)

        # Kind
        kindCombo = ComboBox(self.tlvTable)  # NOQA 名称不规范
        kindCombo.currentTextChanged.connect(lambda text, spin=typeSpin: self._sync_v2_type_id_with_kind(spin, text))
        self.tlvTable.setCellWidget(row, 1, kindCombo)
        self._configure_kind_combo(kindCombo, typeSpin)

        # Value
        self.tlvTable.setItem(row, 2, QTableWidgetItem(''))

        # Enable
        enable = SwitchButton(self.tlvTable)
        enable.setOnText('ON')
        enable.setOffText('OFF')
        enable.setChecked(True)
        self.tlvTable.setCellWidget(row, 3, enable)

    def _delete_selected_tlv_rows(self):
        rows = sorted({i.row() for i in self.tlvTable.selectedIndexes()}, reverse=True)
        for r in rows:
            self.tlvTable.removeRow(r)

    def _iter_tlv_rows(self) -> list[_TlvRow]:
        out: list[_TlvRow] = []
        is_v2 = self.modeCombo.currentIndex() == 2
        for r in range(self.tlvTable.rowCount()):
            enable = self.tlvTable.cellWidget(r, 3)
            if isinstance(enable, SwitchButton) and not enable.isChecked():
                continue

            typeSpin = self.tlvTable.cellWidget(r, 0)
            type_id = typeSpin.value() if isinstance(typeSpin, SpinBox) else 0

            kindCombo = self.tlvTable.cellWidget(r, 1)  # NOQA 名称不规范
            kind = kindCombo.currentText() if isinstance(kindCombo, ComboBox) else 'hex(bytes)'
            if is_v2:
                derived_type_id = self._v2_type_id_from_kind(kind)
                if derived_type_id is None:
                    raise ValueError(f'V2不支持类型: {kind}')
                type_id = derived_type_id

            v_item = self.tlvTable.item(r, 2)
            value = v_item.text() if v_item is not None else ''
            out.append(_TlvRow(kind=kind, value=value, type_id=type_id))
        return out

    def _export_tlv_json_to_tx(self):
        rows = [row.__dict__ for row in self._iter_tlv_rows()]
        self.txEdit.setText(json.dumps(rows, ensure_ascii=False))

    def _import_tlv_json_from_tx(self):
        s = self.txEdit.text().strip()
        if not s:
            return
        data = json.loads(s)
        if not isinstance(data, list):
            raise ValueError('JSON必须是list')

        self.tlvTable.setRowCount(0)
        for it in data:
            type_id = int(it.get('type_id', 0))
            kind = str(it.get('kind', 'hex(bytes)'))
            value = str(it.get('value', ''))

            self._add_default_tlv_row()
            r = self.tlvTable.rowCount() - 1

            typeSpin = self.tlvTable.cellWidget(r, 0)
            kindCombo = self.tlvTable.cellWidget(r, 1)  # NOQA 名称不规范
            if isinstance(kindCombo, ComboBox):
                if self.modeCombo.currentIndex() == 2:
                    selected_kind = self._normalize_v2_kind(kind, type_id)
                    kindCombo.setCurrentText(selected_kind)
                else:
                    selected_kind = self._normalize_v1_kind(kind, type_id)
                    if selected_kind in [kindCombo.itemText(i) for i in range(kindCombo.count())]:
                        kindCombo.setCurrentText(selected_kind)

            if isinstance(typeSpin, SpinBox):
                if self.modeCombo.currentIndex() == 2:
                    derived_type_id = self._v2_type_id_from_kind(kindCombo.currentText())
                    if derived_type_id is None:
                        raise ValueError(f'V2不支持类型: {kind}')
                    typeSpin.setValue(derived_type_id)
                else:
                    typeSpin.setValue(type_id)

            self.tlvTable.setItem(r, 2, QTableWidgetItem(value))
            enable = self.tlvTable.cellWidget(r, 3)
            if isinstance(enable, SwitchButton):
                enable.setChecked(True)

    def _build_payload_from_table(self) -> bytes:
        parts: list[bytes] = []
        for row in self._iter_tlv_rows():
            parts.append(self._encode_tlv_row(row))
        return b''.join(parts)

    def _v1_kind_options(self) -> list[str]:
        return ['string', 'int32', 'uint32', 'float', 'hex(bytes)', 'int8', 'uint8', 'int16', 'uint16']

    def _v2_type_ids(self) -> list[int]:
        return sorted(TYPE_REGISTRY)

    def _v2_selector_options(self) -> list[str]:
        return [self._v2_selector_text(type_id) for type_id in self._v2_type_ids()]

    def _default_v2_selector(self) -> str:
        options = self._v2_selector_options()
        if 'string' in options:
            return 'string'
        return options[0] if options else ''

    def _v2_selector_text(self, type_id: int) -> str:
        return self._v2_type_name(type_id)

    def _normalize_v1_kind(self, kind: str, type_id: int = 0) -> str:
        aliases = {
            'u8': 'uint8',
            'u16': 'uint16',
            'u32': 'uint32',
        }
        normalized = aliases.get((kind or '').strip().lower(), kind or '')
        if normalized in self._v1_kind_options():
            return normalized

        type_id_map = {
            0x01: 'uint8',
            0x02: 'uint16',
            0x03: 'uint32',
            0x10: 'float',
            0x20: 'string',
        }
        return type_id_map.get(type_id, 'string')

    def _v2_type_id_from_kind(self, kind: str) -> Optional[int]:
        normalized = (kind or '').strip().lower()
        aliases = {
            'u8': 0x01,
            'uint8': 0x01,
            'u16': 0x02,
            'uint16': 0x02,
            'u32': 0x03,
            'uint32': 0x03,
            'float': 0x10,
            'string': 0x20,
        }
        type_id = aliases.get(normalized)
        if type_id in TYPE_REGISTRY:
            return type_id
        return None

    def _normalize_v2_kind(self, kind: str, type_id: int = 0) -> str:
        resolved_type_id = self._v2_type_id_from_kind(kind)
        if resolved_type_id is None and type_id in TYPE_REGISTRY:
            resolved_type_id = type_id
        if resolved_type_id is None:
            raise ValueError(f'V2不支持类型: {kind or type_id}')
        return self._v2_selector_text(resolved_type_id)

    def _configure_kind_combo(self, kind_combo: ComboBox, type_spin: SpinBox,
                              preferred_kind: str = '', preferred_type_id: int = 0):
        is_v2 = self.modeCombo.currentIndex() == 2
        kind_combo.blockSignals(True)
        kind_combo.clear()

        if is_v2:
            options = self._v2_selector_options()
            kind_combo.addItems(options)
            if options:
                try:
                    selected = self._normalize_v2_kind(preferred_kind, preferred_type_id)
                except ValueError:
                    selected = self._default_v2_selector()
            else:
                selected = ''
            if selected:
                kind_combo.setCurrentText(selected)
                self._sync_v2_type_id_with_kind(type_spin, selected)
        else:
            options = self._v1_kind_options()
            kind_combo.addItems(options)
            selected = self._normalize_v1_kind(preferred_kind, preferred_type_id)
            kind_combo.setCurrentText(selected)

        kind_combo.blockSignals(False)

    def _refresh_tlv_row_editors_for_mode(self):
        for row in range(self.tlvTable.rowCount()):
            type_spin = self.tlvTable.cellWidget(row, 0)
            kind_combo = self.tlvTable.cellWidget(row, 1)
            if not isinstance(type_spin, SpinBox) or not isinstance(kind_combo, ComboBox):
                continue

            current_kind = kind_combo.currentText()
            current_type_id = type_spin.value()
            try:
                self._configure_kind_combo(kind_combo, type_spin, current_kind, current_type_id)
            except ValueError:
                self._configure_kind_combo(kind_combo, type_spin)

    def _build_v2_payload_from_table(self) -> bytes:
        payload = V2Payload()
        for row in self._iter_tlv_rows():
            type_id = int(row.type_id) & 0xFF
            type_obj = TYPE_REGISTRY.get(type_id)
            if type_obj is None:
                raise ValueError(f'V2不支持Type ID: 0x{type_id:02X}')

            payload.addData(type_obj, self._coerce_v2_value(row, type_obj))
        return payload.toBytes()

    def _sync_v2_type_id_with_kind(self, type_spin: SpinBox, kind: str):
        if self.modeCombo.currentIndex() != 2:
            return
        suggested = self._v2_type_id_from_kind(kind)
        if suggested is not None:
            type_spin.setValue(suggested)

    def _coerce_v2_value(self, row: _TlvRow, type_obj: TypeBase):
        raw_value = row.value.strip()

        if isinstance(type_obj, DataString):
            return row.value
        if isinstance(type_obj, DataFloat):
            return float(raw_value or '0')
        if isinstance(type_obj, DataInt):
            return int(raw_value or '0', 0)

        if row.kind == 'string':
            return row.value
        if row.kind == 'float':
            return float(raw_value or '0')
        if row.kind in ('int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'u8', 'u16', 'u32'):
            return int(raw_value or '0', 0)
        raise ValueError(f'V2不支持值类型: {row.kind}')

    def _reset_v2_protocol(self):
        self._v2_parser = None
        self._v2_dispatcher = None
        self._v2_seq = 0

    def _init_v2_protocol(self):
        self._v2_parser = V2FrameParser()
        self._v2_dispatcher = V2Dispatcher()

        def _v2_ack(cmd, seq, payload_data):
            self.rxEventSignal.emit(f'V2 ACK cmd={cmd:02X} seq={seq} [{self._format_v2_payload_items(payload_data)}]')

        def _v2_nack(cmd, seq, payload_data):
            self.rxEventSignal.emit(f'V2 NACK cmd={cmd:02X} seq={seq} [{self._format_v2_payload_items(payload_data)}]')

        self._v2_dispatcher.setAckHandler(_v2_ack)
        self._v2_dispatcher.setNackHandler(_v2_nack)

    def _v2_type_name(self, type_id: int) -> str:
        type_obj = TYPE_REGISTRY.get(type_id)
        if type_obj is None:
            return 'bytes'
        if isinstance(type_obj, DataString):
            return 'string'
        if isinstance(type_obj, DataFloat):
            return 'float'
        return getattr(type_obj, 'name', type_obj.__class__.__name__)

    def _format_v2_payload_items(self, payload_data: dict[int, Any]) -> str:
        if not payload_data:
            return ''

        parts = []
        for type_id, value in payload_data.items():
            if isinstance(value, bytes):
                text = value.hex(' ')
            else:
                text = str(value)
            parts.append(f'T{type_id:02X}({self._v2_type_name(type_id)}):{text}')
        return ', '.join(parts)

    def _handle_v2_rx_frames(self, data: bytes):
        if self._v2_parser is None:
            return

        frames = self._v2_parser.inputBytes(data)
        for frame in frames:
            if self._v2_dispatcher is not None and self._v2_dispatcher.dispatch(frame):
                continue

            cmd = frame['cmd']
            seq = frame['seq']
            payload = frame['payload']
            parsed = V2Payload.parse(payload)
            self.rxEventSignal.emit(f'V2 RX cmd={cmd:02X} seq={seq} [{self._format_v2_payload_items(parsed)}]')

    def _parse_raw_input(self, s: str, fmt: str) -> bytes:  # NOQA 函数参数命名不规范，但符合语义
        fmt = (fmt or '').upper()
        if fmt == 'ASCII':
            return s.encode('utf-8')

        # HEX input: allow spaces, commas, 0x prefixes
        s = s.replace('0x', '').replace(',', ' ').replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        # remove spaces
        hexstr = ''.join(ch for ch in s if ch not in ' ')
        if len(hexstr) % 2 != 0:
            raise ValueError('HEX长度必须为偶数')
        return binascii.unhexlify(hexstr)

    # ---------------- Serial lifecycle ----------------
    def refresh_ports(self):
        ports = listSerialPorts() or []
        ports = [p.strip() for p in ports if p and p.strip()]

        self._append_log(f'Ports: {ports}')

        cur = self.portCombo.currentText().strip()
        self.portCombo.clear()

        if ports:
            self.portCombo.addItems(ports)
            if cur and cur in ports:
                self.portCombo.setCurrentText(cur)
            return

    def toggle_connection(self):
        if self._session and self._session.is_open:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        port = self.portCombo.currentText().strip()
        if not port:
            self._append_log('ERR: 未找到串口（请先刷新/安装驱动）')
            return

        # ensure baud has a default value for static analyzers
        baud = QSerialPort.BaudRate.Baud9600
        match int(self.baudCombo.currentText().strip()):
            case 9600:
                baud = QSerialPort.BaudRate.Baud9600
            case 19200:
                baud = QSerialPort.BaudRate.Baud19200
            case 38400:
                baud = QSerialPort.BaudRate.Baud38400
            case 57600:
                baud = QSerialPort.BaudRate.Baud57600
            case 115200:
                baud = QSerialPort.BaudRate.Baud115200
            case _:
                baud = QSerialPort.BaudRate.Baud9600

        cfg = SerialConfig(port=port, baudrate=baud)
        self._session = SerialSession(cfg, _event_receiver=self)

        # 使用事件机制：SerialSession 会向该小部件发布事件。
        # 不要在会话中分配回调处理程序;优先选择事件。
        try:
            self._session.set_event_receiver(self)
        except Exception:  # NOQA 异常子句过于宽泛
            # 忽略设置接收端的失败;SerialSession 将回退回调
            pass

        # 记录串行层写入的实际字节
        self._session.on_tx = lambda b: self._append_log(f'TX({len(b)}): {b.hex(" ")}')
        # 将调试消息从会话连接到 UI 日志以进行故障排除
        self._session.on_debug = lambda s: self._append_log(f'DBG: {s}')
        self._session.on_state = lambda ok: self.stateSignal.emit(ok)

        # TVLCOMV1_FULL protocol
        self._proto = Protocol(lambda b: self._safe_write(b))
        self._register_tvl_handlers(self._proto)

        # TVLCOMV2_FULL protocol
        self._init_v2_protocol()

        try:
            self._session.open()
            self._append_log(f'打开串口: {port} @ {self.baudCombo.currentText().strip()}')
        except Exception as e:
            self._on_error(str(e))
            self._session = None
            self._proto = None
            self._reset_v2_protocol()

    def _disconnect(self):
        try:
            if self._session:
                self._session.close()
        finally:
            self._session = None
            self._proto = None
            self._reset_v2_protocol()
            self._append_log('未连接')

    def _safe_write(self, data: bytes):
        # Post a SendEvent to the SerialSession so writes always execute in its thread.
        if not self._session or not self._session.is_open:
            return
        try:
            from app.Core.serial_session import SendEvent
            QCoreApplication.postEvent(self._session, SendEvent(data))
        except Exception:  # NOQA 异常子句过于宽泛
            try:
                self._session.write(data)
            except Exception as e:
                self.errSignal.emit(str(e))

    def _on_state(self, ok: bool):
        self.stateLabel.setText('已连接' if ok else '未连接')
        self.connectButton.setText('断开' if ok else '连接')

    def _on_error(self, msg: str):
        self._append_log(f'ERR: {msg}')
        logger.error(msg)

    # ---------------- RX handling ----------------
    def _on_rx_raw(self, data: bytes):
        # 原始显示被缓冲以避免 UI 停顿
        self._rx_buf.extend(data)

        # optional: TVLCOMV1_FULL / V2 parse
        if self.parseSwitch.isChecked():
            if self._proto is not None:
                try:
                    self._proto.feed(data)
                except Exception as e:
                    pass

            if self._v2_parser is not None:
                try:
                    self._handle_v2_rx_frames(data)
                except Exception as e:
                    self.errSignal.emit(f'TVLCOMV2_FULL feed failed: {e}')

    def _register_tvl_handlers(self, proto: Protocol):
        # Register common TLV type handlers for display.
        def _show(t: int, v: bytes, seq: int):  # NOQA 变量不规范
            name = self._tlv_name(t)
            self.rxEventSignal.emit(f'TLV seq={seq} type={t}({name}) len={len(v)} val={self._format_tlv_value(t, v)}')

        # default: register known constants if available
        for t in [
            getattr(tvl_const, 'TLV_STRING', None),
            getattr(tvl_const, 'TLV_INT32', None),
            getattr(tvl_const, 'TLV_UINT32', None),
            getattr(tvl_const, 'TLV_FLOAT', None),
        ]:
            if isinstance(t, int):
                proto.dispatcher.register(t, lambda v, seq, tt=t: _show(tt, v, seq))

        # Also register a catch-all for types 0..255 that are not registered? Dispatcher doesn't support wildcard,
        # so we keep it minimal.

    def _tlv_name(self, t: int) -> str:  # NOQA 名称不规范
        for k, v in vars(tvl_const).items():
            if k.startswith('TLV_') and v == t:
                return k
        return 'UNKNOWN'

    def _format_tlv_value(self, t: int, v: bytes) -> str:  # NOQA 名称不规范
        try:
            if t == tvl_const.TLV_STRING:
                return v.decode(errors='replace')
            if t == tvl_const.TLV_INT32 and len(v) == 4:
                return str(struct.unpack('<i', v)[0])
            if t == tvl_const.TLV_UINT32 and len(v) == 4:
                return str(struct.unpack('<I', v)[0])
            if t == tvl_const.TLV_FLOAT and len(v) == 4:
                return str(struct.unpack('<f', v)[0])
        except Exception:  # NOQA 名称不规范
            pass
        return '0x' + v.hex()

    # ---------------- TX ----------------
    def on_send(self):
        if not self._session or not self._session.is_open:
            self._append_log('ERR: 串口未连接')

            return

        repeat = int(self.repeatSpin.value())
        idx = self.modeCombo.currentIndex()
        is_tvl = idx == 1
        is_v2 = idx == 2

        if idx == 0:
            raw = self.txEdit.text().strip()
            if not raw:
                return
            try:
                data = self._parse_raw_input(raw, self.rawFmtCombo.currentText())
            except Exception as e:
                self._append_log(f'ERR: Raw解析失败: {e}')
                return

            for _ in range(repeat):
                try:
                    from app.Core.serial_session import SendEvent
                    QCoreApplication.postEvent(self._session, SendEvent(data))
                except Exception:
                    try:
                        self._session.write(data)
                    except Exception as e:
                        self.errSignal.emit(str(e))

            # high-level TX log (SerialSession.on_tx will also log the raw bytes)
            self._append_log(f'TX 原始数据: ({len(data)}): {data.hex(" ")}')
            return

        if is_v2:
            try:
                payload = self._build_v2_payload_from_table()
            except Exception as e:
                self._append_log(f'ERR: V2组包失败: {e}')
                return

            cmd = self.cmdSpin.value()
            seqs: list[int] = []
            for _ in range(repeat):
                self._v2_seq = (self._v2_seq + 1) % 256
                frame_bytes = V2FrameBuilder.buildFrame(cmd, self._v2_seq, payload)
                self._safe_write(frame_bytes)
                seqs.append(self._v2_seq)

            if len(seqs) == 1:
                seq_text = str(seqs[0])
            else:
                seq_text = ','.join(str(seq) for seq in seqs)
            self._append_log(f'TX v2 : CMD={cmd:02X} seq={seq_text} 有效长度: ({len(payload)}),有效数据: {payload.hex(" ")}')
            return

        # TVLCOMV1_FULL TLV compose
        if self._proto is None:
            self._append_log('ERR: TVLCOMV1_FULL 未初始化')  # NOQA 名称不规范
            return

        try:
            payload = self._build_payload_from_table()
        except Exception as e:
            self._append_log(f'ERR: TLV组包失败: {e}')
            return

        ack: bool = self.ackSwitch.isChecked()
        for _ in range(repeat):
            self._proto.send_payload(payload, ack=ack)
        self._append_log(f'TX tvl : 有效长度: ({len(payload)}),有效数据: {payload.hex(" ")}')

    def _encode_tlv_value_only(self, row: _TlvRow) -> bytes:
        if row.kind == 'string':
            return row.value.encode('utf-8')
        if row.kind == 'int8':
            return struct.pack('<b', int(row.value.strip(), 0))
        if row.kind == 'uint8':
            return struct.pack('<B', int(row.value.strip(), 0))
        if row.kind == 'int16':
            return struct.pack('<h', int(row.value.strip(), 0))
        if row.kind == 'uint16':
            return struct.pack('<H', int(row.value.strip(), 0))
        if row.kind == 'int32':
            return struct.pack('<i', int(row.value.strip(), 0))
        if row.kind == 'uint32':
            return struct.pack('<I', int(row.value.strip(), 0))
        if row.kind == 'float':
            return struct.pack('<f', float(row.value.strip()))
        # hex(bytes)
        raw_s = row.value.strip()
        if not raw_s:
            return b''
        hexstr = ''.join(ch for ch in raw_s.replace('0x', '').replace(',', ' ').split() if ch)
        return binascii.unhexlify(hexstr)

    def _encode_tlv_row(self, row: _TlvRow) -> bytes:  # NOQA 函数参数命名不规范，但符合语义
        # 根据kind自动选择type (V1 format)
        raw = self._encode_tlv_value_only(row)
        if row.kind == 'string':
            t = tvl_const.TLV_STRING
        elif row.kind in ('int8', 'int16', 'int32'):
            t = tvl_const.TLV_INT32
        elif row.kind in ('uint8', 'uint16', 'uint32'):
            t = tvl_const.TLV_UINT32
        elif row.kind == 'float':
            t = tvl_const.TLV_FLOAT
        else:
            t = tvl_const.TLV_BINARY
        return tlv_encode(t, raw)
