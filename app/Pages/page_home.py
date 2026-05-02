# -*- coding: utf-8 -*-
from PyQt5.QtCore import QSize, Qt, QUrl
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
    setFont,
)

from Config import AppIconPath, DirPathsInstance, VERSION
from app.Core import StyleSheet


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
        self.installButton.setText(self.tr("Check Update"))
        self.scoreWidget.setTitle(self.tr("Average"))
        self.commentWidget.setTitle(self.tr("Reviews"))
        self.descriptionLabel.setText(
            self.tr(
                "Fluor4CellPower is a multi-function host tool that provides serial communication, "
                "data visualization, and device management for debugging and monitoring electronic devices."
            )
        )
        self.tagButton.setText(self.tr("Dashboard"))


class GalleryCard(HeaderCardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.flipView = HorizontalFlipView(self)
        self.expandButton = TransparentToolButton(FluentIcon.CHEVRON_RIGHT_MED, self)

        self.expandButton.setFixedSize(32, 32)
        self.expandButton.setIconSize(QSize(12, 12))

        imgPath = DirPathsInstance.AssetsDir / "F4CP_2x1_1200x600.png"
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
        self.setTitle(self.tr("Screenshots"))


class FirmwareInfoCard(SimpleCardWidget):
    def __init__(self, title: str, version: str, description: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._description = description

        self.titleLabel = BodyLabel(self)
        self.versionCaptionLabel = CaptionLabel(self)
        self.versionLabel = BodyLabel(version, self)
        self.descriptionLabel = CaptionLabel(self)
        self.vBoxLayout = QVBoxLayout(self)

        self.setObjectName("FirmwareInfoCard")
        self.descriptionLabel.setWordWrap(True)
        self.descriptionLabel.setTextColor(QColor(96, 96, 96), QColor(206, 206, 206))

        setFont(self.titleLabel, 15, QFont.DemiBold)
        setFont(self.versionLabel, 22, QFont.DemiBold)

        self.initLayout()
        self.applyTexts()

    def initLayout(self):
        self.setMinimumHeight(150)
        self.vBoxLayout.setContentsMargins(20, 18, 20, 18)
        self.vBoxLayout.setSpacing(8)
        self.vBoxLayout.addWidget(self.titleLabel)
        self.vBoxLayout.addSpacing(4)
        self.vBoxLayout.addWidget(self.versionCaptionLabel)
        self.vBoxLayout.addWidget(self.versionLabel)
        self.vBoxLayout.addSpacing(4)
        self.vBoxLayout.addWidget(self.descriptionLabel)
        self.vBoxLayout.addStretch(1)

    def setVersion(self, version: str):
        self.versionLabel.setText(version or "--")

    def applyTexts(self):
        self.titleLabel.setText(self.tr(self._title))
        self.versionCaptionLabel.setText(self.tr("Version"))
        self.descriptionLabel.setText(self.tr(self._description))


class FirmwareUpdateCard(HeaderCardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.powerFirmwareCard = FirmwareInfoCard(
            "Power firmware",
            "--",
            "Embedded power controller firmware for output control, protection, and telemetry acquisition.",
            self,
        )
        self.powerUpperCard = FirmwareInfoCard(
            "Power Upper firmware",
            VERSION,
            "Desktop Upper firmware that provides power dashboard, parameter configuration, and device operations.",
            self,
        )
        self.cardLayout = QHBoxLayout()

        self.initLayout()
        self.applyTexts()

    def initLayout(self):
        self.cardLayout.setContentsMargins(0, 0, 0, 0)
        self.cardLayout.setSpacing(12)
        self.cardLayout.addWidget(self.powerFirmwareCard)
        self.cardLayout.addWidget(self.powerUpperCard)
        self.viewLayout.addLayout(self.cardLayout)

    def applyTexts(self):
        self.setTitle(self.tr("Firmware updates"))
        self.powerFirmwareCard.applyTexts()
        self.powerUpperCard.applyTexts()


class HomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(0, 0, 15, 0)
        self.vBoxLayout.setSpacing(10)

        self.appCard = AppInfoCard(self)
        self.firmwareUpdateCard = FirmwareUpdateCard(self)
        self.galleryCard = GalleryCard(self)

        self.vBoxLayout.addWidget(self.appCard, 0, Qt.AlignTop)
        self.vBoxLayout.addWidget(self.firmwareUpdateCard, 0, Qt.AlignTop)
        self.vBoxLayout.addWidget(self.galleryCard, 0, Qt.AlignTop)
        self.vBoxLayout.addStretch(1)

        self.setObjectName("HomePage")
        StyleSheet.HOME_PAGE.apply(self)
