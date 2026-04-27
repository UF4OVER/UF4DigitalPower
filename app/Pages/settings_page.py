# -*- coding: utf-8 -*-

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QApplication, QWidget

from Config import AUTHOR, FEEDBACK_URL, HELP_URL, VERSION, YEAR, cfg
from app.Core.font_manager import (
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
    OptionsSettingCard,
    PrimaryPushSettingCard,
    ScrollArea,
    SettingCard,
    SettingCardGroup,
    SwitchSettingCard,
    setTheme,
    setThemeColor,
)


class FontComboSettingCard(SettingCard):
    """Setting card with a combo box for selecting the global font."""

    def __init__(self, icon, title, content=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.comboBox = ComboBox(self)
        self.comboBox.setMinimumWidth(280)
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)

    def set_options(self, options: list[FontOption], current_key: str):
        self.comboBox.blockSignals(True)
        self.comboBox.clear()

        current_index = 0
        for index, option in enumerate(options):
            self.comboBox.addItem(option.label, userData=option.key)
            if option.key == current_key:
                current_index = index

        self.comboBox.setCurrentIndex(current_index)
        self.comboBox.blockSignals(False)

    def current_key(self) -> str:
        return self.comboBox.currentData()


class SettingsPage(ScrollArea):
    """Setting interface."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)
        self._fontOptions: list[FontOption] = []
        self._fontOptionsLoaded = False

        self.settingLabel = LargeTitleLabel("设置", self)

        self.personalGroup = SettingCardGroup("个性化", self.scrollWidget)
        self.themeCard = OptionsSettingCard(
            configItem=cfg.themeMode,
            icon=FIF.BRUSH,
            title="应用主题",
            content="切换浅色、深色或跟随系统",
            texts=["浅色", "深色", "跟随系统"],
            parent=self.personalGroup,
        )

        self.themeColorCard = CustomColorSettingCard(
            cfg.themeColor,
            FIF.PALETTE,
            "主题色",
            "调整应用的主色调",
            self.personalGroup,
        )

        self.fontCard = FontComboSettingCard(
            FIF.FONT,
            "全局字体",
            "把字体文件放进 Resources/Font，重启后会按需懒加载选中的字体。",
            self.personalGroup,
        )

        self.updateSoftwareGroup = SettingCardGroup("软件更新", self.scrollWidget)
        self.updateOnStartUpCard = SwitchSettingCard(
            FIF.UPDATE,
            "启动时检查更新",
            "在应用启动时检查是否有新版本",
            configItem=cfg.checkUpdateAtStartUp,
            parent=self.updateSoftwareGroup,
        )

        self.aboutGroup = SettingCardGroup("关于", self.scrollWidget)
        self.helpCard = HyperlinkCard(
            HELP_URL,
            "打开帮助文档",
            FIF.HELP,
            "帮助文档",
            "查看使用说明和常见问题。",
            self.aboutGroup,
        )
        self.feedbackCard = PrimaryPushSettingCard(
            "提交反馈",
            FIF.FEEDBACK,
            "反馈",
            "遇到问题或有改进建议时可以在这里反馈。",
            self.aboutGroup,
        )
        self.aboutCard = PrimaryPushSettingCard(
            "查看项目说明",
            FIF.INFO,
            "关于",
            f"Copyright {YEAR}, {AUTHOR}. Version {VERSION}",
            self.aboutGroup,
        )

        self.__initWidget()

    def __initWidget(self):
        self.resize(1000, 800)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 80, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setObjectName("SettingsPage")
        self.scrollWidget.setObjectName("scrollWidget")

        self.setStyleSheet(
            """
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            #scrollWidget {
                background-color: transparent;
            }
            """
        )

        self.__initLayout()
        self.__connectSignalToSlot()

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

    def __showRestartTooltip(self):
        InfoBar.success(
            "已保存",
            "请重启应用以完全应用改动",
            duration=1500,
            parent=self,
        )

    def __connectSignalToSlot(self):
        cfg.appRestartSig.connect(self.__showRestartTooltip)
        cfg.themeChanged.connect(setTheme)
        self.themeColorCard.colorChanged.connect(lambda c: setThemeColor(c))
        self.fontCard.comboBox.currentIndexChanged.connect(self.__onFontChanged)
        self.feedbackCard.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(FEEDBACK_URL)))

    def showEvent(self, event):
        super().showEvent(event)
        self.__refreshFontOptions()

    def __refreshFontOptions(self):
        self._fontOptions = discover_font_options()
        self.fontCard.set_options(self._fontOptions, get_saved_font_key())
        self._fontOptionsLoaded = True

    def __onFontChanged(self):
        if not self._fontOptionsLoaded:
            return

        selected_key = self.fontCard.current_key()
        option = next((item for item in self._fontOptions if item.key == selected_key), None)
        if option is None:
            return

        save_font_selection(option)

        app = QApplication.instance()
        if app is not None:
            apply_font_option(app, option)

        InfoBar.success(
            "字体已切换",
            "当前会话已应用，重启后会按需懒加载所选字体。",
            duration=2500,
            parent=self,
        )
