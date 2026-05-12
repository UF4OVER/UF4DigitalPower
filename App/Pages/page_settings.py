# -*- coding: utf-8 -*-
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QLabel, QWidget, QApplication

from Config import AUTHOR, FEEDBACK_URL, HELP_URL, VERSION, YEAR, cfg
from App.Core import (
    FontOption,
    apply_font_option,
    discover_font_options,
    get_saved_font_key,
    save_font_selection,
)
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import InfoBar, LargeTitleLabel
from qfluentwidgets import (
    ComboBox,
    CustomColorSettingCard,
    ExpandLayout,
    HyperlinkCard,
    PrimaryPushSettingCard,
    ScrollArea,
    SettingCard,
    SettingCardGroup,
    SwitchSettingCard,
    Theme,
    qconfig,
    setTheme,
    setThemeColor,
)


class ComboSettingCard(SettingCard):
    def __init__(self, icon, title, content=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.comboBox = ComboBox(self)
        self.comboBox.setMinimumWidth(280)
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)

    def setItems(self, items: list[tuple[str, str]], currentKey: str) -> None:
        self.comboBox.blockSignals(True)
        self.comboBox.clear()
        currentIndex = 0
        for index, (label, key) in enumerate(items):
            self.comboBox.addItem(label, userData=key)
            if key == currentKey:
                currentIndex = index
        self.comboBox.setCurrentIndex(currentIndex)
        self.comboBox.blockSignals(False)

    def currentKey(self) -> str:
        return self.comboBox.currentData()


