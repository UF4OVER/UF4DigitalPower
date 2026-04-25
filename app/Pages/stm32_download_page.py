# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path

from PyQt5.QtCore import QCoreApplication, Qt
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QFileDialog, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    ComboBox,
    FluentIcon as FIF,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SubtitleLabel,
    SwitchButton,
    TitleLabel,
    TextEdit,
)

from app.Core import (
    ActionFinishedPayload,
    Stm32ConnectConfig,
    Stm32DeviceInfo,
    Stm32MemoryValue,
    Stm32ProbeInfo,
    Stm32ProgrammerEventType,
    Stm32ProgrammerSession,
    Stm32RequestEvent,
    Stm32RequestPayload,
)
from Config import DirPathsInstance


class Stm32DownloadPage(ScrollArea):
    FLASH_BASE_ADDRESS = "0x08000000"

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("Stm32DownloadPage")

        self._probe_items: list[Stm32ProbeInfo] = []
        self._device_info: Stm32DeviceInfo | None = None
        self._last_action_device_info: Stm32DeviceInfo | None = None

        self.readbackPathInput: LineEdit | None = None
        self.readAddressInput: LineEdit | None = None
        self.readSizeInput: LineEdit | None = None
        self.uploadButton: PrimaryPushButton | None = None
        self.memoryAddressInput: LineEdit | None = None
        self.memoryCountInput: LineEdit | None = None
        self.memoryReadButton: PushButton | None = None
        self.memoryResultLabel: BodyLabel | None = None

        self.view = QWidget(self)
        self.view.setObjectName("stm32ScrollWidget")
        self.vBoxLayout = QVBoxLayout(self.view)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.vBoxLayout.setSpacing(12)

        self.titleLabel = TitleLabel("STM32 ST-LINK 下载工具", self.view)
        self.vBoxLayout.addWidget(self.titleLabel)

        self._init_connection_card()
        self._init_info_card()
        self._init_download_card()
        # self._init_upload_card()
        # self._init_tools_card()
        self._init_log_card()

        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self._session = Stm32ProgrammerSession(_event_receiver=self, parent=self)
        self._reset_device_info()

    def event(self, e):
        event_type = e.type()

        if event_type == int(Stm32ProgrammerEventType.LOG):
            self.log(e.payload.text, self._log_color_for_level(e.payload.level))
            return True

        if event_type == int(Stm32ProgrammerEventType.MESSAGE):
            self.showMessage(e.payload.title, e.payload.content, e.payload.level)
            return True

        if event_type == int(Stm32ProgrammerEventType.STATE):
            self.set_buttons_enabled(not e.payload.busy)
            if e.payload.busy and e.payload.action in {"connect", "download"}:
                self._last_action_device_info = None
            return True

        if event_type == int(Stm32ProgrammerEventType.PROBES):
            self._apply_probe_items(e.payload.probes)
            return True

        if event_type == int(Stm32ProgrammerEventType.DEVICE_INFO):
            self._apply_device_info(e.payload.info)
            self._last_action_device_info = e.payload.info
            return True

        if event_type == int(Stm32ProgrammerEventType.CHECKSUM):
            self._apply_checksum_result(e.payload.checksum)
            return True

        if event_type == int(Stm32ProgrammerEventType.MEMORY):
            self._apply_memory_result(e.payload.values)
            return True

        if event_type == int(Stm32ProgrammerEventType.ACTION_FINISHED):
            self._handle_action_finished(e.payload)
            return True

        return super().event(e)

    def closeEvent(self, event):
        self._session.shutdown()
        super().closeEvent(event)

    def _init_connection_card(self):
        self.connectCard = CardWidget(self.view)
        layout = QVBoxLayout(self.connectCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = SubtitleLabel("ST-LINK 连接", self.connectCard)
        layout.addWidget(title)

        row1 = QHBoxLayout()
        self.stlinkCombo = ComboBox(self.connectCard)
        self.stlinkCombo.setPlaceholderText("扫描并选择 ST-LINK")
        self.stlinkCombo.setMinimumWidth(360)
        row1.addWidget(self.stlinkCombo, 1)

        self.scanBtn = PushButton(FIF.SYNC, "扫描", self.connectCard)
        self.scanBtn.clicked.connect(self.scanLink)
        row1.addWidget(self.scanBtn)

        self.connectBtn = PrimaryPushButton(FIF.LINK, "连接并读取信息", self.connectCard)
        self.connectBtn.clicked.connect(self.readInfo)
        row1.addWidget(self.connectBtn)
        layout.addLayout(row1)

        row2 = QGridLayout()
        row2.setHorizontalSpacing(12)
        row2.setVerticalSpacing(8)

        row2.addWidget(BodyLabel("SWD 频率(KHz)", self.connectCard), 0, 0)
        self.freqInput = LineEdit(self.connectCard)
        self.freqInput.setText("4000")
        self.freqInput.setPlaceholderText("例如 4000 / 8000")
        row2.addWidget(self.freqInput, 0, 1)

        row2.addWidget(BodyLabel("连接模式", self.connectCard), 0, 2)
        self.modeCombo = ComboBox(self.connectCard)
        self.modeCombo.addItems(["NORMAL", "HOTPLUG", "UR", "POWERDOWN", "HWRSTPULSE"])
        self.modeCombo.setCurrentText("NORMAL")
        row2.addWidget(self.modeCombo, 0, 3)

        row2.addWidget(BodyLabel("复位模式", self.connectCard), 1, 0)
        self.resetCombo = ComboBox(self.connectCard)
        self.resetCombo.addItems(["SWrst", "HWrst", "Crst"])
        self.resetCombo.setCurrentText("SWrst")
        row2.addWidget(self.resetCombo, 1, 1)

        row2.addWidget(BodyLabel("连接状态", self.connectCard), 1, 2)
        self.stateLabel = BodyLabel("未连接", self.connectCard)
        self.stateLabel.setStyleSheet("font-weight: bold; color: #C42B1C;")
        row2.addWidget(self.stateLabel, 1, 3)
        layout.addLayout(row2)

        self.vBoxLayout.addWidget(self.connectCard)

    def _init_info_card(self):
        self.infoCard = CardWidget(self.view)
        layout = QVBoxLayout(self.infoCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = SubtitleLabel("MCU / 探针信息", self.infoCard)
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        self.infoLabels: dict[str, BodyLabel] = {}

        fields = [
            ("probe_sn", "ST-LINK SN"),
            ("probe_fw", "ST-LINK FW"),
            ("board", "Board"),
            ("voltage", "Voltage"),
            ("device_name", "Device"),
            ("device_id", "Device ID"),
            ("revision", "Revision"),
            ("flash_size", "Flash Size"),
            ("cpu", "CPU"),
            ("connect_mode", "Connect Mode"),
            ("reset_mode", "Reset Mode"),
            ("bl_version", "BL Version"),
        ]

        for index, (key, title_text) in enumerate(fields):
            row = index // 2
            column = (index % 2) * 2
            grid.addWidget(BodyLabel(title_text, self.infoCard), row, column)
            value_label = BodyLabel("--", self.infoCard)
            value_label.setStyleSheet("font-weight: bold;")
            grid.addWidget(value_label, row, column + 1)
            self.infoLabels[key] = value_label

        layout.addLayout(grid)

        infoRow = QHBoxLayout()
        self.summaryLabel = BodyLabel("等待连接 MCU…", self.infoCard)
        self.summaryLabel.setStyleSheet("color: #777777;")
        infoRow.addWidget(self.summaryLabel, 1)

        self.checksumBtn = PushButton(FIF.CALORIES, "计算 Flash 校验和", self.infoCard)
        self.checksumBtn.clicked.connect(self.calculateChecksum)
        infoRow.addWidget(self.checksumBtn)
        layout.addLayout(infoRow)

        self.checksumResultLabel = BodyLabel("最近一次 Flash 校验和：--", self.infoCard)
        self.checksumResultLabel.setWordWrap(True)
        layout.addWidget(self.checksumResultLabel)

        self.vBoxLayout.addWidget(self.infoCard)

    def _init_download_card(self):
        self.downloadCard = CardWidget(self.view)
        layout = QVBoxLayout(self.downloadCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = SubtitleLabel("固件下载到 MCU", self.downloadCard)
        layout.addWidget(title)

        fileRow = QHBoxLayout()
        self.filePathInput = LineEdit(self.downloadCard)
        self.filePathInput.setPlaceholderText("选择待下载的固件文件（.bin/.hex/.elf/.s19）")
        fileRow.addWidget(self.filePathInput, 1)

        self.browseButton = PushButton(FIF.FOLDER, "浏览", self.downloadCard)
        self.browseButton.clicked.connect(self.browseFile)
        fileRow.addWidget(self.browseButton)
        layout.addLayout(fileRow)

        optionRow = QGridLayout()
        optionRow.setHorizontalSpacing(12)
        optionRow.setVerticalSpacing(8)

        optionRow.addWidget(BodyLabel("起始地址", self.downloadCard), 0, 0)
        self.downloadAddressInput = LineEdit(self.downloadCard)
        self.downloadAddressInput.setText(self.FLASH_BASE_ADDRESS)
        self.downloadAddressInput.setPlaceholderText("bin 文件常用 0x08000000")
        optionRow.addWidget(self.downloadAddressInput, 0, 1)

        self.verifySwitch = SwitchButton(self.downloadCard)
        self.verifySwitch.setOnText("写后校验")
        self.verifySwitch.setOffText("写后校验")
        self.verifySwitch.setChecked(True)
        optionRow.addWidget(self.verifySwitch, 0, 2)

        self.skipEraseSwitch = SwitchButton(self.downloadCard)
        self.skipEraseSwitch.setOnText("跳过擦除")
        self.skipEraseSwitch.setOffText("跳过擦除")
        self.skipEraseSwitch.setChecked(False)
        optionRow.addWidget(self.skipEraseSwitch, 0, 3)

        self.resetAfterDownloadSwitch = SwitchButton(self.downloadCard)
        self.resetAfterDownloadSwitch.setOnText("完成后复位")
        self.resetAfterDownloadSwitch.setOffText("完成后复位")
        self.resetAfterDownloadSwitch.setChecked(True)
        optionRow.addWidget(self.resetAfterDownloadSwitch, 1, 2)

        self.downloadButton = PrimaryPushButton(FIF.DOWNLOAD, "开始下载", self.downloadCard)
        self.downloadButton.clicked.connect(self.startDownload)
        optionRow.addWidget(self.downloadButton, 1, 3)
        layout.addLayout(optionRow)

        self.vBoxLayout.addWidget(self.downloadCard)

    def _init_upload_card(self):
        self.uploadCard = CardWidget(self.view)
        layout = QVBoxLayout(self.uploadCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = SubtitleLabel("读取 MCU 固件", self.uploadCard)
        layout.addWidget(title)

        fileRow = QHBoxLayout()
        self.readbackPathInput = LineEdit(self.uploadCard)
        self.readbackPathInput.setPlaceholderText("选择读取后保存的文件路径（.bin/.hex/.s19）")
        fileRow.addWidget(self.readbackPathInput, 1)

        self.readbackBrowseButton = PushButton(FIF.SAVE, "另存为", self.uploadCard)
        self.readbackBrowseButton.clicked.connect(self.chooseReadbackPath)
        fileRow.addWidget(self.readbackBrowseButton)
        layout.addLayout(fileRow)

        optionRow = QGridLayout()
        optionRow.setHorizontalSpacing(12)
        optionRow.setVerticalSpacing(8)

        optionRow.addWidget(BodyLabel("起始地址", self.uploadCard), 0, 0)
        self.readAddressInput = LineEdit(self.uploadCard)
        self.readAddressInput.setText(self.FLASH_BASE_ADDRESS)
        optionRow.addWidget(self.readAddressInput, 0, 1)

        optionRow.addWidget(BodyLabel("读取大小", self.uploadCard), 0, 2)
        self.readSizeInput = LineEdit(self.uploadCard)
        self.readSizeInput.setPlaceholderText("例如 131072 或 0x20000")
        optionRow.addWidget(self.readSizeInput, 0, 3)

        self.uploadButton = PrimaryPushButton(FIF.DOWN, "读取固件", self.uploadCard)
        self.uploadButton.clicked.connect(self.readFirmware)
        optionRow.addWidget(self.uploadButton, 1, 3)
        layout.addLayout(optionRow)

        self.vBoxLayout.addWidget(self.uploadCard)

    def _init_tools_card(self):
        self.toolsCard = CardWidget(self.view)
        layout = QVBoxLayout(self.toolsCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = SubtitleLabel("内存读取 / 调试小工具", self.toolsCard)
        layout.addWidget(title)

        row = QGridLayout()
        row.setHorizontalSpacing(12)
        row.setVerticalSpacing(8)

        row.addWidget(BodyLabel("读取地址", self.toolsCard), 0, 0)
        self.memoryAddressInput = LineEdit(self.toolsCard)
        self.memoryAddressInput.setText(self.FLASH_BASE_ADDRESS)
        row.addWidget(self.memoryAddressInput, 0, 1)

        row.addWidget(BodyLabel("32-bit 数量", self.toolsCard), 0, 2)
        self.memoryCountInput = LineEdit(self.toolsCard)
        self.memoryCountInput.setText("4")
        row.addWidget(self.memoryCountInput, 0, 3)

        self.memoryReadButton = PushButton(FIF.VIEW, "读取内存", self.toolsCard)
        self.memoryReadButton.clicked.connect(self.readMemory)
        row.addWidget(self.memoryReadButton, 1, 3)
        layout.addLayout(row)

        self.memoryResultLabel = BodyLabel("最近一次读取结果：--", self.toolsCard)
        self.memoryResultLabel.setWordWrap(True)
        layout.addWidget(self.memoryResultLabel)

        self.vBoxLayout.addWidget(self.toolsCard)

    def _init_log_card(self):
        self.logCard = CardWidget(self.view)
        layout = QVBoxLayout(self.logCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        titleRow = QHBoxLayout()
        titleRow.addWidget(SubtitleLabel("运行日志", self.logCard))
        titleRow.addStretch(1)

        self.clearLogButton = PushButton(FIF.BROOM, "清空日志", self.logCard)
        self.clearLogButton.clicked.connect(self.clearLog)
        titleRow.addWidget(self.clearLogButton)

        self.saveLogButton = PushButton(FIF.SAVE, "保存日志", self.logCard)
        self.saveLogButton.clicked.connect(self.saveLog)
        titleRow.addWidget(self.saveLogButton)
        layout.addLayout(titleRow)

        self.logEdit = TextEdit(self.logCard)
        self.logEdit.setReadOnly(True)
        self.logEdit.setMinimumHeight(260)
        self.logEdit.setStyleSheet("QTextEdit { font-family: Consolas; font-size: 10pt; }")
        layout.addWidget(self.logEdit)

        self.vBoxLayout.addWidget(self.logCard, 1)

    def log(self, text: str, color: str | None = None):
        if not text:
            return

        plain_text = text.replace("\r\n", "\n").replace("\r", "\n")
        if color in ("red", "#C42B1C"):
            plain_text = f"[ERROR] {plain_text}"
        elif color == "#0078D4":
            plain_text = f"[CMD] {plain_text}"

        cursor = self.logEdit.textCursor()
        cursor.movePosition(QTextCursor.End)
        if not self.logEdit.document().isEmpty():
            cursor.insertText("\n")
        cursor.insertText(plain_text)
        scrollbar = self.logEdit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def showMessage(self, title: str, content: str, level: str = "info"):
        kwargs = dict(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )

        if level == "success":
            InfoBar.success(**kwargs)
        elif level == "warning":
            InfoBar.warning(**kwargs)
        elif level == "error":
            InfoBar.error(**kwargs)
        else:
            InfoBar.info(**kwargs)

    def browseFile(self):
        filePath, _ = QFileDialog.getOpenFileName(
            self,
            "选择固件",
            "",
            "Firmware Files (*.bin *.hex *.elf *.s19 *.srec)",
        )
        if filePath:
            self.filePathInput.setText(filePath)

    def chooseReadbackPath(self):
        if self.readbackPathInput is None:
            return

        default_dir = str(DirPathsInstance.LogDir)
        default_name = "stm32_readback.bin"
        current = self.readbackPathInput.text().strip()
        if current:
            default_dir = current
        elif self.filePathInput.text().strip():
            firmware_path = Path(self.filePathInput.text().strip())
            default_name = f"{firmware_path.stem}_readback.bin"
            default_dir = str(Path(default_dir) / default_name)
        else:
            default_dir = str(Path(default_dir) / default_name)

        filePath, _ = QFileDialog.getSaveFileName(
            self,
            "保存读取固件",
            default_dir,
            "Binary (*.bin);;Hex (*.hex);;S19 (*.s19);;SREC (*.srec)",
        )
        if filePath:
            self.readbackPathInput.setText(filePath)

    def clearLog(self):
        self.logEdit.clear()
        self.log("日志已清空。", "#888888")

    def saveLog(self):
        default_file = str(Path(DirPathsInstance.LogDir) / "stm32_programmer_ui.log")
        filePath, _ = QFileDialog.getSaveFileName(self, "保存日志", default_file, "Log Files (*.log *.txt)")
        if not filePath:
            return

        with open(filePath, "w", encoding="utf-8") as f:
            f.write(self.logEdit.toPlainText())

        self.showMessage("日志已保存", f"已保存到 {filePath}", "success")

    def scanLink(self):
        self._post_request(Stm32RequestPayload(action="scan"))

    def readInfo(self):
        self._post_request(Stm32RequestPayload(action="connect", connect=self._build_connect_config()))

    def startDownload(self):
        filePath = self.filePathInput.text().strip()
        if not filePath or not os.path.isfile(filePath):
            self.showMessage("无效固件", "请先选择有效的固件文件。", "warning")
            return

        self._post_request(
            Stm32RequestPayload(
                action="download",
                connect=self._build_connect_config(),
                file_path=filePath,
                address=self.downloadAddressInput.text().strip(),
                verify=self.verifySwitch.isChecked(),
                skip_erase=self.skipEraseSwitch.isChecked(),
                reset_after_download=self.resetAfterDownloadSwitch.isChecked(),
            )
        )

    def readFirmware(self):
        if self.readbackPathInput is None or self.readAddressInput is None or self.readSizeInput is None:
            return

        savePath = self.readbackPathInput.text().strip()
        if not savePath:
            self.showMessage("缺少保存路径", "请先选择固件读取后的保存路径。", "warning")
            return

        size_value = self._parse_positive_int(self.readSizeInput.text().strip())
        if size_value is None:
            self.showMessage("读取大小无效", "请输入十进制或十六进制的读取大小。", "warning")
            return

        self._post_request(
            Stm32RequestPayload(
                action="upload",
                connect=self._build_connect_config(),
                address=self.readAddressInput.text().strip() or self.FLASH_BASE_ADDRESS,
                size=size_value,
                save_path=savePath,
            )
        )

    def calculateChecksum(self):
        self._post_request(Stm32RequestPayload(action="checksum", connect=self._build_connect_config()))

    def readMemory(self):
        if self.memoryAddressInput is None or self.memoryCountInput is None:
            return

        count = self._parse_positive_int(self.memoryCountInput.text().strip())
        if count is None:
            self.showMessage("读取数量无效", "32-bit 数量请输入正整数。", "warning")
            return

        self._post_request(
            Stm32RequestPayload(
                action="read_memory",
                connect=self._build_connect_config(),
                address=self.memoryAddressInput.text().strip() or self.FLASH_BASE_ADDRESS,
                count=count,
            )
        )

    def _build_connect_config(self) -> Stm32ConnectConfig:
        probe = self._selected_probe()
        return Stm32ConnectConfig(
            probe_sn=probe.sn if probe else None,
            freq=self.freqInput.text().strip(),
            mode=self.modeCombo.currentText().strip(),
            reset=self.resetCombo.currentText().strip(),
        )

    def _selected_probe(self) -> Stm32ProbeInfo | None:
        index = self.stlinkCombo.currentIndex()
        if 0 <= index < len(self._probe_items):
            return self._probe_items[index]
        return None

    def _post_request(self, payload: Stm32RequestPayload):
        if payload.action in {"connect", "download"}:
            self._last_action_device_info = None
        QCoreApplication.postEvent(self._session, Stm32RequestEvent(payload))

    def set_buttons_enabled(self, enabled: bool):
        widgets = [
            self.scanBtn,
            self.connectBtn,
            self.downloadButton,
            self.checksumBtn,
            self.stlinkCombo,
            self.freqInput,
            self.modeCombo,
            self.resetCombo,
            self.uploadButton,
            self.memoryReadButton,
        ]
        for widget in widgets:
            if widget is not None:
                widget.setEnabled(enabled)

    def _apply_probe_items(self, probes: list[Stm32ProbeInfo]):
        self.stlinkCombo.clear()
        self._probe_items = probes

        if not self._probe_items:
            self._clear_info_labels()
            self._device_info = None
            self._last_action_device_info = None
            self.stateLabel.setText("未发现 ST-LINK")
            self.stateLabel.setStyleSheet("font-weight: bold; color: #C42B1C;")
            self.summaryLabel.setText("没有扫描到 ST-LINK，请检查 USB、驱动与供电。")
            self.summaryLabel.setStyleSheet("color: #C42B1C;")
            self.stlinkCombo.addItem("未发现 ST-LINK")
            self.log("No ST-LINK found.", "#C42B1C")
            return

        for item in self._probe_items:
            text = f"#{item.index} | SN {item.sn} | FW {item.fw or '--'} | AP {item.ap or '--'}"
            self.stlinkCombo.addItem(text)

        self.stlinkCombo.setCurrentIndex(0)
        self.stateLabel.setText(f"已发现 {len(self._probe_items)} 个探针")
        self.stateLabel.setStyleSheet("font-weight: bold; color: #0F7B0F;")
        self.summaryLabel.setText("扫描完成，可直接连接读取 MCU 信息。")
        self.summaryLabel.setStyleSheet("color: #0F7B0F;")

    def _apply_device_info(self, info: Stm32DeviceInfo | None):
        self._device_info = info
        if info is None:
            self._clear_info_labels()
            self.summaryLabel.setText("未解析到 MCU 信息，请查看日志输出。")
            self.summaryLabel.setStyleSheet("color: #C42B1C;")
            return

        self._set_info_label("probe_sn", info.probe_sn)
        self._set_info_label("probe_fw", info.probe_fw)
        self._set_info_label("board", info.board)
        self._set_info_label("voltage", info.voltage)
        self._set_info_label("device_name", info.device_name)
        self._set_info_label("device_id", info.device_id)
        self._set_info_label("revision", info.revision)
        self._set_info_label("flash_size", info.flash_size)
        self._set_info_label("cpu", info.cpu)
        self._set_info_label("connect_mode", info.connect_mode)
        self._set_info_label("reset_mode", info.reset_mode)
        self._set_info_label("bl_version", info.bl_version)

        self.summaryLabel.setText(f"设备: {info.device_name} | Flash: {info.flash_size} | ID: {info.device_id}")
        self.summaryLabel.setStyleSheet("color: #0F7B0F; font-weight: bold;")
        self.stateLabel.setText("MCU 已连接")
        self.stateLabel.setStyleSheet("font-weight: bold; color: #0F7B0F;")

        if self.readSizeInput is not None and info.flash_size_bytes:
            self.readSizeInput.setText(str(info.flash_size_bytes))

    def _apply_checksum_result(self, checksum: str | None):
        text = checksum or "--"
        self.checksumResultLabel.setText(f"最近一次 Flash 校验和：{text}")

    def _apply_memory_result(self, values: list[Stm32MemoryValue]):
        if self.memoryResultLabel is None:
            return

        if not values:
            self.memoryResultLabel.setText("最近一次读取结果：未解析到内存内容")
            return

        lines = [f"{item.address} = {item.value}" for item in values]
        self.memoryResultLabel.setText("最近一次读取结果：" + " | ".join(lines))

    def _handle_action_finished(self, payload: ActionFinishedPayload):
        action = payload.action
        if payload.success:
            if action == "connect":
                if self._last_action_device_info is None:
                    self.showMessage("连接完成", "命令执行成功，但未解析到 MCU 信息。", "warning")
                else:
                    self.showMessage("连接成功", "已读取 ST-LINK 与 MCU 信息。", "success")
            elif action == "download":
                if self._last_action_device_info is None:
                    self.showMessage("下载成功", "固件已成功写入 MCU。", "success")
                else:
                    self.showMessage("下载成功", "固件已成功写入 MCU。", "success")
            elif action == "upload":
                self.showMessage("读取成功", "已成功从 MCU 读取固件。", "success")
            elif action == "checksum":
                self.showMessage("校验完成", "已完成 Flash 校验和计算。", "success")
            elif action == "read_memory":
                self.showMessage("读取完成", "内存数据读取完成。", "success")
            return

        if payload.exit_status is None:
            self.stateLabel.setText("执行失败")
            self.stateLabel.setStyleSheet("font-weight: bold; color: #C42B1C;")
            return

        self.stateLabel.setText("操作失败")
        self.stateLabel.setStyleSheet("font-weight: bold; color: #C42B1C;")
        self.showMessage("操作失败", f"{action or '未知操作'} 返回码: {payload.exit_code}", "error")

    @staticmethod
    def _log_color_for_level(level: str) -> str | None:
        if level == "error":
            return "#C42B1C"
        if level == "command":
            return "#0078D4"
        return None

    def _parse_positive_int(self, text: str) -> int | None:
        if not text:
            return None
        try:
            value = int(text, 0)
        except ValueError:
            return None
        return value if value > 0 else None

    def _set_info_label(self, key: str, value: str):
        if key in self.infoLabels:
            self.infoLabels[key].setText(value or "--")

    def _clear_info_labels(self):
        for label in self.infoLabels.values():
            label.setText("--")

    def _reset_device_info(self):
        self._device_info = None
        self._last_action_device_info = None
        self._clear_info_labels()
        self.summaryLabel.setText("等待连接 MCU…")
        self.summaryLabel.setStyleSheet("color: #777777;")
        self.checksumResultLabel.setText("最近一次 Flash 校验和：--")
        self.stateLabel.setText("未连接")
        self.stateLabel.setStyleSheet("font-weight: bold; color: #C42B1C;")
        if self.memoryResultLabel is not None:
            self.memoryResultLabel.setText("最近一次读取结果：--")
