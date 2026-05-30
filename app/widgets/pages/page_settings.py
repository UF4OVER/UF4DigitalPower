# -*- coding: utf-8 -*-
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QApplication, QLabel, QWidget

from config import AUTHOR, FEEDBACK_URL, HELP_URL, VERSION, YEAR, cfg
from app.manager import (
    FontOption,
    applyApplicationTheme,
    apply_font_option,
    discover_font_options,
    get_saved_font_key,
    normalizedTheme,
    save_font_selection,
)
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import InfoBar, LargeTitleLabel
from qfluentwidgets import (
    BodyLabel,
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
    FluentStyleSheet,
    qconfig,
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


class ReadonlyInfoCard(SettingCard):
    def __init__(self, icon, title, content='', value='', parent=None):
        super().__init__(icon, title, content, parent)
        self.valueLabel = BodyLabel(value, self)
        self.valueLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.valueLabel.setMinimumWidth(180)
        self.hBoxLayout.addWidget(self.valueLabel, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)

    def setValue(self, value: str) -> None:
        self.valueLabel.setText(value)


class SettingsPage(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)
        self._fontOptions: list[FontOption] = []
        self._fontOptionsLoaded = False

        self.settingLabel = LargeTitleLabel('设置', self)
        self.settingLabel.setObjectName('settingLabel')

        self.appearanceGroup = SettingCardGroup('外观', self.scrollWidget)
        self.themeCard = ComboSettingCard(FIF.BRUSH, '应用主题', '切换浅色、深色或跟随系统', self.appearanceGroup)
        self.themeColorCard = CustomColorSettingCard(cfg.themeColor, FIF.PALETTE, '主题色', '调整应用的主色调', self.appearanceGroup)
        self.fontCard = ComboSettingCard(FIF.FONT, '全局字体', '选择 Resources/Font 中的字体，当前会话立即应用。', self.appearanceGroup)

        self.behaviorGroup = SettingCardGroup('启动与行为', self.scrollWidget)
        self.updateOnStartUpCard = SwitchSettingCard(
            FIF.UPDATE,
            '启动时检查更新',
            '应用启动时自动检查是否有新版本。',
            configItem=cfg.checkUpdateAtStartUp,
            parent=self.behaviorGroup,
        )

        self.projectGroup = SettingCardGroup('项目', self.scrollWidget)
        self.versionCard = ReadonlyInfoCard(FIF.INFO, '当前版本', 'F4CP 上位机版本信息', VERSION, self.projectGroup)
        self.authorCard = ReadonlyInfoCard(FIF.PEOPLE, '维护者', '项目作者与维护信息', AUTHOR, self.projectGroup)

        self.supportGroup = SettingCardGroup('支持', self.scrollWidget)
        self.helpCard = HyperlinkCard(HELP_URL, '打开帮助文档', FIF.HELP, '帮助文档', '查看使用说明、连接流程和常见问题。', self.supportGroup)
        self.feedbackCard = PrimaryPushSettingCard('提交反馈', FIF.FEEDBACK, '问题反馈', '遇到异常或有改进建议时，可以提交 issue 或反馈。', self.supportGroup)
        self.aboutCard = PrimaryPushSettingCard('查看项目说明', FIF.INFO, '关于 UF4DigitalPower', f'版权所有 {YEAR}，{AUTHOR}。版本 {VERSION}', self.supportGroup)

        self.__initWidget()

    def __initWidget(self):
        self.resize(1000, 800)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 86, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setObjectName('SettingsPage')
        self.scrollWidget.setObjectName('settingsScrollWidget')
        self.viewport().setObjectName('settingsViewport')

        self.__initLayout()
        self.__connectSignalToSlot()
        self.__refreshFontOptions()
        self.__refreshThemeOptions()
        self.__refreshThemeColorCardStyle()
        self.__setCustomColorCardTexts('主题色', '调整应用的主色调')

    def __initLayout(self):
        self.settingLabel.move(36, 30)

        self.appearanceGroup.addSettingCard(self.themeCard)
        self.appearanceGroup.addSettingCard(self.themeColorCard)
        self.appearanceGroup.addSettingCard(self.fontCard)

        self.behaviorGroup.addSettingCard(self.updateOnStartUpCard)

        self.projectGroup.addSettingCard(self.versionCard)
        self.projectGroup.addSettingCard(self.authorCard)

        self.supportGroup.addSettingCard(self.helpCard)
        self.supportGroup.addSettingCard(self.feedbackCard)
        self.supportGroup.addSettingCard(self.aboutCard)

        self.expandLayout.setSpacing(24)
        self.expandLayout.setContentsMargins(36, 10, 36, 0)
        self.expandLayout.addWidget(self.appearanceGroup)
        self.expandLayout.addWidget(self.behaviorGroup)
        self.expandLayout.addWidget(self.projectGroup)
        self.expandLayout.addWidget(self.supportGroup)

    def __connectSignalToSlot(self):
        cfg.appRestartSig.connect(self.__showRestartTooltip)
        cfg.themeChanged.connect(self._onThemeChanged)
        self.themeCard.comboBox.currentIndexChanged.connect(self.__onThemeModeChanged)
        self.themeColorCard.colorChanged.connect(self.__onThemeColorChanged)
        self.fontCard.comboBox.currentIndexChanged.connect(self.__onFontChanged)
        self.feedbackCard.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(FEEDBACK_URL)))
        self.aboutCard.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(HELP_URL)))

    def _onThemeChanged(self, *_):
        self.__refreshThemeColorCardStyle()
        self.__setCustomColorCardTexts('主题色', '调整应用的主色调')
        for widget in (self, self.scrollWidget, self.settingLabel):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def showEvent(self, event):
        super().showEvent(event)
        self.__refreshFontOptions()
        self.__refreshThemeOptions()
        self.versionCard.setValue(VERSION)
        self.authorCard.setValue(AUTHOR)

    def __showRestartTooltip(self):
        InfoBar.success('已保存', '请重启应用以完全应用改动', duration=1500, parent=self)

    def __refreshThemeOptions(self):
        value = getattr(cfg.themeMode.value, 'value', 'Auto')
        items = [('浅色', 'Light'), ('深色', 'Dark'), ('跟随系统', 'Auto')]
        self.themeCard.setItems(items, value)

        if value == 'Light':
            self.themeCard.comboBox.setCurrentIndex(0)
        elif value == 'Dark':
            self.themeCard.comboBox.setCurrentIndex(1)
        else:
            self.themeCard.comboBox.setCurrentIndex(2)

    def __onThemeModeChanged(self):
        index = self.themeCard.comboBox.currentIndex()
        modes = [Theme.LIGHT, Theme.DARK, Theme.AUTO]
        if 0 <= index < len(modes):
            qconfig.set(cfg.themeMode, modes[index])

    def __onThemeColorChanged(self, color) -> None:
        setThemeColor(color)
        applyApplicationTheme(theme=normalizedTheme(cfg.themeMode.value))
        self._onThemeChanged()

    def __refreshFontOptions(self):
        self._fontOptionsLoaded = False
        self._fontOptions = discover_font_options()
        translatedItems = []
        for option in self._fontOptions:
            label = option.label
            if option.key == '__system__':
                label = '系统默认'
            elif option.label.startswith('Built-in Default - '):
                family = option.label.removeprefix('Built-in Default - ')
                label = f'内置默认 - {family}'
            translatedItems.append((label, option.key))

        self.fontCard.setItems(translatedItems, get_saved_font_key())
        self._fontOptionsLoaded = True

    def __setCustomColorCardTexts(self, title: str, content: str) -> None:
        labels = self.themeColorCard.findChildren(QLabel)
        if len(labels) >= 2:
            labels[0].setText(title)
            labels[1].setText(content)

    def __refreshThemeColorCardStyle(self) -> None:
        FluentStyleSheet.EXPAND_SETTING_CARD.apply(self.themeColorCard.card)
        FluentStyleSheet.EXPAND_SETTING_CARD.apply(self.themeColorCard)
        for widget in (
            self.themeColorCard.choiceLabel,
            self.themeColorCard.customLabel,
            self.themeColorCard.chooseColorButton,
            self.themeColorCard.defaultRadioButton,
            self.themeColorCard.customRadioButton,
            self.themeColorCard.radioWidget,
            self.themeColorCard.customColorWidget,
            self.themeColorCard.view,
        ):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def __onFontChanged(self):
        if not self._fontOptionsLoaded:
            return

        selectedKey = self.fontCard.currentKey()
        option = next((item for item in self._fontOptions if item.key == selectedKey), None)
        if option is None:
            return

        save_font_selection(option)
        app = QApplication.instance()
        if app is not None:
            apply_font_option(app, option)

        InfoBar.success('字体已切换', '当前会话已应用所选字体，重启后会按需加载。', duration=2500, parent=self)
