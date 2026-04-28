# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path

from PyQt5.QtCore import QCoreApplication, QEvent, QTimer
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QFileDialog, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    ComboBox,
    FluentIcon as FIF,
    LineEdit,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    ScrollArea,
    SubtitleLabel,
    SwitchButton,
    TextEdit,
    TitleLabel,
)

from Config import DirPathsInstance, logger
from app.Core.utility import showMessage
from app.Core.Session import session_daplink as daplink_pyocd


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

        self.titleLabel = TitleLabel(self.view)
        self.vBoxLayout.addWidget(self.titleLabel)

        self._init_connection_card()
        self._init_info_card()
        self._init_download_card()
        self._init_log_card()

        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self._session = daplink_pyocd.DaplinkPyocdSession(_event_receiver=self, parent=self)
        self._reset_device_info()
        self._retranslate_ui()

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

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.LanguageChange:
            self._retranslate_ui()

    def closeEvent(self, event):
        self._session.shutdown()
        super().closeEvent(event)

    def _init_connection_card(self):
        self.connectCard = CardWidget(self.view)
        layout = QVBoxLayout(self.connectCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.connectionCardTitle = SubtitleLabel(self.connectCard)
        layout.addWidget(self.connectionCardTitle)

        probe_row = QHBoxLayout()
        self.probeCombo = ComboBox(self.connectCard)
        self.probeCombo.setMinimumWidth(360)
        probe_row.addWidget(self.probeCombo, 1)

        self.scanProbeBtn = PushButton(FIF.SYNC, "", self.connectCard)
        self.scanProbeBtn.clicked.connect(self.scanProbe)
        probe_row.addWidget(self.scanProbeBtn)

        self.connectBtn = PrimaryPushButton(FIF.LINK, "", self.connectCard)
        self.connectBtn.clicked.connect(self.readInfo)
        probe_row.addWidget(self.connectBtn)
        layout.addLayout(probe_row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        self.targetLabel = BodyLabel(self.connectCard)
        grid.addWidget(self.targetLabel, 0, 0)
        self.targetCombo = ComboBox(self.connectCard)
        self.targetCombo.setMinimumWidth(360)
        self.targetCombo.currentIndexChanged.connect(self._on_target_changed)
        grid.addWidget(self.targetCombo, 0, 1)

        self.reloadPackBtn = PushButton(FIF.ROTATE, "", self.connectCard)
        self.reloadPackBtn.clicked.connect(self.reloadPackTargets)
        grid.addWidget(self.reloadPackBtn, 0, 2)

        self.targetFilterLabel = BodyLabel(self.connectCard)
        grid.addWidget(self.targetFilterLabel, 1, 0)
        self.targetFilterInput = LineEdit(self.connectCard)
        self.targetFilterInput.setText("G474RBT")
        self.targetFilterInput.textChanged.connect(self._apply_target_filter)
        grid.addWidget(self.targetFilterInput, 1, 1)

        self.frequencyLabel = BodyLabel(self.connectCard)
        grid.addWidget(self.frequencyLabel, 2, 0)
        self.frequencyInput = LineEdit(self.connectCard)
        self.frequencyInput.setText("1000000")
        grid.addWidget(self.frequencyInput, 2, 1)

        self.connectModeLabel = BodyLabel(self.connectCard)
        grid.addWidget(self.connectModeLabel, 2, 2)
        self.connectModeCombo = ComboBox(self.connectCard)
        self.connectModeCombo.addItems(["halt", "under-reset", "pre-reset", "attach"])
        self.connectModeCombo.setCurrentText("halt")
        grid.addWidget(self.connectModeCombo, 2, 3)

        self.stateTitleLabel = BodyLabel(self.connectCard)
        grid.addWidget(self.stateTitleLabel, 3, 0)
        self.stateLabel = BodyLabel(self.connectCard)
        self.stateLabel.setStyleSheet("font-weight: bold; color: #C42B1C;")
        grid.addWidget(self.stateLabel, 3, 1)

        self.packSourceTitleLabel = BodyLabel(self.connectCard)
        grid.addWidget(self.packSourceTitleLabel, 3, 2)
        self.packSummaryLabel = BodyLabel(self.connectCard)
        self.packSummaryLabel.setWordWrap(True)
        grid.addWidget(self.packSummaryLabel, 3, 3)
        layout.addLayout(grid)

        self.targetSummaryLabel = BodyLabel(self.connectCard)
        self.targetSummaryLabel.setWordWrap(True)
        layout.addWidget(self.targetSummaryLabel)
        self.vBoxLayout.addWidget(self.connectCard)

    def _init_info_card(self):
        self.infoCard = CardWidget(self.view)
        layout = QVBoxLayout(self.infoCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.infoCardTitle = SubtitleLabel(self.infoCard)
        layout.addWidget(self.infoCardTitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        self.infoLabels: dict[str, BodyLabel] = {}
        self.infoTitleLabels: dict[str, BodyLabel] = {}

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
            title_label = BodyLabel(self.infoCard)
            grid.addWidget(title_label, row, column)
            value_label = BodyLabel("--", self.infoCard)
            value_label.setStyleSheet("font-weight: bold;")
            value_label.setWordWrap(True)
            grid.addWidget(value_label, row, column + 1)
            self.infoTitleLabels[key] = title_label
            self.infoLabels[key] = value_label
            title_label.setProperty("sourceText", title_text)

        layout.addLayout(grid)

        self.summaryLabel = BodyLabel(self.infoCard)
        self.summaryLabel.setWordWrap(True)
        self.summaryLabel.setStyleSheet("color: #777777;")
        layout.addWidget(self.summaryLabel)
        self.vBoxLayout.addWidget(self.infoCard)

    def _init_download_card(self):
        self.downloadCard = CardWidget(self.view)
        layout = QVBoxLayout(self.downloadCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.downloadCardTitle = SubtitleLabel(self.downloadCard)
        layout.addWidget(self.downloadCardTitle)

        file_row = QHBoxLayout()
        self.filePathInput = LineEdit(self.downloadCard)
        file_row.addWidget(self.filePathInput, 1)

        self.browseButton = PushButton(FIF.FOLDER, "", self.downloadCard)
        self.browseButton.clicked.connect(self.browseFile)
        file_row.addWidget(self.browseButton)
        layout.addLayout(file_row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        self.baseAddressLabel = BodyLabel(self.downloadCard)
        grid.addWidget(self.baseAddressLabel, 0, 0)
        self.baseAddressInput = LineEdit(self.downloadCard)
        grid.addWidget(self.baseAddressInput, 0, 1)

        self.eraseModeLabel = BodyLabel(self.downloadCard)
        grid.addWidget(self.eraseModeLabel, 0, 2)
        self.eraseModeCombo = ComboBox(self.downloadCard)
        self.eraseModeCombo.addItems(["sector", "chip", "auto"])
        self.eraseModeCombo.setCurrentText("sector")
        grid.addWidget(self.eraseModeCombo, 0, 3)

        self.smartFlashSwitch = SwitchButton(self.downloadCard)
        self.smartFlashSwitch.setChecked(True)
        grid.addWidget(self.smartFlashSwitch, 1, 0)

        self.trustCrcSwitch = SwitchButton(self.downloadCard)
        self.trustCrcSwitch.setChecked(False)
        grid.addWidget(self.trustCrcSwitch, 1, 1)

        self.resetAfterDownloadSwitch = SwitchButton(self.downloadCard)
        self.resetAfterDownloadSwitch.setChecked(True)
        grid.addWidget(self.resetAfterDownloadSwitch, 1, 2)

        self.downloadButton = PrimaryPushButton(FIF.DOWNLOAD, "", self.downloadCard)
        self.downloadButton.clicked.connect(self.startDownload)
        grid.addWidget(self.downloadButton, 1, 3)
        layout.addLayout(grid)

        self.progressBar = ProgressBar(self.downloadCard)
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        layout.addWidget(self.progressBar)

        self.progressLabel = BodyLabel(self.downloadCard)
        layout.addWidget(self.progressLabel)
        self.vBoxLayout.addWidget(self.downloadCard)

    def _init_log_card(self):
        self.logCard = CardWidget(self.view)
        layout = QVBoxLayout(self.logCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        self.logCardTitle = SubtitleLabel(self.logCard)
        title_row.addWidget(self.logCardTitle)
        title_row.addStretch(1)

        self.clearLogButton = PushButton(FIF.BROOM, "", self.logCard)
        self.clearLogButton.clicked.connect(self.clearLog)
        title_row.addWidget(self.clearLogButton)

        self.saveLogButton = PushButton(FIF.SAVE, "", self.logCard)
        self.saveLogButton.clicked.connect(self.saveLog)
        title_row.addWidget(self.saveLogButton)
        layout.addLayout(title_row)

        self.logEdit = TextEdit(self.logCard)
        self.logEdit.setReadOnly(True)
        self.logEdit.setMinimumHeight(260)
        layout.addWidget(self.logEdit)
        self.vBoxLayout.addWidget(self.logCard, 1)

    def _retranslate_ui(self):
        self.titleLabel.setText(self.tr("DAPLink pyOCD Download"))
        self.connectionCardTitle.setText(self.tr("DAPLink connection"))
        self.probeCombo.setPlaceholderText(self.tr("Scan and select DAPLink"))
        self.scanProbeBtn.setText(self.tr("Scan DAPLink"))
        self.connectBtn.setText(self.tr("Connect"))

        self.targetLabel.setText(self.tr("Local pack target"))
        self.targetCombo.setPlaceholderText(self.tr("Load targets from Resources/Tools/Pack"))
        self.reloadPackBtn.setText(self.tr("Reload pack"))
        self.targetFilterLabel.setText(self.tr("Target filter"))
        self.targetFilterInput.setPlaceholderText(self.tr("Enter STM32G474 / G474 / RETx or other keywords"))
        self.frequencyLabel.setText(self.tr("SWD frequency"))
        self.frequencyInput.setPlaceholderText(self.tr("For example 1000000 / 4M / 4000K"))
        self.connectModeLabel.setText(self.tr("Connect mode"))
        self.stateTitleLabel.setText(self.tr("State"))
        self.packSourceTitleLabel.setText(self.tr("Pack source"))

        self.infoCardTitle.setText(self.tr("Probe / target info"))
        for key, label in self.infoTitleLabels.items():
            label.setText(self.tr(label.property("sourceText")))

        self.downloadCardTitle.setText(self.tr("Download firmware with pyOCD"))
        self.filePathInput.setPlaceholderText(self.tr("Select the firmware file to download (.bin/.hex/.elf)"))
        self.browseButton.setText(self.tr("Browse"))
        self.baseAddressLabel.setText(self.tr("Bin start address"))
        self.baseAddressInput.setPlaceholderText(self.tr("If empty, use the flash start address from the pack"))
        self.eraseModeLabel.setText(self.tr("Erase strategy"))
        self.smartFlashSwitch.setOnText(self.tr("Smart Flash"))
        self.smartFlashSwitch.setOffText(self.tr("Smart Flash"))
        self.trustCrcSwitch.setOnText(self.tr("Trust CRC"))
        self.trustCrcSwitch.setOffText(self.tr("Trust CRC"))
        self.resetAfterDownloadSwitch.setOnText(self.tr("Reset when finished"))
        self.resetAfterDownloadSwitch.setOffText(self.tr("Reset when finished"))
        self.downloadButton.setText(self.tr("Start download"))

        self.logCardTitle.setText(self.tr("Run log"))
        self.clearLogButton.setText(self.tr("Clear log"))
        self.saveLogButton.setText(self.tr("Save log"))

        self._apply_progress(self.progressBar.value())
        if self._device_info is None and not self.summaryLabel.text():
            self._reset_device_info()

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
            self.tr("Select firmware"),
            "",
            self.tr("Firmware Files (*.bin *.hex *.elf *.axf)"),
        )
        if file_path:
            self.filePathInput.setText(file_path)

    def clearLog(self):
        self.logEdit.clear()
        self.log(self.tr("The log has been cleared."), "#888888")

    def saveLog(self):
        default_file = str(Path(DirPathsInstance.LogDir) / "daplink_pyocd_ui.log")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save logs"),
            default_file,
            self.tr("Log Files (*.log *.txt)"),
        )
        if not file_path:
            return

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.logEdit.toPlainText())

        self.showMessage(self.tr("Log saved"), self.tr("Saved to {path}").format(path=file_path), "success")

    def reloadPackTargets(self):
        self._post_request(daplink_pyocd.DaplinkRequestPayload(action="load_targets"))

    def scanProbe(self):
        self._post_request(daplink_pyocd.DaplinkRequestPayload(action="scan_probes"))

    def readInfo(self):
        self._post_request(daplink_pyocd.DaplinkRequestPayload(action="connect", connect=self._build_connect_config()))

    def startDownload(self):
        file_path = self.filePathInput.text().strip()
        if not file_path or not os.path.isfile(file_path):
            self.showMessage(self.tr("Invalid firmware"), self.tr("Please select a valid firmware file first."), "warning")
            return

        if self._selected_target() is None:
            self.showMessage(self.tr("Missing target"), self.tr("Please select the target from the local pack first."), "warning")
            return

        base_address = self.baseAddressInput.text().strip()
        if base_address:
            try:
                int(base_address, 0)
            except ValueError:
                self.showMessage(self.tr("Invalid address"), self.tr("The bin start address must be a decimal or hexadecimal number."), "warning")
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
        for widget in [
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
        ]:
            widget.setEnabled(enabled)

    def _apply_probe_items(self, probes: list[daplink_pyocd.DaplinkProbeInfo]):
        self.probeCombo.clear()
        self._probe_items = probes

        if not probes:
            self.probeCombo.addItem(self.tr("No DAPLink / CMSIS-DAP found"))
            self.stateLabel.setText(self.tr("No debugger found"))
            self.stateLabel.setStyleSheet("font-weight: bold; color: #C42B1C;")
            self.summaryLabel.setText(self.tr("DAPLink / CMSIS-DAP was not found. Check the USB connection, driver, and firmware."))
            self.summaryLabel.setStyleSheet("color: #C42B1C;")
            return

        for item in probes:
            self.probeCombo.addItem(f"#{item.index} | {item.description} | UID {item.uid}")

        self.probeCombo.setCurrentIndex(0)
        self.stateLabel.setText(self.tr("Detected {count} debugger(s)").format(count=len(probes)))
        self.stateLabel.setStyleSheet("font-weight: bold; color: #0F7B0F;")
        self.summaryLabel.setText(self.tr("Debugger scan finished. You can connect and read target information now."))
        self.summaryLabel.setStyleSheet("color: #0F7B0F;")

    def _apply_target_items(self, targets: list[daplink_pyocd.DaplinkTargetInfo], pack_paths: list[str]):
        self._all_target_items = targets
        self._target_items = []

        if not targets:
            self.targetCombo.clear()
            self.targetCombo.addItem(self.tr("No local pack targets found"))
            self.packSummaryLabel.setText(self.tr("No .pack file was found in Resources/Tools/Pack."))
            self.packSummaryLabel.setStyleSheet("color: #C42B1C;")
            self.targetSummaryLabel.setText(self.tr("Please put a CMSIS Device Family Pack into the directory first."))
            self.targetSummaryLabel.setStyleSheet("color: #C42B1C;")
            return

        pack_names = sorted({Path(path).name for path in pack_paths})
        self.packSummaryLabel.setText(
            self.tr("Loaded {count} pack(s): {packs}").format(count=len(pack_names), packs=", ".join(pack_names))
        )
        self.packSummaryLabel.setStyleSheet("color: #0F7B0F;")
        self._apply_target_filter(self.targetFilterInput.text())

    def _apply_target_filter(self, text: str = ""):
        keyword = (text or "").strip().lower()
        current = self._selected_target()
        current_target_name = current.target_name if current else ""

        if keyword:
            filtered = [
                item
                for item in self._all_target_items
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
            self.targetCombo.addItem(self.tr("No matching target"))
            self.targetCombo.blockSignals(False)
            self.targetSummaryLabel.setText(
                self.tr("No target matches the current filter. Try STM32G474, G474, RETx, and similar keywords.")
            )
            self.targetSummaryLabel.setStyleSheet("color: #C42B1C;")
            return

        for item in filtered:
            self.targetCombo.addItem(f"{item.part_number} | {item.flash_size} Flash | {item.ram_size} RAM")

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
                self.targetSummaryLabel.setText(
                    self.tr("Please select a local pack target. If your chip is STM32G474, you can filter with STM32G474 directly.")
                )
                self.targetSummaryLabel.setStyleSheet("color: #777777;")
            return

        self.targetSummaryLabel.setText(
            self.tr("Current target: {part} | pyOCD ID: {target} | Flash: {flash_start} ({flash_size}) | Pack: {pack_name} {pack_version}").format(
                part=target.part_number,
                target=target.target_name,
                flash_start=target.flash_start,
                flash_size=target.flash_size,
                pack_name=target.pack_name,
                pack_version=target.pack_version,
            )
        )
        self.targetSummaryLabel.setStyleSheet("color: #777777;")
        if not self.baseAddressInput.text().strip() and target.flash_start != "--":
            self.baseAddressInput.setText(target.flash_start)

    def _apply_device_info(self, info: daplink_pyocd.DaplinkDeviceInfo | None):
        self._device_info = info
        if info is None:
            self._clear_info_labels()
            self.summaryLabel.setText(self.tr("Wait for DAPLink to connect to the target chip..."))
            self.summaryLabel.setStyleSheet("color: #C42B1C;")
            return

        for key, label in self.infoLabels.items():
            label.setText(getattr(info, key, "--") or "--")

        self.stateLabel.setText(self.tr("Connected"))
        self.stateLabel.setStyleSheet("font-weight: bold; color: #0F7B0F;")
        self.summaryLabel.setText(
            self.tr("Probe: {probe} | Device: {part} | Flash: {flash} | Pack: {pack_name} {pack_version}").format(
                probe=info.probe_description,
                part=info.part_number,
                flash=info.flash_size,
                pack_name=info.pack_name,
                pack_version=info.pack_version,
            )
        )
        self.summaryLabel.setStyleSheet("color: #0F7B0F; font-weight: bold;")

    def _apply_progress(self, percent: float):
        value = max(0, min(100, int(round(percent))))
        self.progressBar.setValue(value)
        self.progressLabel.setText(self.tr("Download progress: {value}%").format(value=value))

    def _handle_action_finished(self, payload: daplink_pyocd.ActionFinishedPayload):
        if payload.success:
            if payload.action == "connect":
                self.showMessage(self.tr("Connect success"), self.tr("DAPLink and target information have been read."), "success")
            elif payload.action == "download":
                self.showMessage(self.tr("Download success"), self.tr("Firmware has been written to the target with pyOCD."), "success")
            return

        if payload.action == "download":
            self.progressBar.setValue(0)
            self._apply_progress(0)

        self.stateLabel.setText(self.tr("Action failed"))
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
        self.summaryLabel.setText(self.tr("Waiting to connect DAPLink and target chip..."))
        self.summaryLabel.setStyleSheet("color: #777777;")
        self.stateLabel.setText(self.tr("Not connected"))
        self.stateLabel.setStyleSheet("font-weight: bold; color: #C42B1C;")
        self.progressBar.setValue(0)
        self._apply_progress(0)
        self.packSummaryLabel.setText(self.tr("Waiting for local pack data to load..."))
        self.packSummaryLabel.setStyleSheet("color: #777777;")
        self.targetSummaryLabel.setText(self.tr("Showing filtered targets from Resources/Tools/Pack."))
        self.targetSummaryLabel.setStyleSheet("color: #777777;")
