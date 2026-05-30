# -*- coding: utf-8 -*-
from PyQt5.QtCore import QSize, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QImage
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    HeaderCardWidget,
    HorizontalFlipView,
    HyperlinkLabel,
    ImageLabel,
    PillPushButton,
    PrimaryPushButton,
    SimpleCardWidget,
    TransparentToolButton,
    VerticalSeparator,
    setFont, ScrollArea,
)

from config import CTX, AppIconPath
from app.manager import (
    FirmwareCheckFinishedEvent,
    FirmwareDownloadFinishedEvent,
    StyleSheet,
    UpdateCheckFinishedEvent,
    firmware_check_manager,
    firmware_download_manager,
    update_manager,
)
from app.core.utility import showMessage

FIRMWARE_KIND_TEXT = {
    "Power": "电源",
    "Upper": "上位机",
}

FIRMWARE_CARD_TEXT = {
    "Power firmware": "电源固件",
    "Power Upper firmware": "电源上位机固件",
    "Embedded power controller firmware for output control, protection, and telemetry acquisition.": "用于输出控制、保护策略和遥测采集的电源控制器嵌入式固件。",
    "Desktop Upper firmware that provides power dashboard, parameter configuration, and devices operations.": "提供电源仪表盘、参数配置和设备操作能力的上位机固件。",
}

UPDATE_MESSAGE_TEXT = {
    "Update URL is not configured.": "未配置更新地址。",
    "Failed to connect to the update server.": "连接更新服务器失败。",
    "The update server returned invalid version data.": "更新服务器返回的版本数据无效。",
    "app update URL is not configured.": "未配置软件更新地址。",
    "Failed to check updates.": "检查更新失败。",
    "Failed to check firmware updates.": "检查固件更新失败。",
    "Failed to download firmware.": "下载固件失败。",
}


class StatisticsWidget(QWidget):
    def __init__(self, title: str, value: str, parent=None):
        super().__init__(parent=parent)
        self.titleLabel = CaptionLabel(title, self)
        self.valueLabel = BodyLabel(value, self)
        self.vBoxLayout = QVBoxLayout(self)

        margin = 16
        self.vBoxLayout.setContentsMargins(margin, 0, margin, 0)
        self.vBoxLayout.addWidget(self.valueLabel, 0, Qt.AlignTop | Qt.AlignHCenter)
        self.vBoxLayout.addWidget(self.titleLabel, 0, Qt.AlignBottom | Qt.AlignHCenter)

        setFont(self.valueLabel, 18, QFont.DemiBold)
        self.titleLabel.setTextColor(QColor(96, 96, 96), QColor(206, 206, 206))

    def setTitle(self, title: str) -> None:
        self.titleLabel.setText(title)


