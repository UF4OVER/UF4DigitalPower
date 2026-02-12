# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-14 14:13
#  @FileName: config_ini.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------
import sys
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Union

from PyQt5.QtCore import QSettings, QLocale
from qfluentwidgets import (qconfig, QConfig, ConfigItem, OptionsConfigItem, BoolValidator,
                            OptionsValidator, RangeConfigItem, RangeValidator,
                            FolderListValidator, Theme, FolderValidator, ConfigSerializer, __version__)


class SettingsManager:
    def __init__(self, config_path: Path):
        self.config_path = str(config_path.resolve())
        self.settings = QSettings(self.config_path, QSettings.Format.IniFormat)

    def get(self, section: str, option: str, fallback: Union[str, int, bool] = None) -> Union[str, int, bool]:
        key = f"{section}/{option}"
        if self.settings.contains(key):
            value = self.settings.value(key)
            if isinstance(fallback, bool):
                return value.lower() == 'true' if isinstance(value, str) else bool(value)
            if isinstance(fallback, int):
                try:
                    return int(value)
                except ValueError:
                    return fallback
            return value
        return fallback

    def set(self, section: str, option: str, value: Union[str, int, bool]):
        key = f"{section}/{option}"
        self.settings.setValue(key, value)
        self.settings.sync()
    @cached_property
    def BaseDir(self) -> Path:
        if getattr(sys, 'frozen', False):
            # 打包后
            return Path(sys.executable).resolve().parent
        else:
            # 正常运行
            print(str(sys.executable))
            print(Path(__file__).resolve().parent.parent.parent)
            return Path(__file__).resolve().parent.parent.parent

    @cached_property
    def AssetsDir(self) -> Path:
        return self.BaseDir / "Resources" / "Assets"

    @cached_property
    def ConfigDir(self) -> Path:
        return self.BaseDir / "Resources" / "Config"

    @cached_property
    def ThemeDir(self) -> Path:
        return self.BaseDir / "Resources" / "Theme"


class Language(Enum):
    """ Language enumeration """

    CHINESE_SIMPLIFIED = QLocale(QLocale.Chinese, QLocale.China)
    CHINESE_TRADITIONAL = QLocale(QLocale.Chinese, QLocale.HongKong)
    ENGLISH = QLocale(QLocale.English)
    AUTO = QLocale()


class LanguageSerializer(ConfigSerializer):
    """ Language serializer """

    def serialize(self, language):
        return language.value.name() if language != Language.AUTO else "Auto"

    def deserialize(self, value: str):
        return Language(QLocale(value)) if value != "Auto" else Language.AUTO


def isWin11():
    return sys.platform == 'win32' and sys.getwindowsversion().build >= 22000


class Config(QConfig):
    """ Config of application """

    micaEnabled = ConfigItem("MainWindow", "MicaEnabled", isWin11(), BoolValidator())

    # software update
    checkUpdateAtStartUp = ConfigItem("Update", "CheckUpdateAtStartUp", True, BoolValidator())


YEAR = 2023
AUTHOR = "zhiyiYo"
VERSION = __version__
HELP_URL = "https://qfluentwidgets.com"
REPO_URL = "https://github.com/zhiyiYo/PyQt-Fluent-Widgets"
EXAMPLE_URL = "https://github.com/zhiyiYo/PyQt-Fluent-Widgets/tree/master/examples"
FEEDBACK_URL = "https://github.com/zhiyiYo/PyQt-Fluent-Widgets/issues"
RELEASE_URL = "https://github.com/zhiyiYo/PyQt-Fluent-Widgets/releases/latest"
ZH_SUPPORT_URL = "https://qfluentwidgets.com/zh/price/"
EN_SUPPORT_URL = "https://qfluentwidgets.com/price/"


SettingMangerInstance = SettingsManager(config_path=Path("config.ini"))
AppIconPath = str(SettingMangerInstance.AssetsDir / "F4CP_ICO_256.ico")

cfg = Config()
cfg.themeMode.value = Theme.AUTO
qconfig.load(SettingMangerInstance.ConfigDir / "config.json", cfg)