# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path

from PyQt5.QtCore import QCoreApplication, QTimer
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
from App.Core.Manager import firmware_manager
from App.Core.utility import showMessage
from App.Core.Session import session_daplink as daplink_pyocd


class DaplinkFlashPage(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("DaplinkFlashPage")

        self._probeItems: list[daplink_pyocd.DaplinkProbeInfo] = []
        self._allTargetItems: list[daplink_pyocd.DaplinkTargetInfo] = []
        self._targetItems: list[daplink_pyocd.DaplinkTargetInfo] = []
        self._internalFirmwareItems: list[Path] = []
        self._deviceInfo: daplink_pyocd.DaplinkDeviceInfo | None = None
        self._powerPageSuspended = False

        self.view = QWidget(self)
        self.view.setObjectName("daplinkScrollWidget")
        self.vBoxLayout = QVBoxLayout(self.view)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.vBoxLayout.setSpacing(12)

        self.titleLabel = TitleLabel(self.view)
        self.vBoxLayout.addWidget(self.titleLabel)

        self._initConnectionCard()
        self._initInfoCard()
        self._initDownloadCard()
        self._initLogCard()

        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self._session = daplink_pyocd.DaplinkPyocdSession(
            _event_receiver=self, parent=self
        )
        self._resetDeviceInfo()
        self._applyTexts()

        QTimer.singleShot(0, self.reloadPackTargets)
        QTimer.singleShot(0, self.scanProbe)

    def event(self, e):
        eventType = e.type()

        if eventType == int(daplink_pyocd.DaplinkProgrammerEventType.LOG):
            self.log(e.payload.text, self._logColorForLevel(e.payload.level))
            return True
        if eventType == int(daplink_pyocd.DaplinkProgrammerEventType.MESSAGE):
            self.showMessage(e.payload.title, e.payload.content, e.payload.level)
            return True
        if eventType == int(daplink_pyocd.DaplinkProgrammerEventType.STATE):
            self.setButtonsEnabled(not e.payload.busy)
            return True
        if eventType == int(daplink_pyocd.DaplinkProgrammerEventType.PROBES):
            self._applyProbeItems(e.payload.probes)
            return True
        if eventType == int(daplink_pyocd.DaplinkProgrammerEventType.TARGETS):
            self._applyTargetItems(e.payload.targets, e.payload.pack_paths)
            return True
        if eventType == int(daplink_pyocd.DaplinkProgrammerEventType.DEVICE_INFO):
            self._applyDeviceInfo(e.payload.info)
            return True
        if eventType == int(daplink_pyocd.DaplinkProgrammerEventType.PROGRESS):
            self._applyProgress(e.payload.percent)
            return True
        if eventType == int(daplink_pyocd.DaplinkProgrammerEventType.ACTION_FINISHED):
            self._restorePowerPageAfterDaplink()
            self._handleActionFinished(e.payload)
            return True

        return super().event(e)

    def closeEvent(self, event):
        self._session.shutdown()
        super().closeEvent(event)

    def _initConnectionCard(self):
        self.connectCard = CardWidget(self.view)
        layout = QVBoxLayout(self.connectCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.connectionCardTitle = SubtitleLabel(self.connectCard)
        layout.addWidget(self.connectionCardTitle)

        probeRow = QHBoxLayout()
        self.probeCombo = ComboBox(self.connectCard)
        self.probeCombo.setMinimumWidth(360)
        probeRow.addWidget(self.probeCombo, 1)

        self.scanProbeBtn = PushButton(FIF.SYNC, "", self.connectCard)
        self.scanProbeBtn.clicked.connect(self.scanProbe)
        probeRow.addWidget(self.scanProbeBtn)

        self.connectBtn = PrimaryPushButton(FIF.LINK, "", self.connectCard)
        self.connectBtn.clicked.connect(self.readInfo)
        probeRow.addWidget(self.connectBtn)
        layout.addLayout(probeRow)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        self.targetLabel = BodyLabel(self.connectCard)
        grid.addWidget(self.targetLabel, 0, 0)
        self.targetCombo = ComboBox(self.connectCard)
        self.targetCombo.setMinimumWidth(360)
        self.targetCombo.currentIndexChanged.connect(self._onTargetChanged)
        grid.addWidget(self.targetCombo, 0, 1)

        self.reloadPackBtn = PushButton(FIF.ROTATE, "", self.connectCard)
        self.reloadPackBtn.clicked.connect(self.reloadPackTargets)
        grid.addWidget(self.reloadPackBtn, 0, 2)

        self.targetFilterLabel = BodyLabel(self.connectCard)
        grid.addWidget(self.targetFilterLabel, 1, 0)
        self.targetFilterInput = LineEdit(self.connectCard)
        self.targetFilterInput.setText("G474RBT")
        self.targetFilterInput.textChanged.connect(self._applyTargetFilter)
        grid.addWidget(self.targetFilterInput, 1, 1)

        self.frequencyLabel = BodyLabel(self.connectCard)
        grid.addWidget(self.frequencyLabel, 2, 0)
        self.frequencyInput = LineEdit(self.connectCard)
        self.frequencyInput.setText("100000")
        grid.addWidget(self.frequencyInput, 2, 1)

        self.connectModeLabel = BodyLabel(self.connectCard)
        grid.addWidget(self.connectModeLabel, 2, 2)
        self.connectModeCombo = ComboBox(self.connectCard)
        self.connectModeCombo.addItems(["halt", "under-reset", "pre-reset", "attach"])
        self.connectModeCombo.setCurrentText("under-reset")
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

    def _initInfoCard(self):
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
            ("target_name", "Target"),
            ("part_number", "Part Number"),
            ("family", "Family"),
            ("flash_start", "Flash Start"),
            ("flash_size", "Flash Size"),
            ("ram_size", "RAM Size"),
            ("pack_name", "Pack Name"),
            ("pack_version", "Pack Version"),
        ]

        for index, (key, titleText) in enumerate(fields):
            row = index // 2
            column = (index % 2) * 2
            titleLabel = BodyLabel(self.infoCard)
            grid.addWidget(titleLabel, row, column)
            valueLabel = BodyLabel("--", self.infoCard)
            valueLabel.setStyleSheet("font-weight: bold;")
            valueLabel.setWordWrap(True)
            grid.addWidget(valueLabel, row, column + 1)
            self.infoTitleLabels[key] = titleLabel
            self.infoLabels[key] = valueLabel
            titleLabel.setProperty("sourceText", titleText)

        layout.addLayout(grid)

        self.summaryLabel = BodyLabel(self.infoCard)
        self.summaryLabel.setWordWrap(True)
        self.summaryLabel.setStyleSheet("color: #777777;")
        layout.addWidget(self.summaryLabel)
        self.vBoxLayout.addWidget(self.infoCard)

    def _initDownloadCard(self):
        self.downloadCard = CardWidget(self.view)
        layout = QVBoxLayout(self.downloadCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.downloadCardTitle = SubtitleLabel(self.downloadCard)
        layout.addWidget(self.downloadCardTitle)

        sourceRow = QHBoxLayout()
        self.firmwareSourceLabel = BodyLabel(self.downloadCard)
        sourceRow.addWidget(self.firmwareSourceLabel)
        self.firmwareSourceCombo = ComboBox(self.downloadCard)
        self.firmwareSourceCombo.currentIndexChanged.connect(self._onFirmwareSourceChanged)
        sourceRow.addWidget(self.firmwareSourceCombo, 1)
        layout.addLayout(sourceRow)

        internalRow = QHBoxLayout()
        self.internalFirmwareCombo = ComboBox(self.downloadCard)
        self.internalFirmwareCombo.currentIndexChanged.connect(self._onInternalFirmwareChanged)
        internalRow.addWidget(self.internalFirmwareCombo, 1)

        self.refreshFirmwareButton = PushButton(FIF.SYNC, "", self.downloadCard)
        self.refreshFirmwareButton.clicked.connect(self._reloadInternalFirmwareOptions)
        internalRow.addWidget(self.refreshFirmwareButton)
        layout.addLayout(internalRow)

        self.externalFileRowWidget = QWidget(self.downloadCard)
        fileRow = QHBoxLayout(self.externalFileRowWidget)
        fileRow.setContentsMargins(0, 0, 0, 0)
        self.filePathInput = LineEdit(self.downloadCard)
        fileRow.addWidget(self.filePathInput, 1)

        self.browseButton = PushButton(FIF.FOLDER, "", self.downloadCard)
        self.browseButton.clicked.connect(self.browseFile)
        fileRow.addWidget(self.browseButton)
        layout.addWidget(self.externalFileRowWidget)

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

    def _initLogCard(self):
        self.logCard = CardWidget(self.view)
        layout = QVBoxLayout(self.logCard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        titleRow = QHBoxLayout()
        self.logCardTitle = SubtitleLabel(self.logCard)
        titleRow.addWidget(self.logCardTitle)
        titleRow.addStretch(1)

        self.clearLogButton = PushButton(FIF.BROOM, "", self.logCard)
        self.clearLogButton.clicked.connect(self.clearLog)
        titleRow.addWidget(self.clearLogButton)

        self.saveLogButton = PushButton(FIF.SAVE, "", self.logCard)
        self.saveLogButton.clicked.connect(self.saveLog)
        titleRow.addWidget(self.saveLogButton)
        layout.addLayout(titleRow)

        self.logEdit = TextEdit(self.logCard)
        self.logEdit.setReadOnly(True)
        self.logEdit.setMinimumHeight(260)
        layout.addWidget(self.logEdit)
        self.vBoxLayout.addWidget(self.logCard, 1)

    def _applyTexts(self):
        self.titleLabel.setText(self.tr("DAPLink Download"))
        self.connectionCardTitle.setText(self.tr("DAPLink connection"))
        self.probeCombo.setPlaceholderText(self.tr("Scan and select DAPLink"))
        self.scanProbeBtn.setText(self.tr("Scan DAPLink"))
        self.connectBtn.setText(self.tr("Connect"))

        self.targetLabel.setText(self.tr("Local pack target"))
        self.targetCombo.setPlaceholderText(
            self.tr("Load targets from Resources/Tools/Pack")
        )
        self.reloadPackBtn.setText(self.tr("Reload pack"))
        self.targetFilterLabel.setText(self.tr("Target filter"))
        self.targetFilterInput.setPlaceholderText(
            self.tr("Enter STM32G474 / G474 / RETx or other keywords")
        )
        self.frequencyLabel.setText(self.tr("SWD frequency"))
        self.frequencyInput.setPlaceholderText(
            self.tr("For example 1000000 / 4M / 4000K")
        )
        self.connectModeLabel.setText(self.tr("Connect mode"))
        self.stateTitleLabel.setText(self.tr("State"))
        self.packSourceTitleLabel.setText(self.tr("Pack source"))

        self.infoCardTitle.setText(self.tr("Probe / target info"))
        for key, label in self.infoTitleLabels.items():
            label.setText(self.tr(label.property("sourceText")))

        self.downloadCardTitle.setText(self.tr("Download firmware"))
        self.firmwareSourceLabel.setText(self.tr("Firmware source"))
        self._setFirmwareSourceItems()
        self.internalFirmwareCombo.setPlaceholderText(
            self.tr("Select internal firmware from Resources/Firmware")
        )
        self.refreshFirmwareButton.setText(self.tr("Refresh firmware"))
        self.filePathInput.setPlaceholderText(
            self.tr("Select the firmware file to download (.bin/.hex/.elf)")
        )
        self.browseButton.setText(self.tr("Browse"))
        self.baseAddressLabel.setText(self.tr("Bin start address"))
        self.baseAddressInput.setPlaceholderText(
            self.tr("If empty, use the flash start address from the pack")
        )
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

        self._applyProgress(self.progressBar.value())
        self._reloadInternalFirmwareOptions()
        if self._deviceInfo is None and not self.summaryLabel.text():
            self._resetDeviceInfo()

    def log(self, text: str, color: str | None = None):
        if not text:
            return

        plainText = text.replace("\r\n", "\n").replace("\r", "\n")
        if color in ("red", "#C42B1C"):
            plainText = f"[ERROR] {plainText}"
        elif color == "#0078D4":
            plainText = f"[CMD] {plainText}"

        cursor = self.logEdit.textCursor()
        cursor.movePosition(QTextCursor.End)
        if not self.logEdit.document().isEmpty():
            cursor.insertText("\n")
        cursor.insertText(plainText)
        scrollbar = self.logEdit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        logger.info(f"{self.__class__.__name__}: {text}", extra={"color": color})

    def showMessage(self, title: str, content: str, level: str = "info"):
        showMessage(self, title, content, level)

    def browseFile(self):
        filePath, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select firmware"),
            "",
            self.tr("Firmware Files (*.bin *.hex *.elf *.axf)"),
        )
        if filePath:
            self.filePathInput.setText(filePath)

    def _setFirmwareSourceItems(self):
        currentIndex = self.firmwareSourceCombo.currentIndex()
        if currentIndex < 0:
            currentIndex = 0

        self.firmwareSourceCombo.blockSignals(True)
        self.firmwareSourceCombo.clear()
        self.firmwareSourceCombo.addItem(self.tr("Internal firmware"))
        self.firmwareSourceCombo.addItem(self.tr("External file"))

        self.firmwareSourceCombo.setCurrentIndex(min(currentIndex, self.firmwareSourceCombo.count() - 1))
        self.firmwareSourceCombo.blockSignals(False)
        self._onFirmwareSourceChanged()

    def _reloadInternalFirmwareOptions(self):
        currentPath = self._selectedInternalFirmwarePath()
        firmwareFiles = firmware_manager.GetLowerFirmware() + firmware_manager.GetUpperFirmware()
        self._internalFirmwareItems = sorted(
            firmwareFiles,
            key=lambda item: (item.parent.name, item.name),
            reverse=True,
        )

        self.internalFirmwareCombo.blockSignals(True)
        self.internalFirmwareCombo.clear()
        if not self._internalFirmwareItems:
            self.internalFirmwareCombo.addItem(self.tr("No internal firmware found"))
        else:
            for path in self._internalFirmwareItems:
                self.internalFirmwareCombo.addItem(self._formatInternalFirmwareItem(path))

        if currentPath is not None:
            for index, path in enumerate(self._internalFirmwareItems):
                if path == currentPath:
                    self.internalFirmwareCombo.setCurrentIndex(index)
                    break
        self.internalFirmwareCombo.blockSignals(False)

    def _onFirmwareSourceChanged(self):
        useInternal = self.firmwareSourceCombo.currentIndex() == 0
        self.internalFirmwareCombo.setVisible(useInternal)
        self.refreshFirmwareButton.setVisible(useInternal)
        self.externalFileRowWidget.setVisible(not useInternal)
        if useInternal:
            self._onInternalFirmwareChanged()

    def _selectedInternalFirmwarePath(self) -> Path | None:
        index = self.internalFirmwareCombo.currentIndex()
        if 0 <= index < len(self._internalFirmwareItems):
            return self._internalFirmwareItems[index]
        return None

    def _selectedFirmwarePath(self) -> str:
        if self.firmwareSourceCombo.currentIndex() == 1:
            return self.filePathInput.text().strip()

        internalPath = self._selectedInternalFirmwarePath()
        return str(internalPath) if internalPath is not None else ""

    def _formatInternalFirmwareItem(self, path: Path) -> str:
        try:
            relative = path.relative_to(DirPathsInstance.FirmwareDir)
        except ValueError:
            relative = path
        return str(relative)

    def _onInternalFirmwareChanged(self):
        if self.firmwareSourceCombo.currentIndex() != 0:
            return

        firmwareKind = self._firmwareKindFromPath(self._selectedInternalFirmwarePath())
        if firmwareKind == "Power":
            self.targetFilterInput.setText("STM32G474")
        elif firmwareKind == "Upper":
            self.targetFilterInput.setText("STM32H750")

    @staticmethod
    def _firmwareKindFromPath(path: Path | str | None) -> str | None:
        if path is None:
            return None

        text = str(path).lower()
        if "uf4dp_power" in text or "\\power\\" in text or "/power/" in text:
            return "Power"
        if "uf4dp_upper" in text or "\\upper\\" in text or "/upper/" in text:
            return "Upper"
        return None

    def _validateFirmwareTargetMatch(self, firmwarePath: str) -> bool:
        target = self._selectedTarget()
        if target is None:
            return True

        firmwareKind = self._firmwareKindFromPath(firmwarePath)
        targetText = " ".join(
            [
                target.target_name,
                target.part_number,
                target.family,
                target.pack_name,
            ]
        ).lower()

        if firmwareKind == "Power" and "g474" not in targetText:
            self.showMessage(
                self.tr("Firmware and target mismatch"),
                self.tr("Power firmware must be downloaded to STM32G474."),
                "warning",
            )
            return False

        if firmwareKind == "Upper" and "h750" not in targetText:
            self.showMessage(
                self.tr("Firmware and target mismatch"),
                self.tr("Upper firmware must be downloaded to STM32H750."),
                "warning",
            )
            return False

        return True

    def clearLog(self):
        self.logEdit.clear()
        self.log(self.tr("The log has been cleared."), "#888888")

    def saveLog(self):
        defaultFile = str(Path(DirPathsInstance.LogDir) / "daplink_pyocd_ui.log")
        filePath, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save logs"),
            defaultFile,
            self.tr("Log Files (*.log *.txt)"),
        )
        if not filePath:
            return

        with open(filePath, "w", encoding="utf-8") as f:
            f.write(self.logEdit.toPlainText())

        self.showMessage(
            self.tr("Log saved"),
            self.tr("Saved to {path}").format(path=filePath),
            "success",
        )

    def reloadPackTargets(self):
        self._postRequest(daplink_pyocd.DaplinkRequestPayload(action="load_targets"))

    def scanProbe(self):
        self._postRequest(daplink_pyocd.DaplinkRequestPayload(action="scan_probes"))

    def readInfo(self):
        if self._session.is_busy:
            return
        self._preparePowerPageForDaplink()
        self._postRequest(
            daplink_pyocd.DaplinkRequestPayload(
                action="connect", connect=self._buildConnectConfig()
            )
        )

    def startDownload(self):
        filePath = self._selectedFirmwarePath()
        if not filePath or not os.path.isfile(filePath):
            self.showMessage(
                self.tr("Invalid firmware"),
                self.tr("Please select a valid firmware file first."),
                "warning",
            )
            return

        if self._selectedTarget() is None:
            self.showMessage(
                self.tr("Missing target"),
                self.tr("Please select the target from the local pack first."),
                "warning",
            )
            return

        if not self._validateFirmwareTargetMatch(filePath):
            return

        baseAddress = self.baseAddressInput.text().strip()
        if baseAddress:
            try:
                int(baseAddress, 0)
            except ValueError:
                self.showMessage(
                    self.tr("Invalid address"),
                    self.tr(
                        "The bin start address must be a decimal or hexadecimal number."
                    ),
                    "warning",
                )
                return

        if self._session.is_busy:
            return
        self._preparePowerPageForDaplink()
        self._postRequest(
            daplink_pyocd.DaplinkRequestPayload(
                action="download",
                connect=self._buildConnectConfig(),
                file_path=filePath,
                base_address=baseAddress,
                erase_mode=self.eraseModeCombo.currentText().strip(),
                smart_flash=self.smartFlashSwitch.isChecked(),
                trust_crc=self.trustCrcSwitch.isChecked(),
                reset_after_download=self.resetAfterDownloadSwitch.isChecked(),
            )
        )

    def _preparePowerPageForDaplink(self) -> None:
        if self._powerPageSuspended:
            return

        powerPage = getattr(self.window(), "powerInterface", None)
        if powerPage is not None and hasattr(powerPage, "suspendForDaplink"):
            powerPage.suspendForDaplink()
            self._powerPageSuspended = True

    def _restorePowerPageAfterDaplink(self) -> None:
        if not self._powerPageSuspended:
            return

        powerPage = getattr(self.window(), "powerInterface", None)
        if powerPage is not None and hasattr(powerPage, "resumeAfterDaplink"):
            powerPage.resumeAfterDaplink()
        self._powerPageSuspended = False

    def _buildConnectConfig(self) -> daplink_pyocd.DaplinkConnectConfig:
        probe = self._selectedProbe()
        target = self._selectedTarget()
        return daplink_pyocd.DaplinkConnectConfig(
            probe_uid=probe.uid if probe else None,
            target_name=target.target_name if target else "",
            frequency=self.frequencyInput.text().strip(),
            connect_mode=self.connectModeCombo.currentText().strip(),
        )

    def _selectedProbe(self) -> daplink_pyocd.DaplinkProbeInfo | None:
        index = self.probeCombo.currentIndex()
        if 0 <= index < len(self._probeItems):
            return self._probeItems[index]
        return None

    def _selectedTarget(self) -> daplink_pyocd.DaplinkTargetInfo | None:
        index = self.targetCombo.currentIndex()
        if 0 <= index < len(self._targetItems):
            return self._targetItems[index]
        return None

    def _postRequest(self, payload: daplink_pyocd.DaplinkRequestPayload):
        QCoreApplication.postEvent(
            self._session, daplink_pyocd.DaplinkRequestEvent(payload)
        )

    def setButtonsEnabled(self, enabled: bool):
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
            self.firmwareSourceCombo,
            self.internalFirmwareCombo,
            self.refreshFirmwareButton,
            self.eraseModeCombo,
        ]:
            widget.setEnabled(enabled)

    def _applyProbeItems(self, probes: list[daplink_pyocd.DaplinkProbeInfo]):
        self.probeCombo.clear()
        self._probeItems = probes

        if not probes:
            self.probeCombo.addItem(self.tr("No DAPLink / CMSIS-DAP found"))
            self.stateLabel.setText(self.tr("No debugger found"))
            self.stateLabel.setStyleSheet("font-weight: bold; color: #C42B1C;")
            self.summaryLabel.setText(
                self.tr(
                    "DAPLink / CMSIS-DAP was not found. Check the USB connection, driver, and firmware."
                )
            )
            self.summaryLabel.setStyleSheet("color: #C42B1C;")
            return

        for item in probes:
            self.probeCombo.addItem(
                f"#{item.index} | {item.description} | UID {item.uid}"
            )

        self.probeCombo.setCurrentIndex(0)
        self.stateLabel.setText(
            self.tr("Detected {count} debugger(s)").format(count=len(probes))
        )
        self.stateLabel.setStyleSheet("font-weight: bold; color: #0F7B0F;")
        self.summaryLabel.setText(
            self.tr(
                "Debugger scan finished. You can connect and read target information now."
            )
        )
        self.summaryLabel.setStyleSheet("color: #0F7B0F;")

    def _applyTargetItems(
        self, targets: list[daplink_pyocd.DaplinkTargetInfo], pack_paths: list[str]
    ):
        self._allTargetItems = targets
        self._targetItems = []

        if not targets:
            self.targetCombo.clear()
            self.targetCombo.addItem(self.tr("No local pack targets found"))
            self.packSummaryLabel.setText(
                self.tr("No .pack file was found in Resources/Tools/Pack.")
            )
            self.packSummaryLabel.setStyleSheet("color: #C42B1C;")
            self.targetSummaryLabel.setText(
                self.tr(
                    "Please put a CMSIS Device Family Pack into the directory first."
                )
            )
            self.targetSummaryLabel.setStyleSheet("color: #C42B1C;")
            return

        packNames = sorted({Path(path).name for path in pack_paths})
        self.packSummaryLabel.setText(
            self.tr("Loaded {count} pack(s): {packs}").format(
                count=len(packNames), packs=", ".join(packNames)
            )
        )
        self.packSummaryLabel.setStyleSheet("color: #0F7B0F;")
        self._applyTargetFilter(self.targetFilterInput.text())

    def _applyTargetFilter(self, text: str = ""):
        keyword = (text or "").strip().lower()
        current = self._selectedTarget()
        currentTargetName = current.target_name if current else ""

        if keyword:
            filtered = [
                item
                for item in self._allTargetItems
                if keyword in item.part_number.lower()
                or keyword in item.target_name.lower()
                or keyword in item.family.lower()
            ]
        else:
            filtered = list(self._allTargetItems)

        self.targetCombo.blockSignals(True)
        self.targetCombo.clear()
        self._targetItems = filtered

        if not filtered:
            self.targetCombo.addItem(self.tr("No matching target"))
            self.targetCombo.blockSignals(False)
            self.targetSummaryLabel.setText(
                self.tr(
                    "No target matches the current filter. Try STM32G474, G474, RETx, and similar keywords."
                )
            )
            self.targetSummaryLabel.setStyleSheet("color: #C42B1C;")
            return

        for item in filtered:
            self.targetCombo.addItem(
                f"{item.part_number} | {item.flash_size} Flash | {item.ram_size} RAM"
            )

        selectedIndex = 0
        if currentTargetName:
            for index, item in enumerate(filtered):
                if item.target_name == currentTargetName:
                    selectedIndex = index
                    break

        self.targetCombo.setCurrentIndex(selectedIndex)
        self.targetCombo.blockSignals(False)
        self._onTargetChanged()

    def _onTargetChanged(self):
        target = self._selectedTarget()
        if target is None:
            if self._allTargetItems:
                self.targetSummaryLabel.setText(
                    self.tr(
                        "Please select a local pack target. If your chip is STM32G474, you can filter with STM32G474 directly."
                    )
                )
                self.targetSummaryLabel.setStyleSheet("color: #777777;")
            return

        self.targetSummaryLabel.setText(
            self.tr(
                "Current target: {part} | pyOCD ID: {target} | Flash: {flash_start} ({flash_size}) | Pack: {pack_name} {pack_version}"
            ).format(
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

    def _applyDeviceInfo(self, info: daplink_pyocd.DaplinkDeviceInfo | None):
        self._deviceInfo = info
        if info is None:
            self._clearInfoLabels()
            self.summaryLabel.setText(
                self.tr("Wait for DAPLink to connect to the target chip...")
            )
            self.summaryLabel.setStyleSheet("color: #C42B1C;")
            return

        for key, label in self.infoLabels.items():
            label.setText(getattr(info, key, "--") or "--")

        self.stateLabel.setText(self.tr("Connected"))
        self.stateLabel.setStyleSheet("font-weight: bold; color: #0F7B0F;")
        self.summaryLabel.setText(
            self.tr(
                "Probe: {probe} | Device: {part} | Flash: {flash} | Pack: {pack_name} {pack_version}"
            ).format(
                probe=info.probe_description,
                part=info.part_number,
                flash=info.flash_size,
                pack_name=info.pack_name,
                pack_version=info.pack_version,
            )
        )
        self.summaryLabel.setStyleSheet("color: #0F7B0F; font-weight: bold;")

    def _applyProgress(self, percent: float):
        value = max(0, min(100, int(round(percent))))
        self.progressBar.setValue(value)
        self.progressLabel.setText(
            self.tr("Download progress: {value}%").format(value=value)
        )

    def _handleActionFinished(self, payload: daplink_pyocd.ActionFinishedPayload):
        if payload.success:
            if payload.action == "connect":
                self.showMessage(
                    self.tr("Connect success"),
                    self.tr("DAPLink and target information have been read."),
                    "success",
                )
            elif payload.action == "download":
                self.showMessage(
                    self.tr("Download success"),
                    self.tr("Firmware has been written to the target."),
                    "success",
                )
            return

        if payload.action == "download":
            self.progressBar.setValue(0)
            self._applyProgress(0)

        self.stateLabel.setText(self.tr("Action failed"))
        self.stateLabel.setStyleSheet("font-weight: bold; color: #C42B1C;")

    @staticmethod
    def _logColorForLevel(level: str) -> str | None:
        if level == "error":
            return "#C42B1C"
        if level == "command":
            return "#0078D4"
        return None

    def _clearInfoLabels(self):
        for label in self.infoLabels.values():
            label.setText("--")

    def _resetDeviceInfo(self):
        self._deviceInfo = None
        self._clearInfoLabels()
        self.summaryLabel.setText(
            self.tr("Waiting to connect DAPLink and target chip...")
        )
        self.summaryLabel.setStyleSheet("color: #777777;")
        self.stateLabel.setText(self.tr("Not connected"))
        self.stateLabel.setStyleSheet("font-weight: bold; color: #C42B1C;")
        self.progressBar.setValue(0)
        self._applyProgress(0)
        self.packSummaryLabel.setText(self.tr("Waiting for local pack data to load..."))
        self.packSummaryLabel.setStyleSheet("color: #777777;")
        self.targetSummaryLabel.setText(
            self.tr("Showing filtered targets from Resources/Tools/Pack.")
        )
        self.targetSummaryLabel.setStyleSheet("color: #777777;")
