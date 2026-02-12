"""Device page (下位机界面)

Serial console for device connection/control.

Features:
- Serial port scan / connect / disconnect (pyserial)
- RX display (raw bytes), optional TVLCOM parsing events
- TX modes:
  - Raw: HEX/ASCII
  - TVLCOM: compose payload from TLV fields then Protocol.send_payload()
"""

from __future__ import annotations

import binascii
import json
import struct
import time
from dataclasses import dataclass
from typing import Optional

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
from app.Core import SerialConfig, SerialSession, SerialEventType, listSerialPorts, StyleSheet
from app.Core import logger
from app.TVLCOM import const as tvl_const
from app.TVLCOM.protocol import Protocol
from app.TVLCOM.tlv import tlv_encode
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    LineEdit,
    PlainTextEdit,
    PrimaryPushButton,
    PushButton,
    SpinBox,
    SwitchButton,
    TitleLabel,
    TableWidget
)
from qfluentwidgets import isDarkTheme


@dataclass
class _TlvRow:
    kind: str
    value: str


class DevicePage(QWidget):
    rxEventSignal = pyqtSignal(str)
    stateSignal = pyqtSignal(bool)
    errSignal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._session: Optional[SerialSession] = None
        self._proto: Optional[Protocol] = None

        self._rx_buf = bytearray()
        self._rx_timer = QTimer(self)
        self._rx_timer.setInterval(60)
        self._rx_timer.timeout.connect(self._flush_rx)
        self._rx_timer.start()

        self.setObjectName("DevicePage")  # 主题设置
        StyleSheet.DEVICE_PAGE.apply(self)
        # 响应主题切换
        from app.Config import cfg
        cfg.themeChanged.connect(self._on_theme_changed)

        self.vBoxLayout = QVBoxLayout(self)
        m = 24
        self.vBoxLayout.setContentsMargins(m, m, m, m)
        self.vBoxLayout.setSpacing(12)

        self.titleLabel = TitleLabel('TVL COM', self)
        self.vBoxLayout.addWidget(self.titleLabel)

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

        self.stateLabel = BodyLabel('Disconnected', connBar)
        connLayout.addWidget(self.stateLabel)

        connLayout.addStretch(1)
        self.vBoxLayout.addWidget(connBar)

        # ---- Log console ----
        self.logEdit = PlainTextEdit(self)
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
        self.modeCombo.addItems(['Raw(HEX/ASCII)', 'TVLCOM(TLV)'])
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

        # ---- TLV table (only used in TVLCOM mode) ----
        self.tlvTable = TableWidget(self)
        self.tlvTable.setColumnCount(3)
        self.tlvTable.setHorizontalHeaderLabels(['Kind', 'Value', 'Enable'])
        self.tlvTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
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
        self.txEdit.setPlaceholderText('Raw: 输入HEX(如 01 0A FF) 或 ASCII 文本；TVLCOM: 可留空（按TLV表组包）')
        sendLayout.addWidget(self.txEdit, 1)

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
        is_tvl = self.modeCombo.currentIndex() == 1
        self.tlvTable.setVisible(is_tvl)
        self.addTlvBtn.setVisible(is_tvl)
        self.delTlvBtn.setVisible(is_tvl)
        self.exportTlvBtn.setVisible(is_tvl)
        self.importTlvBtn.setVisible(is_tvl)
        self.rawFmtCombo.setVisible(not is_tvl)
        self.ackSwitch.setVisible(is_tvl)

    def _append_log(self, text: str):
        ts = time.strftime('%H:%M:%S')
        msg = f'[{ts}] {text}'
        logger.info(msg)

        # choose color based on message content/type
        lc = text.strip()
        # Theme-aware color defaults: pick readable colors depending on theme
        dark = isDarkTheme()
        if lc.startswith('ERR:'):
            color = QColor('red')
        elif lc.startswith('RX('):
            color = QColor('#6ea8fe') if dark else QColor('darkBlue')
        elif lc.startswith('TLV') or 'TLV seq=' in lc or lc.startswith('TX tvl'):
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
        # 重新应用样式表
        StyleSheet.DEVICE_PAGE.apply(self)
        # 强制刷新TEXTEDIT颜色
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

        # Kind
        kindCombo = ComboBox(self.tlvTable)  # NOQA 名称不规范
        kindCombo.addItems(['string', 'int32', 'uint32', 'float', 'hex(bytes)'])
        kindCombo.setCurrentText('string')
        self.tlvTable.setCellWidget(row, 0, kindCombo)

        # Value
        self.tlvTable.setItem(row, 1, QTableWidgetItem(''))

        # Enable
        enable = SwitchButton(self.tlvTable)
        enable.setOnText('ON')
        enable.setOffText('OFF')
        enable.setChecked(True)
        self.tlvTable.setCellWidget(row, 2, enable)

    def _delete_selected_tlv_rows(self):
        rows = sorted({i.row() for i in self.tlvTable.selectedIndexes()}, reverse=True)
        for r in rows:
            self.tlvTable.removeRow(r)

    def _iter_tlv_rows(self) -> list[_TlvRow]:
        out: list[_TlvRow] = []
        for r in range(self.tlvTable.rowCount()):
            enable = self.tlvTable.cellWidget(r, 2)
            if isinstance(enable, SwitchButton) and not enable.isChecked():
                continue

            kindCombo = self.tlvTable.cellWidget(r, 0)  # NOQA 名称不规范
            kind = kindCombo.currentText() if isinstance(kindCombo, ComboBox) else 'hex(bytes)'

            v_item = self.tlvTable.item(r, 1)
            value = v_item.text() if v_item is not None else ''
            out.append(_TlvRow(kind=kind, value=value))
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
            kind = str(it.get('kind', 'hex(bytes)'))
            value = str(it.get('value', ''))

            self._add_default_tlv_row()
            r = self.tlvTable.rowCount() - 1

            kindCombo = self.tlvTable.cellWidget(r, 0)  # NOQA 名称不规范
            if isinstance(kindCombo, ComboBox):
                if kind in [kindCombo.itemText(i) for i in range(kindCombo.count())]:
                    kindCombo.setCurrentText(kind)

            self.tlvTable.setItem(r, 1, QTableWidgetItem(value))
            enable = self.tlvTable.cellWidget(r, 2)
            if isinstance(enable, SwitchButton):
                enable.setChecked(True)

    def _build_payload_from_table(self) -> bytes:
        parts: list[bytes] = []
        for row in self._iter_tlv_rows():
            parts.append(self._encode_tlv_row(row))
        return b''.join(parts)

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

        # # 枚举不到时：提供常见 COM 列表，便于手动选择虚拟串口
        # fallback = [f'COM{i}' for i in range(1, 257)]
        # self.portCombo.addItems(fallback)
        # if cur and cur in fallback:
        #     self.portCombo.setCurrentText(cur)

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
        self._session = SerialSession(cfg)
        # Use event mechanism: SerialSession will post events to this widget.
        # Do not assign callback handlers on the session; prefer events.
        try:
            self._session.set_event_receiver(self)
        except Exception:  # NOQA 异常子句过于宽泛
            # ignore failures to set receiver; SerialSession will fallback to callbacks
            pass

        # 记录串行层写入的实际字节
        self._session.on_tx = lambda b: self._append_log(f'TX({len(b)}): {b.hex(" ")}')
        # 将调试消息从会话连接到 UI 日志以进行故障排除
        self._session.on_debug = lambda s: self._append_log(f'DBG: {s}')
        self._session.on_state = lambda ok: self.stateSignal.emit(ok)

        # TVLCOM protocol
        self._proto = Protocol(lambda b: self._safe_write(b))
        self._register_tvl_handlers(self._proto)

        try:
            self._session.open()
            self._append_log(f'打开串口:  {port} @ {baud}')
        except Exception as e:
            self._on_error(str(e))
            self._session = None
            self._proto = None

    def _disconnect(self):
        try:
            if self._session:
                self._session.close()
        finally:
            self._session = None
            self._proto = None
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

        # optional: TVLCOM parse
        if self.parseSwitch.isChecked() and self._proto is not None:
            try:
                self._proto.feed(data)
            except Exception as e:
                self.errSignal.emit(f'TVLCOM feed failed: {e}')

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
        is_tvl = self.modeCombo.currentIndex() == 1

        if not is_tvl:
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

        # TVLCOM TLV compose
        if self._proto is None:
            self._append_log('ERR: TVLCOM 未初始化')  # NOQA 名称不规范
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

    def _encode_tlv_row(self, row: _TlvRow) -> bytes:  # NOQA 函数参数命名不规范，但符合语义
        # 根据kind自动选择type
        if row.kind == 'string':
            t = tvl_const.TLV_STRING
            return tlv_encode(t, row.value.encode('utf-8'))
        if row.kind == 'int32':
            t = tvl_const.TLV_INT32
            return tlv_encode(t, struct.pack('<i', int(row.value.strip(), 0)))
        if row.kind == 'uint32':
            t = tvl_const.TLV_UINT32
            return tlv_encode(t, struct.pack('<I', int(row.value.strip(), 0)))
        if row.kind == 'float':
            t = tvl_const.TLV_FLOAT
            return tlv_encode(t, struct.pack('<f', float(row.value.strip())))
        # hex(bytes)
        t = tvl_const.TLV_BINARY
        raw_s = row.value.strip()
        if not raw_s:
            raw = b''
        else:
            # accept hex like '01 02 03' or '0x010203' or '010203'
            hexstr = ''.join(ch for ch in raw_s.replace('0x', '').replace(',', ' ').split() if ch)
            raw = binascii.unhexlify(hexstr)
        return tlv_encode(t, raw)