class SettingsPage(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)
        self._fontOptions: list[FontOption] = []
        self._fontOptionsLoaded = False

        self.settingLabel = LargeTitleLabel(self)

        self.personalGroup = SettingCardGroup("", self.scrollWidget)
        self.themeCard = ComboSettingCard(FIF.BRUSH, "", parent=self.personalGroup)
        self.themeCard.comboBox.currentIndexChanged.connect(self.__onThemeModeChanged)

        self.themeColorCard = CustomColorSettingCard(
            cfg.themeColor, FIF.PALETTE, "", "", self.personalGroup
        )

        self.fontCard = ComboSettingCard(FIF.FONT, "", parent=self.personalGroup)

        self.updateSoftwareGroup = SettingCardGroup("", self.scrollWidget)
        self.updateOnStartUpCard = SwitchSettingCard(
            FIF.UPDATE,
            "",
            "",
            configItem=cfg.checkUpdateAtStartUp,
            parent=self.updateSoftwareGroup,
        )

        self.aboutGroup = SettingCardGroup("", self.scrollWidget)
        self.helpCard = HyperlinkCard(HELP_URL, "", FIF.HELP, "", "", self.aboutGroup)
        self.feedbackCard = PrimaryPushSettingCard(
            "", FIF.FEEDBACK, "", "", self.aboutGroup
        )
        self.aboutCard = PrimaryPushSettingCard("", FIF.INFO, "", "", self.aboutGroup)

        self.__initWidget()

    def __initWidget(self):
        self.resize(1000, 800)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 80, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setObjectName("SettingsPage")
        self.scrollWidget.setObjectName("scrollWidget")

        self.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            #scrollWidget {
                background-color: transparent;
            }
            """)

        self.__initLayout()
        self.__connectSignalToSlot()
        self.__refreshFontOptions()
        self.__refreshThemeOptions()
        self._applyTexts()

    def __initLayout(self):
        self.settingLabel.move(36, 30)

        self.personalGroup.addSettingCard(self.themeCard)
        self.personalGroup.addSettingCard(self.themeColorCard)
        self.personalGroup.addSettingCard(self.fontCard)

        self.updateSoftwareGroup.addSettingCard(self.updateOnStartUpCard)

        self.aboutGroup.addSettingCard(self.helpCard)
        self.aboutGroup.addSettingCard(self.feedbackCard)
        self.aboutGroup.addSettingCard(self.aboutCard)

        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(36, 10, 36, 0)
        self.expandLayout.addWidget(self.personalGroup)
        self.expandLayout.addWidget(self.updateSoftwareGroup)
        self.expandLayout.addWidget(self.aboutGroup)

    def __connectSignalToSlot(self):
        cfg.appRestartSig.connect(self.__showRestartTooltip)
        cfg.themeChanged.connect(setTheme)
        self.themeColorCard.colorChanged.connect(lambda c: setThemeColor(c))
        self.fontCard.comboBox.currentIndexChanged.connect(self.__onFontChanged)
        self.feedbackCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(FEEDBACK_URL))
        )

    def showEvent(self, event):
        super().showEvent(event)
        self.__refreshFontOptions()

    def _applyTexts(self):
        self.settingLabel.setText('设置')
        self.personalGroup.titleLabel.setText('个性化')
        self.updateSoftwareGroup.titleLabel.setText('软件更新')
        self.aboutGroup.titleLabel.setText('关于')

        self.themeCard.titleLabel.setText('应用主题')
        self.themeCard.contentLabel.setText(
            '切换浅色、深色或跟随系统'
        )
        self.__refreshThemeOptions()

        self.__setCustomColorCardTexts(
            '主题色',
            '调整应用的主色调',
        )

        self.fontCard.titleLabel.setText('全局字体')
        self.fontCard.contentLabel.setText(
            "将字体文件放到 Resources/Font，重启后会按需加载所选字体。"
        )
        self.__refreshFontOptions()

        self.updateOnStartUpCard.titleLabel.setText(
            '启动时检查更新'
        )
        self.updateOnStartUpCard.contentLabel.setText(
            '在应用启动时检查是否有新版本'
        )

        self.helpCard.setTitle('帮助')
        self.helpCard.setContent('查看使用说明和常见问题。')
        self.helpCard.linkButton.setText('打开帮助文档')

        self.feedbackCard.setTitle('反馈')
        self.feedbackCard.setContent(
            '遇到问题或有改进建议时可以在这里反馈。'
        )
        self.feedbackCard.button.setText('提交反馈')

        self.aboutCard.setTitle('关于')
        self.aboutCard.setContent(f"版权所有 {YEAR}，{AUTHOR}。版本 {VERSION}")
        self.aboutCard.button.setText('查看项目说明')

    def __showRestartTooltip(self):
        InfoBar.success(
            '已保存',
            '请重启应用以完全应用改动',
            duration=1500,
            parent=self,
        )

    def __refreshThemeOptions(self):
        value = getattr(cfg.themeMode.value, "value", "Auto")
        items = [
            ('浅色', "Light"),
            ('深色', "Dark"),
            ('跟随系统', "Auto"),
        ]
        self.themeCard.setItems(items, value)

        if value == "Light":
            self.themeCard.comboBox.setCurrentIndex(0)
        elif value == "Dark":
            self.themeCard.comboBox.setCurrentIndex(1)
        else:
            self.themeCard.comboBox.setCurrentIndex(2)

    def __onThemeModeChanged(self):
        index = self.themeCard.comboBox.currentIndex()
        modes = [Theme.LIGHT, Theme.DARK, Theme.AUTO]
        if 0 <= index < len(modes):
            qconfig.set(cfg.themeMode, modes[index])

    def __refreshFontOptions(self):
        self._fontOptionsLoaded = False
        self._fontOptions = discover_font_options()
        translatedItems = []
        for option in self._fontOptions:
            label = option.label
            if option.key == "__system__":
                label = '系统默认'
            elif option.label.startswith("Built-in Default - "):
                family = option.label.removeprefix("Built-in Default - ")
                label = '内置默认 - {family}'.format(family=family)
            translatedItems.append((label, option.key))

        self.fontCard.setItems(translatedItems, get_saved_font_key())
        self._fontOptionsLoaded = True

    def __setCustomColorCardTexts(self, title: str, content: str) -> None:
        labels = self.themeColorCard.findChildren(QLabel)
        if len(labels) >= 3:
            labels[0].setText(title)
            labels[1].setText(content)

    def __onFontChanged(self):
        if not self._fontOptionsLoaded:
            return

        selectedKey = self.fontCard.currentKey()
        option = next(
            (item for item in self._fontOptions if item.key == selectedKey), None
        )
        if option is None:
            return

        save_font_selection(option)

        app = QApplication.instance()
        if app is not None:
            apply_font_option(app, option)

        InfoBar.success(
            '字体已切换',
            "当前会话已应用所选字体，重启后会按需加载。",
            duration=2500,
            parent=self,
        )