class AppInfoCard(SimpleCardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.iconLabel = ImageLabel(QImage(AppIconPath), self)
        self.iconLabel.setBorderRadius(8, 8, 8, 8)
        self.iconLabel.scaledToWidth(120)

        self.nameLabel = BodyLabel("Fluor4CellPower", self)
        setFont(self.nameLabel, 16, QFont.DemiBold)

        self.installButton = PrimaryPushButton(self)
        self.companyLabel = HyperlinkLabel(
            QUrl("https://github.com/UF4OVER"), "UF4OVER", self
        )
        self.installButton.setFixedWidth(160)

        self.scoreWidget = StatisticsWidget("", "5.0", self)
        self.separator = VerticalSeparator(self)
        self.commentWidget = StatisticsWidget("", "3K", self)

        self.descriptionLabel = BodyLabel(self)
        self.descriptionLabel.setWordWrap(True)

        self.tagButton = PillPushButton(self)
        self.tagButton.setCheckable(False)
        setFont(self.tagButton, 12)
        self.tagButton.setFixedSize(80, 32)

        self.shareButton = TransparentToolButton(FluentIcon.SHARE, self)
        self.shareButton.setFixedSize(32, 32)
        self.shareButton.setIconSize(QSize(15, 15))

        self.hBoxLayout = QHBoxLayout(self)
        self.vBoxLayout = QVBoxLayout()
        self.topLayout = QHBoxLayout()
        self.statisticsLayout = QHBoxLayout()
        self.buttonLayout = QHBoxLayout()

        self.initLayout()
        self.applyTexts()

    def initLayout(self):
        self.hBoxLayout.setSpacing(30)
        self.hBoxLayout.setContentsMargins(34, 24, 24, 24)
        self.hBoxLayout.addWidget(self.iconLabel)
        self.hBoxLayout.addLayout(self.vBoxLayout)

        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(0)

        self.vBoxLayout.addLayout(self.topLayout)
        self.topLayout.setContentsMargins(0, 0, 0, 0)
        self.topLayout.addWidget(self.nameLabel)
        self.topLayout.addWidget(self.installButton, 0, Qt.AlignRight)

        self.vBoxLayout.addSpacing(3)
        self.vBoxLayout.addWidget(self.companyLabel)
        self.vBoxLayout.addSpacing(20)
        self.vBoxLayout.addLayout(self.statisticsLayout)
        self.statisticsLayout.setContentsMargins(0, 0, 0, 0)
        self.statisticsLayout.setSpacing(10)
        self.statisticsLayout.addWidget(self.scoreWidget)
        self.statisticsLayout.addWidget(self.separator)
        self.statisticsLayout.addWidget(self.commentWidget)
        self.statisticsLayout.setAlignment(Qt.AlignLeft)

        self.vBoxLayout.addSpacing(20)
        self.vBoxLayout.addWidget(self.descriptionLabel)

        self.vBoxLayout.addSpacing(12)
        self.buttonLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.addLayout(self.buttonLayout)
        self.buttonLayout.addWidget(self.tagButton, 0, Qt.AlignLeft)
        self.buttonLayout.addWidget(self.shareButton, 0, Qt.AlignRight)

    def applyTexts(self):
        if not self.installButton.isEnabled():
            self.installButton.setText('检查中...')
        else:
            self.installButton.setText('检查更新')
        self.scoreWidget.setTitle('评分')
        self.commentWidget.setTitle('评论数')
        self.descriptionLabel.setText(
            "Fluor4CellPower 是一个多功能上位机工具，提供串口通信、数据可视化和设备管理能力，用于电子设备调试和监控。"
        )
        self.tagButton.setText('功能板')

    def setCheckInProgress(self, checking: bool) -> None:
        self.installButton.setEnabled(not checking)
        self.applyTexts()


class GalleryCard(HeaderCardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.flipView = HorizontalFlipView(self)
        self.expandButton = TransparentToolButton(FluentIcon.CHEVRON_RIGHT_MED, self)

        self.expandButton.setFixedSize(32, 32)
        self.expandButton.setIconSize(QSize(12, 12))

        imgPath = CTX.dirs.AssetsDir / "F4CP_2x1_1200x600.png"
        self.flipView.addImages([QImage(str(imgPath))])
        self.flipView.setBorderRadius(8)
        self.flipView.setSpacing(10)

        itemSize = QSize(620, 351)
        self.flipView.setItemSize(itemSize)
        self.flipView.setMinimumSize(itemSize)

        self.headerLayout.addWidget(self.expandButton, 0, Qt.AlignRight)
        self.viewLayout.addWidget(self.flipView)
        self.applyTexts()

    def applyTexts(self):
        self.setTitle('截图')


class FirmwareInfoCard(SimpleCardWidget):
    def __init__(
        self,
        title: str,
        localVersion: str,
        latestVersion: str,
        description: str,
        parent=None,
    ):
        super().__init__(parent)
        self._title = title
        self._description = description

        self.titleLabel = BodyLabel(self)
        self.versionLayout = QHBoxLayout()
        self.localVersionLayout = QVBoxLayout()
        self.latestVersionLayout = QVBoxLayout()
        self.localVersionCaptionLabel = CaptionLabel(self)
        self.localVersionLabel = BodyLabel(localVersion, self)
        self.latestVersionCaptionLabel = CaptionLabel(self)
        self.latestVersionLabel = BodyLabel(latestVersion, self)
        self.descriptionLabel = CaptionLabel(self)
        self.downloadButton = PrimaryPushButton(self)
        self.vBoxLayout = QVBoxLayout(self)

        self.setObjectName("FirmwareInfoCard")
        self.descriptionLabel.setWordWrap(True)
        self.descriptionLabel.setTextColor(QColor(96, 96, 96), QColor(206, 206, 206))
        self.downloadButton.setEnabled(False)

        setFont(self.titleLabel, 15, QFont.DemiBold)
        setFont(self.localVersionLabel, 18, QFont.DemiBold)
        setFont(self.latestVersionLabel, 18, QFont.DemiBold)

        self.initLayout()
        self.applyTexts()

    def initLayout(self):
        self.setMinimumHeight(180)
        self.vBoxLayout.setContentsMargins(20, 18, 20, 18)
        self.vBoxLayout.setSpacing(8)
        self.vBoxLayout.addWidget(self.titleLabel)
        self.vBoxLayout.addSpacing(4)
        self.versionLayout.setContentsMargins(0, 0, 0, 0)
        self.versionLayout.setSpacing(24)
        self.localVersionLayout.setContentsMargins(0, 0, 0, 0)
        self.localVersionLayout.setSpacing(4)
        self.latestVersionLayout.setContentsMargins(0, 0, 0, 0)
        self.latestVersionLayout.setSpacing(4)
        self.localVersionLayout.addWidget(self.localVersionCaptionLabel)
        self.localVersionLayout.addWidget(self.localVersionLabel)
        self.latestVersionLayout.addWidget(self.latestVersionCaptionLabel)
        self.latestVersionLayout.addWidget(self.latestVersionLabel)
        self.versionLayout.addLayout(self.localVersionLayout, 1)
        self.versionLayout.addLayout(self.latestVersionLayout, 1)
        self.vBoxLayout.addLayout(self.versionLayout)
        self.vBoxLayout.addSpacing(4)
        self.vBoxLayout.addWidget(self.descriptionLabel)
        self.vBoxLayout.addSpacing(8)
        self.vBoxLayout.addWidget(self.downloadButton, 0, Qt.AlignRight)
        self.vBoxLayout.addStretch(1)

    def setVersions(self, localVersion: str, latestVersion: str):
        self.localVersionLabel.setText(localVersion or "--")
        self.latestVersionLabel.setText(latestVersion or "--")

    def applyTexts(self):
        self.titleLabel.setText(FIRMWARE_CARD_TEXT.get(self._title, self._title))
        self.localVersionCaptionLabel.setText('本地版本')
        self.latestVersionCaptionLabel.setText('最新版本')
        self.descriptionLabel.setText(FIRMWARE_CARD_TEXT.get(self._description, self._description))
        self.downloadButton.setText('下载固件更新')

    def setDownloadInProgress(self, downloading: bool) -> None:
        self.downloadButton.setEnabled(not downloading)
        self.downloadButton.setText(
            '下载中...' if downloading else '下载固件更新'
        )

    def setUpdateAvailable(self, available: bool) -> None:
        self.downloadButton.setEnabled(available)


class FirmwareUpdateCard(HeaderCardWidget):
    firmwareCheckRequested = pyqtSignal()
    powerFirmwareDownloadRequested = pyqtSignal()
    upperFirmwareDownloadRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.powerFirmwareCard = FirmwareInfoCard(
            "Power firmware",
            "--",
            "--",
            "Embedded power controller firmware for output control, protection, and telemetry acquisition.",
            self,
        )
        self.powerUpperCard = FirmwareInfoCard(
            "Power Upper firmware",
            "--",
            "--",
            "Desktop Upper firmware that provides power dashboard, parameter configuration, and devices operations.",
            self,
        )
        self.cardLayout = QHBoxLayout()
        self.checkFirmwareButton = PrimaryPushButton(self)

        self.initLayout()
        self.applyTexts()
        self.checkFirmwareButton.clicked.connect(self.firmwareCheckRequested)
        self.powerFirmwareCard.downloadButton.clicked.connect(self.powerFirmwareDownloadRequested)
        self.powerUpperCard.downloadButton.clicked.connect(self.upperFirmwareDownloadRequested)

    def initLayout(self):
        self.cardLayout.setContentsMargins(0, 0, 0, 0)
        self.cardLayout.setSpacing(12)
        self.cardLayout.addWidget(self.powerFirmwareCard)
        self.cardLayout.addWidget(self.powerUpperCard)
        self.headerLayout.addWidget(self.checkFirmwareButton, 0, Qt.AlignRight)
        self.viewLayout.addLayout(self.cardLayout)

    def applyTexts(self):
        self.setTitle('固件更新')
        self.checkFirmwareButton.setText('检查固件更新')
        self.powerFirmwareCard.applyTexts()
        self.powerUpperCard.applyTexts()

    def setVersions(
        self,
        *,
        powerLocalVersion: str,
        powerLatestVersion: str,
        upperLocalVersion: str,
        upperLatestVersion: str,
    ) -> None:
        self.powerFirmwareCard.setVersions(powerLocalVersion, powerLatestVersion)
        self.powerUpperCard.setVersions(upperLocalVersion, upperLatestVersion)

    def setFirmwareDownloadInProgress(self, kind: str, downloading: bool) -> None:
        if kind == "Power":
            self.powerFirmwareCard.setDownloadInProgress(downloading)
        elif kind == "Upper":
            self.powerUpperCard.setDownloadInProgress(downloading)

    def setFirmwareUpdateAvailable(self, kind: str, available: bool) -> None:
        if kind == "Power":
            self.powerFirmwareCard.setUpdateAvailable(available)
        elif kind == "Upper":
            self.powerUpperCard.setUpdateAvailable(available)

    def setFirmwareCheckInProgress(self, checking: bool) -> None:
        self.checkFirmwareButton.setEnabled(not checking)
        self.checkFirmwareButton.setText(
            '检查中...' if checking else '检查固件更新'
        )


class HomePage(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._isCheckingUpdate = False
        self._isCheckingFirmware = False
        self._firmwareUpdateAvailable = {"Power": False, "Upper": False}
        self._downloadingFirmwareKinds: set[str] = set()
        self.setObjectName("HomePage")

        self.scrollWidget = QWidget(self)
        self.scrollWidget.setObjectName("homeScrollWidget")

        self.vBoxLayout = QVBoxLayout(self.scrollWidget)
        self.vBoxLayout.setContentsMargins(0, 0, 15, 0)
        self.vBoxLayout.setSpacing(10)

        self.appCard = AppInfoCard(self.scrollWidget)
        self.firmwareUpdateCard = FirmwareUpdateCard(self.scrollWidget)
        self.galleryCard = GalleryCard(self.scrollWidget)

        self.vBoxLayout.addWidget(self.appCard, 0, Qt.AlignTop)
        self.vBoxLayout.addWidget(self.firmwareUpdateCard, 0, Qt.AlignTop)
        self.vBoxLayout.addWidget(self.galleryCard, 0, Qt.AlignTop)
        self.vBoxLayout.addStretch(1)

        self.appCard.installButton.clicked.connect(lambda: self.requestUpdateCheck(manual=True))
        self.firmwareUpdateCard.firmwareCheckRequested.connect(self.requestFirmwareCheck)
        self.firmwareUpdateCard.powerFirmwareDownloadRequested.connect(
            lambda: self.requestFirmwareDownload("Power")
        )
        self.firmwareUpdateCard.upperFirmwareDownloadRequested.connect(
            lambda: self.requestFirmwareDownload("Upper")
        )

        self._applyVersionSnapshot(update_manager.get_cached_versions())

        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        StyleSheet.HOME_PAGE.apply(self)

    def _onThemeChanged(self, *_):
        StyleSheet.HOME_PAGE.apply(self)

    def event(self, event):
        if event.type() == UpdateCheckFinishedEvent.EVENT_TYPE:
            self._isCheckingUpdate = False
            self.appCard.setCheckInProgress(False)
            self._applyVersionSnapshot(event.result.snapshot)
            self._handleUpdateResult(event.result)
            return True

        if event.type() == FirmwareCheckFinishedEvent.EVENT_TYPE:
            self._isCheckingFirmware = False
            self.firmwareUpdateCard.setFirmwareCheckInProgress(False)
            self._applyVersionSnapshot(update_manager.get_cached_versions())
            self._handleFirmwareCheckResult(event.result)
            return True

        if event.type() == FirmwareDownloadFinishedEvent.EVENT_TYPE:
            kind = event.result.kind
            self._downloadingFirmwareKinds.discard(kind)
            self._firmwareUpdateAvailable[kind] = False
            self.firmwareUpdateCard.setFirmwareDownloadInProgress(kind, False)
            self.firmwareUpdateCard.setFirmwareUpdateAvailable(kind, False)
            self._applyVersionSnapshot(update_manager.get_cached_versions())
            self._handleFirmwareDownloadResult(event.result)
            return True

        return super().event(event)

    def requestUpdateCheck(self, manual: bool = False) -> None:
        if self._isCheckingUpdate or update_manager.is_checking:
            if manual:
                showMessage(
                    self,
                    '检查中...',
                    '已有软件更新检查正在进行中。',
                    "warning",
                    True,
                    3000
                )
            return

        self._isCheckingUpdate = True
        self.appCard.setCheckInProgress(True)
        started = update_manager.check_for_updates(self, manual=manual)
        if not started:
            self._isCheckingUpdate = False
            self.appCard.setCheckInProgress(False)

    def requestFirmwareCheck(self) -> None:
        if self._isCheckingFirmware or firmware_check_manager.is_checking:
            showMessage(
                self,
                '检查中...',
                '已有固件更新检查正在进行中。',
                "warning",
                True,
                3000

            )
            return

        self._isCheckingFirmware = True
        self.firmwareUpdateCard.setFirmwareCheckInProgress(True)
        started = firmware_check_manager.check_updates(self)
        if not started:
            self._isCheckingFirmware = False
            self.firmwareUpdateCard.setFirmwareCheckInProgress(False)

    def requestFirmwareDownload(self, kind: str) -> None:
        if not self._firmwareUpdateAvailable.get(kind, False):
            showMessage(
                self,
                '无固件更新',
                '请先检查固件更新。没有可用更新时会跳过下载。',
                "info",
                True,
                3000
            )
            return

        if firmware_download_manager.is_downloading(kind):
            showMessage(
                self,
                '下载中...',
                '已有固件下载正在进行中。',
                "warning",
                True,
                3000
            )
            return

        started = firmware_download_manager.download_latest(kind, self)
        if not started:
            return

        self._downloadingFirmwareKinds.add(kind)
        self.firmwareUpdateCard.setFirmwareDownloadInProgress(kind, True)

    def _applyVersionSnapshot(self, snapshot) -> None:
        self.firmwareUpdateCard.setVersions(
            powerLocalVersion=snapshot.local_lower_version,
            powerLatestVersion=snapshot.latest_lower_version,
            upperLocalVersion=snapshot.local_upper_version,
            upperLatestVersion=snapshot.latest_upper_version,
        )

    def _handleUpdateResult(self, result) -> None:
        if not result.manual:
            return

        if result.success:
            showMessage(
                self,
                '更新检查完成',
                '最新软件版本已刷新。',
                "success",
            )
            return

        showMessage(
            self,
            '更新检查失败',
            UPDATE_MESSAGE_TEXT.get(result.message, result.message),
            "warning",
        )

    def _handleFirmwareDownloadResult(self, result) -> None:
        if result.success and result.release is not None:
            showMessage(
                self,
                '固件下载完成',
                '{kind}固件已下载：{version}'.format(
                    kind=FIRMWARE_KIND_TEXT.get(result.kind, result.kind),
                    version=result.release.version,
                ),
                "success",
            )
            return

        showMessage(
            self,
            '固件下载失败',
            UPDATE_MESSAGE_TEXT.get(result.message, result.message),
            "warning",
        )

    def _handleFirmwareCheckResult(self, result) -> None:
        if not result.success:
            showMessage(
                self,
                '更新检查失败',
                UPDATE_MESSAGE_TEXT.get(result.message, result.message),
                "warning",
            )
            return

        self._firmwareUpdateAvailable = {
            "Power": bool(result.has_updates.get("Power", False)),
            "Upper": bool(result.has_updates.get("Upper", False)),
        }
        for kind, available in self._firmwareUpdateAvailable.items():
            self.firmwareUpdateCard.setFirmwareUpdateAvailable(kind, available)

        if any(self._firmwareUpdateAvailable.values()):
            showMessage(
                self,
                '发现固件更新',
                '发现新固件，请在固件卡片中手动下载。',
                "success",
            )
            return

        showMessage(
            self,
            '无固件更新',
            '本地固件已是最新版本。',
            "info",
        )

