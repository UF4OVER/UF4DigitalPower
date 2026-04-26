# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 04-25 13:14
#  @FileName: daplink_flash_page.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : Powered By GPT-5.4
#  @Python  :
# -------------------------------

from __future__ import annotations

import os
from pathlib import Path

from PyQt5.QtCore import QCoreApplication, QTimer
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QFileDialog, QGridLayout, QHBoxLayout, QProgressBar, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    ComboBox,
    FluentIcon as FIF,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SubtitleLabel,
    SwitchButton,
    TextEdit,
    TitleLabel,
    ProgressBar
)

from Config import DirPathsInstance, logger
from ..Core.utility import showMessage
from ..Core import daplink_pyocd_session as daplink_pyocd


class DaplinkFlashPage(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("DaplinkFlashPage")

        self._probe_items: list[daplink_pyocd.DaplinkProbeInfo] = []
        self._all_target_items: list[daplink_pyocd.DaplinkTargetInfo] = []
        self._target_items: list[daplink_pyocd.DaplinkTargetInfo] = []
        self._device_info: daplink_pyocd.DaplinkDeviceInfo | None = None

        self.view = QWidget(self)
        self.view.setObjectName("daplinkScrollWidget")
        self.vBoxLayout = QVBoxLayout(self.view)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.vBoxLayout.setSpacing(12)

        self.titleLabel = TitleLabel("DAPLink pyOCD DOWNLOAD", self.view)
        self.vBoxLayout.addWidget(self.titleLabel)

        self._init_connection_card()
        self._init_info_card()
        self._init_download_card()
        self._init_log_card()

        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self._session = daplink_pyocd.DaplinkPyocdSession(_event_receiver=self, parent=self)
        self._reset_device_info()

        QTimer.singleShot(0, self.reloadPackTargets)
        QTimer.singleShot(0, self.scanProbe)

    def event(self, e):
        event_type = e.type()

        if event_type == int(daplink_pyocd.DaplinkProgrammerEventType.LOG):
            self.log(e.payload.text, self._log_color_for_level(e.payload.level))
            return True

        if event_type == int(daplink_pyocd.DaplinkProgrammerEventType.MESSAGE):
            self.showMessage(e.payload.title, e.payload.content, e.payload.level)
            return True

        if event_type == int(daplink_pyocd.DaplinkProgrammerEventType.STATE):
            self.set_buttons_enabled(not e.payload.busy)
            return True

        if event_type == int(daplink_pyocd.DaplinkProgrammerEventType.PROBES):
            self._apply_probe_items(e.payload.probes)
            return True

        if event_type == int(daplink_pyocd.DaplinkProgrammerEventType.TARGETS):
            self._apply_target_items(e.payload.targets, e.payload.pack_paths)
            return True

        if event_type == int(daplink_pyocd.DaplinkProgrammerEventType.DEVICE_INFO):
            self._apply_device_info(e.payload.info)
            return True

        if event_type == int(daplink_pyocd.DaplinkProgrammerEventType.PROGRESS):
            self._apply_progress(e.payload.percent)
            return True

        if event_type == int(daplink_pyocd.DaplinkProgrammerEventType.ACTION_FINISHED):
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

        title = SubtitleLabel("DAPLink connect", self.connectCard)
        layout.addWidget(title)

        probe_row = QHBoxLayout()
        self.probeCombo = ComboBox(self.connectCard)
        self.probeCombo.setPlaceholderText("Scan and Connect DAPLink")
        self.probeCombo.setMinimumWidth(360)
        probe_row.addWidget(self.probeCombo, 1)

        self.scanProbeBtn = PushButton(FIF.SYNC, "Scan DAPLink", self.connectCard)
        self.scanProbeBtn.clicked.connect(self.scanProbe)
        probe_row.addWidget(self.scanProbeBtn)

        self.connectBtn = PrimaryPushButton(FIF.LINK, "connect", self.connectCard)
        self.connectBtn.clicked.connect(self.readInfo)
        probe_row.addWidget(self.connectBtn)
        layout.addLayout(probe_row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        grid.addWidget(BodyLabel("local Pack Target", self.connectCard), 0, 0)
        self.targetCombo = ComboBox(self.connectCard)
        self.targetCombo.setPlaceholderText("load target from Resources/Tools/Pack ")
        self.targetCombo.setMinimumWidth(360)
        self.targetCombo.currentIndexChanged.connect(self._on_target_changed)
        grid.addWidget(self.targetCombo, 0, 1)

        self.reloadPackBtn = PushButton(FIF.ROTATE, "reload Pack", self.connectCard)
        self.reloadPackBtn.clicked.connect(self.reloadPackTargets)
        grid.addWidget(self.reloadPackBtn, 0, 2)

        grid.addWidget(BodyLabel("Target filter", self.connectCard), 1, 0)
        self.targetFilterInput = LineEdit(self.connectCard)
        self.targetFilterInput.setPlaceholderText("input STM32G474 / G474 / RETx and Other Keywords")
        self.targetFilterInput.setText("G474RBT")  # 默认芯片支持
        self.targetFilterInput.textChanged.connect(self._apply_target_filter)
        grid.addWidget(self.targetFilterInput, 1, 1)

        grid.addWidget(BodyLabel("SWD freq", self.connectCard), 2, 0)
        self.frequencyInput = LineEdit(self.connectCard)
        self.frequencyInput.setText("1000000")
        self.frequencyInput.setPlaceholderText("like 1000000 / 4M / 4000K")
        grid.addWidget(self.frequencyInput, 2, 1)

        grid.addWidget(BodyLabel("connect mode", self.connectCard), 2, 2)
        self.connectModeCombo = ComboBox(self.connectCard)
        self.connectModeCombo.addItems(["halt", "under-reset", "pre-reset", "attach"])
        self.connectModeCombo.setCurrentText("halt")
        grid.addWidget(self.connectModeCombo, 2, 3)

        grid.addWidget(BodyLabel("state", self.connectCard), 3, 0)
        self.stateLabel = BodyLabel("not Connected", self.connectCard)
        self.stateLabel.setStyleSheet("font-weight: bold; color: #C42B1C;")
        grid.addWidget(self.stateLabel, 3, 1)

        grid.addWidget(BodyLabel("Pack source", self.connectCard), 3, 2)
        self.packSummaryLabel = BodyLabel("Wait for the local to load Pack…", self.connectCard)
        self.packSummaryLabel.setWordWrap(True)
        grid.addWidget(self.packSummaryLabel, 3, 3)
        layout.addLayout(grid)

        self.targetSummaryLabel = BodyLabel("Show only Resources/Tools/Pack after being cropped target。", self.connectCard)
        self.targetSummaryLabel.setWordWrap(True)
        layout.addWidget(self.targetSummaryLabel)

        self.vBoxLayout.addWidget(self.connectCard)

    def _init_info_card(self):
        self.infoCard = CardWidget(self.view)
        layout = QVBoxLayout(self.infoCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = SubtitleLabel("probe / Target infor", self.infoCard)
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        self.infoLabels: dict[str, BodyLabel] = {}

        fields = [
            ("probe_uid", "Probe UID"),
            ("probe_description", "Probe"),
            ("vendor", "Vendor"),
            ("product", "Product"),
            ("target_name", "pyOCD Target"),
            ("part_number", "Part Number"),
            ("family", "Family"),
            ("flash_start", "Flash Start"),
            ("flash_size", "Flash Size"),
            ("ram_size", "RAM Size"),
            ("pack_name", "Pack Name"),
            ("pack_version", "Pack Version"),
        ]

        for index, (key, title_text) in enumerate(fields):
            row = index // 2
            column = (index % 2) * 2
            grid.addWidget(BodyLabel(title_text, self.infoCard), row, column)
            value_label = BodyLabel("--", self.infoCard)
            value_label.setStyleSheet("font-weight: bold;")
            value_label.setWordWrap(True)
            grid.addWidget(value_label, row, column + 1)
            self.infoLabels[key] = value_label

        layout.addLayout(grid)

        self.summaryLabel = BodyLabel("Wait for the DAPLink to connect with the target chip…", self.infoCard)
        self.summaryLabel.setWordWrap(True)
        self.summaryLabel.setStyleSheet("color: #777777;")
        layout.addWidget(self.summaryLabel)

        self.vBoxLayout.addWidget(self.infoCard)

    def _init_download_card(self):
        self.downloadCard = CardWidget(self.view)
        layout = QVBoxLayout(self.downloadCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = SubtitleLabel("Download Firmware Using PyOCD", self.downloadCard)
        layout.addWidget(title)

        file_row = QHBoxLayout()
        self.filePathInput = LineEdit(self.downloadCard)
        self.filePathInput.setPlaceholderText("Select the firmware to download（.bin/.hex/.elf）")
        file_row.addWidget(self.filePathInput, 1)

        self.browseButton = PushButton(FIF.FOLDER, "browse", self.downloadCard)
        self.browseButton.clicked.connect(self.browseFile)
        file_row.addWidget(self.browseButton)
        layout.addLayout(file_row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        grid.addWidget(BodyLabel("Bin Starting address", self.downloadCard), 0, 0)
        self.baseAddressInput = LineEdit(self.downloadCard)
        self.baseAddressInput.setPlaceholderText("If left blank, it is used Flash start address in Pack")
        grid.addWidget(self.baseAddressInput, 0, 1)

        grid.addWidget(BodyLabel("Erase strategy", self.downloadCard), 0, 2)
        self.eraseModeCombo = ComboBox(self.downloadCard)
        self.eraseModeCombo.addItems(["sector", "chip", "auto"])
        self.eraseModeCombo.setCurrentText("sector")
        grid.addWidget(self.eraseModeCombo, 0, 3)

        self.smartFlashSwitch = SwitchButton(self.downloadCard)
        self.smartFlashSwitch.setOnText("Smart Flash")
        self.smartFlashSwitch.setOffText("Smart Flash")
        self.smartFlashSwitch.setChecked(True)
        grid.addWidget(self.smartFlashSwitch, 1, 0)

        self.trustCrcSwitch = SwitchButton(self.downloadCard)
        self.trustCrcSwitch.setOnText("Trust CRC")
        self.trustCrcSwitch.setOffText("Trust CRC")
        self.trustCrcSwitch.setChecked(False)
        grid.addWidget(self.trustCrcSwitch, 1, 1)

        self.resetAfterDownloadSwitch = SwitchButton(self.downloadCard)
        self.resetAfterDownloadSwitch.setOnText("Reset when finished")
        self.resetAfterDownloadSwitch.setOffText("Reset when finished")
        self.resetAfterDownloadSwitch.setChecked(True)
        grid.addWidget(self.resetAfterDownloadSwitch, 1, 2)

        self.downloadButton = PrimaryPushButton(FIF.DOWNLOAD, "Start downloading", self.downloadCard)
        self.downloadButton.clicked.connect(self.startDownload)
        grid.addWidget(self.downloadButton, 1, 3)
        layout.addLayout(grid)

        self.progressBar = ProgressBar(self.downloadCard)
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        layout.addWidget(self.progressBar)

        self.progressLabel = BodyLabel("下载进度：0%", self.downloadCard)
        layout.addWidget(self.progressLabel)

        self.vBoxLayout.addWidget(self.downloadCard)

    def _init_log_card(self):
        self.logCard = CardWidget(self.view)
        layout = QVBoxLayout(self.logCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title_row.addWidget(SubtitleLabel("运行日志", self.logCard))
        title_row.addStretch(1)

        self.clearLogButton = PushButton(FIF.BROOM, "清空日志", self.logCard)
        self.clearLogButton.clicked.connect(self.clearLog)
        title_row.addWidget(self.clearLogButton)

        self.saveLogButton = PushButton(FIF.SAVE, "保存日志", self.logCard)
        self.saveLogButton.clicked.connect(self.saveLog)
        title_row.addWidget(self.saveLogButton)
        layout.addLayout(title_row)

        self.logEdit = TextEdit(self.logCard)
        self.logEdit.setReadOnly(True)
        self.logEdit.setMinimumHeight(260)
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
        logger.info(f"{self.__class__.__name__}: {text}", extra={"color": color})

    def showMessage(self, title: str, content: str, level: str = "info"):
        showMessage(self, title, content, level)

    def browseFile(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select firmware",
            "",
            "Firmware Files (*.bin *.hex *.elf *.axf)",
        )
        if file_path:
            self.filePathInput.setText(file_path)

    def clearLog(self):
        self.logEdit.clear()
        self.log("The log has been cleared.", "#888888")

    def saveLog(self):
        default_file = str(Path(DirPathsInstance.LogDir) / "daplink_pyocd_ui.log")
        file_path, _ = QFileDialog.getSaveFileName(self, "Save logs", default_file, "Log Files (*.log *.txt)")
        if not file_path:
            return

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.logEdit.toPlainText())

        self.showMessage("Log saved", f"saved {file_path}", "success")

    def reloadPackTargets(self):
        self._post_request(daplink_pyocd.DaplinkRequestPayload(action="load_targets"))

    def scanProbe(self):
        self._post_request(daplink_pyocd.DaplinkRequestPayload(action="scan_probes"))

    def readInfo(self):
        self._post_request(daplink_pyocd.DaplinkRequestPayload(action="connect", connect=self._build_connect_config()))

    def startDownload(self):
        file_path = self.filePathInput.text().strip()
        if not file_path or not os.path.isfile(file_path):
            self.showMessage("Invalid firmware", "Please select a valid firmware file first.", "warning")
            return

        if self._selected_target() is None:
            self.showMessage("Missing Target", "Please select the target from the local pack first.", "warning")
            return

        base_address = self.baseAddressInput.text().strip()
        if base_address:
            try:
                int(base_address, 0)
            except ValueError:
                self.showMessage("The address is invalid", "The bin starting address must be a decimal or hexadecimal number.", "warning")
                return

        self._post_request(
            daplink_pyocd.DaplinkRequestPayload(
                action="download",
                connect=self._build_connect_config(),
                file_path=file_path,
                base_address=base_address,
                erase_mode=self.eraseModeCombo.currentText().strip(),
                smart_flash=self.smartFlashSwitch.isChecked(),
                trust_crc=self.trustCrcSwitch.isChecked(),
                reset_after_download=self.resetAfterDownloadSwitch.isChecked(),
            )
        )

    def _build_connect_config(self) -> daplink_pyocd.DaplinkConnectConfig:
        probe = self._selected_probe()
        target = self._selected_target()
        return daplink_pyocd.DaplinkConnectConfig(
            probe_uid=probe.uid if probe else None,
            target_name=target.target_name if target else "",
            frequency=self.frequencyInput.text().strip(),
            connect_mode=self.connectModeCombo.currentText().strip(),
        )

    def _selected_probe(self) -> daplink_pyocd.DaplinkProbeInfo | None:
        index = self.probeCombo.currentIndex()
        if 0 <= index < len(self._probe_items):
            return self._probe_items[index]
        return None

    def _selected_target(self) -> daplink_pyocd.DaplinkTargetInfo | None:
        index = self.targetCombo.currentIndex()
        if 0 <= index < len(self._target_items):
            return self._target_items[index]
        return None

    def _post_request(self, payload: daplink_pyocd.DaplinkRequestPayload):
        QCoreApplication.postEvent(self._session, daplink_pyocd.DaplinkRequestEvent(payload))

    def set_buttons_enabled(self, enabled: bool):
        widgets = [
            self.scanProbeBtn,
            self.connectBtn,
            self.reloadPackBtn,
            self.downloadButton,
            self.probeCombo,
            self.targetCombo,
            self.targetFilterInput,
            self.frequencyInput,
            self.connectModeCombo,
            self.browseButton,
            self.eraseModeCombo,
        ]
        for widget in widgets:
            widget.setEnabled(enabled)

    def _apply_probe_items(self, probes: list[daplink_pyocd.DaplinkProbeInfo]):
        self.probeCombo.clear()
        self._probe_items = probes

        if not probes:
            self.probeCombo.addItem("Not found DAPLink / CMSIS-DAP")
            self.stateLabel.setText("No debugger found")
            self.stateLabel.setStyleSheet("font-weight: bold; color: #C42B1C;")
            self.summaryLabel.setText("DAPLink / CMSIS-DAP is not scanned, please check the USB, driver and firmware.")
            self.summaryLabel.setStyleSheet("color: #C42B1C;")
            return

        for item in probes:
            text = f"#{item.index} | {item.description} | UID {item.uid}"
            self.probeCombo.addItem(text)

        self.probeCombo.setCurrentIndex(0)
        self.stateLabel.setText(f"已发现 {len(probes)} 个调试器")
        self.stateLabel.setStyleSheet("font-weight: bold; color: #0F7B0F;")
        self.summaryLabel.setText("调试器扫描完成，可直接连接读取目标信息。")
        self.summaryLabel.setStyleSheet("color: #0F7B0F;")

    def _apply_target_items(self, targets: list[daplink_pyocd.DaplinkTargetInfo], pack_paths: list[str]):
        self._all_target_items = targets
        self._target_items = []

        if not targets:
            self.targetCombo.clear()
            self.targetCombo.addItem("未发现本地 Pack Target")
            self.packSummaryLabel.setText("Resources/Tools/Pack 中没有可用 .pack 文件。")
            self.packSummaryLabel.setStyleSheet("color: #C42B1C;")
            self.targetSummaryLabel.setText("请先放入 CMSIS Device Family Pack。")
            self.targetSummaryLabel.setStyleSheet("color: #C42B1C;")
            return

        pack_names = sorted({Path(path).name for path in pack_paths})
        self.packSummaryLabel.setText(f"已加载 {len(pack_names)} 个 Pack：{', '.join(pack_names)}")
        self.packSummaryLabel.setStyleSheet("color: #0F7B0F;")
        self._apply_target_filter(self.targetFilterInput.text())

    def _apply_target_filter(self, text: str = ""):
        keyword = (text or "").strip().lower()
        current_target_name = self._selected_target().target_name if self._selected_target() else ""

        if keyword:
            filtered = [
                item for item in self._all_target_items
                if keyword in item.part_number.lower()
                or keyword in item.target_name.lower()
                or keyword in item.family.lower()
            ]
        else:
            filtered = list(self._all_target_items)

        self.targetCombo.blockSignals(True)
        self.targetCombo.clear()
        self._target_items = filtered

        if not filtered:
            self.targetCombo.addItem("没有匹配的 target")
            self.targetCombo.blockSignals(False)
            self.targetSummaryLabel.setText("当前筛选没有命中 target，请尝试输入 STM32G474、G474、RETx 等关键字。")
            self.targetSummaryLabel.setStyleSheet("color: #C42B1C;")
            return

        for item in filtered:
            text = f"{item.part_number} | {item.flash_size} Flash | {item.ram_size} RAM"
            self.targetCombo.addItem(text)

        selected_index = 0
        if current_target_name:
            for index, item in enumerate(filtered):
                if item.target_name == current_target_name:
                    selected_index = index
                    break

        self.targetCombo.setCurrentIndex(selected_index)
        self.targetCombo.blockSignals(False)
        self._on_target_changed()

    def _on_target_changed(self):
        target = self._selected_target()
        if target is None:
            if self._all_target_items:
                self.targetSummaryLabel.setText("请选择一个本地 Pack target。若你的芯片是 STM32G474，可直接在筛选框输入 STM32G474。")
                self.targetSummaryLabel.setStyleSheet("color: #777777;")
            return

        self.targetSummaryLabel.setText(
            f"当前 Target：{target.part_number} | pyOCD ID: {target.target_name} | Flash: {target.flash_start} ({target.flash_size}) | Pack: {target.pack_name} {target.pack_version}"
        )
        self.targetSummaryLabel.setStyleSheet("color: #777777;")
        if not self.baseAddressInput.text().strip() and target.flash_start != "--":
            self.baseAddressInput.setText(target.flash_start)

    def _apply_device_info(self, info: daplink_pyocd.DaplinkDeviceInfo | None):
        self._device_info = info
        if info is None:
            self._clear_info_labels()
            self.summaryLabel.setText("未解析到探针或目标信息，请查看日志输出。")
            self.summaryLabel.setStyleSheet("color: #C42B1C;")
            return

        for key, label in self.infoLabels.items():
            label.setText(getattr(info, key, "--") or "--")

        self.stateLabel.setText("已连接")
        self.stateLabel.setStyleSheet("font-weight: bold; color: #0F7B0F;")
        self.summaryLabel.setText(
            f"Probe: {info.probe_description} | Device: {info.part_number} | Flash: {info.flash_size} | Pack: {info.pack_name} {info.pack_version}"
        )
        self.summaryLabel.setStyleSheet("color: #0F7B0F; font-weight: bold;")

    def _apply_progress(self, percent: float):
        value = max(0, min(100, int(round(percent))))
        self.progressBar.setValue(value)
        self.progressLabel.setText(f"下载进度：{value}%")

    def _handle_action_finished(self, payload: daplink_pyocd.ActionFinishedPayload):
        if payload.success:
            if payload.action == "connect":
                self.showMessage("连接成功", "已读取 DAPLink 与目标芯片信息。", "success")
            elif payload.action == "download":
                self.showMessage("下载成功", "固件已通过 pyOCD 写入目标芯片。", "success")
            return

        if payload.action == "download":
            self.progressBar.setValue(0)
            self.progressLabel.setText("下载进度：0%")

        self.stateLabel.setText("操作失败")
        self.stateLabel.setStyleSheet("font-weight: bold; color: #C42B1C;")

    @staticmethod
    def _log_color_for_level(level: str) -> str | None:
        if level == "error":
            return "#C42B1C"
        if level == "command":
            return "#0078D4"
        return None

    def _clear_info_labels(self):
        for label in self.infoLabels.values():
            label.setText("--")

    def _reset_device_info(self):
        self._device_info = None
        self._clear_info_labels()
        self.summaryLabel.setText("等待连接 DAPLink 与目标芯片…")
        self.summaryLabel.setStyleSheet("color: #777777;")
        self.stateLabel.setText("未连接")
        self.stateLabel.setStyleSheet("font-weight: bold; color: #C42B1C;")
        self.progressBar.setValue(0)
        self.progressLabel.setText("下载进度：0%")

