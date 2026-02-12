# -*- coding: utf-8 -*-
"""Home page (主页)

Keep the UI/layout consistent with the original `start.py` demo code.
"""

from PyQt5.QtCore import Qt, QSize, QUrl
from PyQt5.QtGui import QFont, QColor, QImage
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from app.Config import SettingMangerInstance as SMI, AppIconPath
from app.Core import StyleSheet
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
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
    FluentIcon,
)


class StatisticsWidget(QWidget):

    def __init__(self, title: str, value: str, parent=None):
        super().__init__(parent=parent)
        self.titleLabel = CaptionLabel(title, self)
        self.valueLabel = BodyLabel(value, self)
        self.vBoxLayout = QVBoxLayout(self)

        m = 16
        self.vBoxLayout.setContentsMargins(m, 0, m, 0)
        self.vBoxLayout.addWidget(
            self.valueLabel,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addWidget(
            self.titleLabel,
            0,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)

        setFont(self.valueLabel, 18, QFont.DemiBold)

        self.titleLabel.setTextColor(QColor(96, 96, 96), QColor(206, 206, 206))


class AppInfoCard(SimpleCardWidget):
    """App information card (原 demo 保持不变)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.iconLabel = ImageLabel(QImage(AppIconPath), self)
        self.iconLabel.setBorderRadius(8, 8, 8, 8)
        self.iconLabel.scaledToWidth(120)

        self.nameLabel = BodyLabel('Fluor4CellPower', self)
        setFont(self.nameLabel, 16, QFont.DemiBold)

        self.installButton = PrimaryPushButton('更新', self)
        self.companyLabel = HyperlinkLabel(
            QUrl('https://github.com/UF4OVER'), 'UF4OVER', self)
        self.installButton.setFixedWidth(160)

        self.scoreWidget = StatisticsWidget('平均', '5.0', self)
        self.separator = VerticalSeparator(self)
        self.commentWidget = StatisticsWidget('评论数', '3K', self)

        self.descriptionLabel = BodyLabel(
            'Fluor4CellPower是一个多功能上位机软件，提供串口通信、数据可视化、设备管理等功能，适用于各种电子设备的调试和监控。',
            self)
        self.descriptionLabel.setWordWrap(True)
        # self.descriptionLabel.setStyleSheet(f'QLabel {{padding-right: {(125)}px}}')

        self.tagButton = PillPushButton('功能库', self)
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

    def initLayout(self):
        self.hBoxLayout.setSpacing(30)
        self.hBoxLayout.setContentsMargins(34, 24, 24, 24)
        self.hBoxLayout.addWidget(self.iconLabel)
        self.hBoxLayout.addLayout(self.vBoxLayout)

        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(0)

        # name label and install button
        self.vBoxLayout.addLayout(self.topLayout)
        self.topLayout.setContentsMargins(0, 0, 0, 0)
        self.topLayout.addWidget(self.nameLabel)
        self.topLayout.addWidget(self.installButton, 0, Qt.AlignmentFlag.AlignRight)

        # company label
        self.vBoxLayout.addSpacing(3)
        self.vBoxLayout.addWidget(self.companyLabel)

        # statistics widgets
        self.vBoxLayout.addSpacing(20)
        self.vBoxLayout.addLayout(self.statisticsLayout)
        self.statisticsLayout.setContentsMargins(0, 0, 0, 0)
        self.statisticsLayout.setSpacing(10)
        self.statisticsLayout.addWidget(self.scoreWidget)
        self.statisticsLayout.addWidget(self.separator)
        self.statisticsLayout.addWidget(self.commentWidget)
        self.statisticsLayout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # description label
        self.vBoxLayout.addSpacing(20)
        self.vBoxLayout.addWidget(self.descriptionLabel)

        # button
        self.vBoxLayout.addSpacing(12)
        self.buttonLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.addLayout(self.buttonLayout)
        self.buttonLayout.addWidget(self.tagButton, 0, Qt.AlignmentFlag.AlignLeft)
        self.buttonLayout.addWidget(self.shareButton, 0, Qt.AlignmentFlag.AlignRight)


class GalleryCard(HeaderCardWidget):
    """Gallery card (原 demo 保持不变)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle('截图')

        self.flipView = HorizontalFlipView(self)
        self.expandButton = TransparentToolButton(FluentIcon.CHEVRON_RIGHT_MED, self)

        self.expandButton.setFixedSize(32, 32)
        self.expandButton.setIconSize(QSize(12, 12))

        img_path = SMI.AssetsDir / 'F4CP_2x1_1200x600.png'
        self.flipView.addImages([QImage(str(img_path))])
        self.flipView.setBorderRadius(8)
        self.flipView.setSpacing(10)

        item_size = QSize(620, 351)
        self.flipView.setItemSize(item_size)
        self.flipView.setMinimumSize(item_size)

        self.headerLayout.addWidget(self.expandButton, 0, Qt.AlignmentFlag.AlignRight)
        self.viewLayout.addWidget(self.flipView)


class HomePage(QWidget):
    """主页页面，用于放到 MSFluentWindow 的导航系统里。"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(0, 0, (15), 0)
        self.vBoxLayout.setSpacing((10))

        self.appCard = AppInfoCard(self)
        self.galleryCard = GalleryCard(self)

        self.vBoxLayout.addWidget(self.appCard, 0, Qt.AlignTop)
        self.vBoxLayout.addWidget(self.galleryCard, 0, Qt.AlignTop)
        self.vBoxLayout.addStretch(1)

        # self.setStyleSheet('QWidget {background:transparent}')
        self.setObjectName('HomePage')

        StyleSheet.HOME_PAGE.apply(self)
