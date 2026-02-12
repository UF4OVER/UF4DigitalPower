# -*- coding: utf-8 -*-

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QWidget, QLabel
from app.Config import cfg, HELP_URL, FEEDBACK_URL, AUTHOR, VERSION, YEAR, isWin11
from app.Core import StyleSheet
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import InfoBar
# use setting card components
from qfluentwidgets import (SettingCardGroup, SwitchSettingCard, OptionsSettingCard, HyperlinkCard,
                            PrimaryPushSettingCard, ScrollArea,
                            ExpandLayout, CustomColorSettingCard,
                            setTheme, setThemeColor)


class SettingsPage(ScrollArea):
    """ Setting interface """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)

        # setting label
        self.settingLabel = QLabel("设置", self)


        # personalization
        self.personalGroup = SettingCardGroup(
            ('个性化'), self.scrollWidget)

        self.themeCard = OptionsSettingCard(
            configItem=cfg.themeMode,
            icon=FIF.BRUSH,
            title="应用主题",
            content="更改外观",
            texts=['亮','暗','使用系统设置'],
            parent=self.personalGroup
        )


        self.themeColorCard = CustomColorSettingCard(
            cfg.themeColor,
            FIF.PALETTE,
            '主题颜色',
            '更改应用的主题颜色',
            self.personalGroup
        )

        # update software
        self.updateSoftwareGroup = SettingCardGroup(
            "软件更新", self.scrollWidget)
        self.updateOnStartUpCard = SwitchSettingCard(
            FIF.UPDATE,
            "启动时检查更新",
            '新版本会更稳定，功能更多',
            configItem=cfg.checkUpdateAtStartUp,
            parent=self.updateSoftwareGroup
        )

        # application
        self.aboutGroup = SettingCardGroup("关于", self.scrollWidget)
        self.helpCard = HyperlinkCard(
            HELP_URL,
            "打开帮助文档",
            FIF.HELP,
            "帮助文档",
            "如果您在使用过程中遇到任何问题，或者有任何建议，请随时反馈给我们！",
            self.aboutGroup
        )
        self.feedbackCard = PrimaryPushSettingCard(
            "有问题？",
            FIF.FEEDBACK,
            "反馈",
            "如果您在使用过程中遇到任何问题，或者有任何建议，请随时反馈给我们！",
            self.aboutGroup
        )
        self.aboutCard = PrimaryPushSettingCard(
            "查看源代码",
            FIF.INFO,
            "关于",
            f'©Copyright{YEAR}, {AUTHOR}.  版本号: {VERSION}',
            self.aboutGroup
        )

        self.__initWidget()

    def __initWidget(self):
        self.resize(1000, 800)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 80, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        # Use object names matching the qss selectors (qss filenames without .qss)
        self.setObjectName('SettingsPage')
        self.scrollWidget.setObjectName('scrollWidget')
        self.settingLabel.setObjectName('settingLabel')

        StyleSheet.SETTINGS_PAGE.apply(self)

        # initialize layout
        self.__initLayout()
        self.__connectSignalToSlot()

    def __initLayout(self):
        self.settingLabel.move(36, 30)

        self.personalGroup.addSettingCard(self.themeCard)
        self.personalGroup.addSettingCard(self.themeColorCard)

        self.updateSoftwareGroup.addSettingCard(self.updateOnStartUpCard)

        self.aboutGroup.addSettingCard(self.helpCard)
        self.aboutGroup.addSettingCard(self.feedbackCard)
        self.aboutGroup.addSettingCard(self.aboutCard)

        # add setting card group to layout
        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(36, 10, 36, 0)
        self.expandLayout.addWidget(self.personalGroup)
        self.expandLayout.addWidget(self.updateSoftwareGroup)
        self.expandLayout.addWidget(self.aboutGroup)

    def __showRestartTooltip(self):
        """ show restart tooltip """
        InfoBar.success(
            "已保存",
            "请重启应用以应用更改",
            duration=1500,
            parent=self
        )

    # def __onDownloadFolderCardClicked(self):
    #     """ download folder card clicked slot """
    #     folder = QFileDialog.getExistingDirectory(
    #         self, "选择文件夹", "./")
    #     if not folder or cfg.get(cfg.downloadFolder) == folder:
    #         return
    #
    #     cfg.set(cfg.downloadFolder, folder)
    #     self.downloadFolderCard.setContent(folder)

    def __connectSignalToSlot(self):
        """ connect signal to slot """
        cfg.appRestartSig.connect(self.__showRestartTooltip)


        cfg.themeChanged.connect(setTheme)
        # cfg.themeColorChanged.connect(setThemeColor)

        self.themeColorCard.colorChanged.connect(lambda c: setThemeColor(c))

        # about
        self.feedbackCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(FEEDBACK_URL)))
