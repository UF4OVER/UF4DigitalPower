# -*- coding: utf-8 -*-
from PyQt5.QtCore import QEvent, Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QApplication, QLabel, QWidget

from Config import AUTHOR, FEEDBACK_URL, HELP_URL, VERSION, YEAR, cfg
from app.Core import (
    FontOption,
    apply_font_option,
    discover_font_options,
    get_saved_font_key,
    save_font_selection,
)
from app.Core import LANGUAGE_EN_US, LANGUAGE_ZH_CN, language_manager
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

    def set_items(self, items: list[tuple[str, str]], current_key: str) -> None:
        self.comboBox.blockSignals(True)
        self.comboBox.clear()
        current_index = 0
        for index, (label, key) in enumerate(items):
            self.comboBox.addItem(label, userData=key)
            if key == current_key:
                current_index = index
        self.comboBox.setCurrentIndex(current_index)
        self.comboBox.blockSignals(False)

    def current_key(self) -> str:
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

        self.themeColorCard = CustomColorSettingCard(cfg.themeColor, FIF.PALETTE, "", "", self.personalGroup)

        self.languageCard = ComboSettingCard(FIF.LANGUAGE, "", parent=self.personalGroup)
        self.languageCard.comboBox.currentIndexChanged.connect(self.__onLanguageChanged)

        self.fontCard = ComboSettingCard(FIF.FONT, "", parent=self.personalGroup)

        self.updateSoftwareGroup = SettingCardGroup("", self.scrollWidget)
        self.updateOnStartUpCard = SwitchSettingCard(FIF.UPDATE, "", "", configItem=cfg.checkUpdateAtStartUp, parent=self.updateSoftwareGroup)

        self.aboutGroup = SettingCardGroup("", self.scrollWidget)
        self.helpCard = HyperlinkCard(HELP_URL, "", FIF.HELP, "", "", self.aboutGroup)
        self.feedbackCard = PrimaryPushSettingCard("", FIF.FEEDBACK, "", "", self.aboutGroup)
        self.aboutCard = PrimaryPushSettingCard("", FIF.INFO, "", "", self.aboutGroup)

        self.__initWidget()

    def __initWidget(self):
        self.resize(1000, 800)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
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
        self.__refreshFontOptions()
        self.__refreshThemeOptions()
        self.__refreshLanguageOptions()
        self._retranslate_ui()

    def __initLayout(self):
        self.settingLabel.move(36, 30)

        self.personalGroup.addSettingCard(self.themeCard)
        self.personalGroup.addSettingCard(self.themeColorCard)
        self.personalGroup.addSettingCard(self.languageCard)
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
        self.feedbackCard.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(FEEDBACK_URL)))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.LanguageChange:
            self._retranslate_ui()

    def showEvent(self, event):
        super().showEvent(event)
        self.__refreshFontOptions()

    def _retranslate_ui(self):
        self.settingLabel.setText(self.tr("Settings"))
        self.personalGroup.titleLabel.setText(self.tr("Personalization"))
        self.updateSoftwareGroup.titleLabel.setText(self.tr("Software update"))
        self.aboutGroup.titleLabel.setText(self.tr("About"))

        self.themeCard.titleLabel.setText(self.tr("Application theme"))
        self.themeCard.contentLabel.setText(self.tr("Switch between light, dark, or system theme"))
        self.__refreshThemeOptions()

        self.__set_custom_color_card_texts(
            self.tr("Theme color"),
            self.tr("Adjust the primary accent color of the application"),
        )

        self.languageCard.titleLabel.setText(self.tr("Language"))
        self.languageCard.contentLabel.setText(self.tr("Switch the application language between Chinese and English"))
        self.__refreshLanguageOptions()

        self.fontCard.titleLabel.setText(self.tr("Global font"))
        self.fontCard.contentLabel.setText(
            self.tr("Put font files in Resources/Font. The selected font will be lazily loaded after restart.")
        )
        self.__refreshFontOptions()

        self.updateOnStartUpCard.titleLabel.setText(self.tr("Check for updates on startup"))
        self.updateOnStartUpCard.contentLabel.setText(self.tr("Check whether a new version is available when the app starts"))

        self.helpCard.setTitle(self.tr("Help"))
        self.helpCard.setContent(self.tr("View instructions and common questions."))
        self.helpCard.linkButton.setText(self.tr("Open help documentation"))

        self.feedbackCard.setTitle(self.tr("Feedback"))
        self.feedbackCard.setContent(self.tr("Report issues or share suggestions here."))
        self.feedbackCard.button.setText(self.tr("Send feedback"))

        self.aboutCard.setTitle(self.tr("About"))
        self.aboutCard.setContent(f"Copyright {YEAR}, {AUTHOR}. Version {VERSION}")
        self.aboutCard.button.setText(self.tr("View project info"))

    def __showRestartTooltip(self):
        InfoBar.success(
            self.tr("Saved"),
            self.tr("Restart the app to fully apply the change"),
            duration=1500,
            parent=self,
        )

    def __refreshThemeOptions(self):
        value = getattr(cfg.themeMode.value, "value", "Auto")
        items = [(self.tr("Light"), "Light"), (self.tr("Dark"), "Dark"), (self.tr("Use system setting"), "Auto")]
        self.themeCard.set_items(items, value)

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

    def __refreshLanguageOptions(self):
        current_key = language_manager.get_saved_language()
        items = [("中文", LANGUAGE_ZH_CN), ("English", LANGUAGE_EN_US)]
        self.languageCard.set_items(items, current_key)

    def __onLanguageChanged(self):
        app = QApplication.instance()
        if app is None:
            return

        selected_key = self.languageCard.current_key()
        if not selected_key or selected_key == language_manager.current_language():
            return

        language_manager.save_language(selected_key)
        language_manager.apply_language(app, selected_key)
        InfoBar.success(
            self.tr("Settings saved"),
            self.tr("Language switched successfully."),
            duration=2000,
            parent=self,
        )

    def __refreshFontOptions(self):
        self._fontOptionsLoaded = False
        self._fontOptions = discover_font_options()
        translated_items = []
        for option in self._fontOptions:
            label = option.label
            if option.key == "__system__":
                label = self.tr("System Default")
            elif option.label.startswith("Built-in Default - "):
                family = option.label.removeprefix("Built-in Default - ")
                label = self.tr("Built-in Default - {family}").format(family=family)
            translated_items.append((label, option.key))

        self.fontCard.set_items(translated_items, get_saved_font_key())
        self._fontOptionsLoaded = True

    def __set_custom_color_card_texts(self, title: str, content: str) -> None:
        labels = self.themeColorCard.findChildren(QLabel)
        if len(labels) >= 3:
            labels[0].setText(title)
            labels[1].setText(content)

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
            self.tr("Font switched"),
            self.tr("The font has been applied in the current session. It will be lazily loaded after restart."),
            duration=2500,
            parent=self,
        )
