# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-14 14:13
#  @FileName: config.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------
import logging
import sys
from datetime import datetime
from functools import cached_property, cache
from os import makedirs
from pathlib import Path
from typing import Union
from warnings import warn
from PyQt5.QtCore import QSettings
from PyQt5.QtGui import QFontDatabase, QFont
from qfluentwidgets import (qconfig, QConfig, ConfigItem, BoolValidator,
                            Theme, __version__)


class DirPaths:

    @cached_property
    def BaseDir(self) -> Path:
        """
        return: 应用程序的基础目录Path对象
        """
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).resolve().parent
        else:
            return Path(__file__).resolve().parent.parent

    @cached_property
    def AssetsDir(self) -> Path:
        """
        return: Assets目录的Path对象
        """
        _assetsDir = self.BaseDir / "Resources" / "Assets"
        if not _assetsDir.exists():
            makedirs(_assetsDir, exist_ok=True)
        return _assetsDir

    @cached_property
    def ConfigDir(self) -> Path:
        """
        return: Config目录的Path对象
        """
        _configDir = self.BaseDir / "Resources" / "Config"
        if not _configDir.exists():
            makedirs(_configDir, exist_ok=True)
        return _configDir

    @cached_property
    def ThemeDir(self) -> Path:
        """
        return: Theme目录的Path对象
        """
        _themeDir = self.BaseDir / "Resources" / "Theme"
        if not _themeDir.exists():
            makedirs(_themeDir, exist_ok=True)
        return _themeDir

    @cached_property
    def FontDir(self) -> Path:
        """
        return: Font目录的Path对象
        """
        _fontDir = self.BaseDir / "Resources" / "Font"
        if not _fontDir.exists():
            makedirs(_fontDir, exist_ok=True)
        return _fontDir

    @cached_property
    def LogDir(self) -> Path:
        """
        return: Logs目录的Path对象
        """
        _logDir = self.BaseDir / "Logs"
        if not _logDir.exists():
            makedirs(_logDir, exist_ok=True)
        return _logDir

    @cached_property
    def McuPack(self) -> Path:
        """
        return: McuPack目录的Path对象，0.1.3 之后弃用
        """
        _McuPack = self.BaseDir / "Resources" / "Tools" / "Pack"
        if not _McuPack.exists():
            makedirs(_McuPack, exist_ok=True)
        return _McuPack




_dirPaths = DirPaths()

# 日志文件夹路径
LOG_DIR = _dirPaths.LogDir

# 按年月日_时分生成文件名
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
LOG_PATH = LOG_DIR / f"{timestamp}.log"

# 创建日志器
logger = logging.getLogger("F4CP")
logger.setLevel(logging.DEBUG)

# 控制台输出
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# 文件输出
file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)

# 日志格式
formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

if not logger.hasHandlers():
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)



class SettingsManager:
    def __init__(self, config_path: Path):
        self.config_path = str(config_path.resolve())
        self.settings = QSettings(self.config_path, QSettings.Format.IniFormat)

        # QTimer.singleShot(0, self.loadFontToWidget)

    def get(self, section: str, option: str, fallback: Union[str, int, bool] = None) -> Union[str, int, bool]:
        key = f"{section}/{option}"
        if self.settings.contains(key):
            value = self.settings.value(key)
            if isinstance(fallback, bool):
                logger.info(f"{self.__class__.__name__} Fallback value: {fallback}")
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
        logger.info(f"{self.__class__.__name__} Setting {key} to {value}")
        self.settings.setValue(key, value)
        self.settings.sync()


def isWin11():
    return sys.platform == 'win32' and sys.getwindowsversion().build >= 22000


class Config(QConfig):
    """ Config of application """

    micaEnabled = ConfigItem("MainWindow", "MicaEnabled", isWin11(), BoolValidator())

    checkUpdateAtStartUp = ConfigItem("Update", "CheckUpdateAtStartUp", True, BoolValidator())

    enableAcrylicBackground = ConfigItem("MainWindow", "EnableAcrylicBackground", False, BoolValidator())

YEAR = 2026
AUTHOR = "UF4OVER"
VERSION = "1.4.0423"
HELP_URL = "https://hepi.ng"
REPO_URL = "https://github.com/zhiyiYo/PyQt-Fluent-Widgets"
EXAMPLE_URL = "https://github.com/zhiyiYo/PyQt-Fluent-Widgets/tree/master/examples"
FEEDBACK_URL = "https://github.com/zhiyiYo/PyQt-Fluent-Widgets/issues"
RELEASE_URL = "https://github.com/zhiyiYo/PyQt-Fluent-Widgets/releases/latest"
ZH_SUPPORT_URL = "https://qfluentwidgets.com/zh/price/"
EN_SUPPORT_URL = "https://qfluentwidgets.com/price/"

# -------------------------------config of application-------------------------------
_iniPath = _dirPaths.ConfigDir / "config.ini"

SettingMangerInstance = SettingsManager(_iniPath)
logger.info(f"SettingsManager initialized with config path: {_iniPath}")

# -------------------------------config of qfluentwidgets-------------------------------
cfg = Config()
cfg.themeMode.value = Theme.AUTO
_config_json_path = _dirPaths.ConfigDir / "config.json"
qconfig.load(_config_json_path, cfg)
logger.info(f"Config loaded from {_config_json_path}")

AppIconPath = str(_dirPaths.AssetsDir / "F4CP_ICO_256.ico")
