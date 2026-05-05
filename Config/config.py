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
from functools import cached_property
from pathlib import Path
from typing import Union
from PyQt5.QtCore import QSettings
from qfluentwidgets import qconfig, QConfig, ConfigItem, BoolValidator


class _DirPaths:

    def _ensureDir(self, *parts: str) -> Path:
        """根据基础目录创建并返回目标目录。"""
        directory = self.BaseDir.joinpath(*parts)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _ensureSubDir(self, baseDir: Path, *parts: str) -> Path:
        """根据已有目录创建并返回子目录。"""
        directory = baseDir.joinpath(*parts)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

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
        return self._ensureSubDir(self.ResourcesDir, "Assets")

    @cached_property
    def ConfigDir(self) -> Path:
        """
        return: Config目录的Path对象
        """
        return self._ensureSubDir(self.ResourcesDir, "Config")

    @cached_property
    def ThemeDir(self) -> Path:
        """
        return: Theme目录的Path对象
        """
        return self._ensureSubDir(self.ResourcesDir, "Theme")

    @cached_property
    def FontDir(self) -> Path:
        """
        return: Font目录的Path对象
        """
        return self._ensureSubDir(self.ResourcesDir, "Font")

    @cached_property
    def LogDir(self) -> Path:
        """
        return: Logs目录的Path对象
        """
        return self._ensureDir("Logs")

    @cached_property
    def ResourcesDir(self) -> Path:
        """
        return: Resources目录的Path对象
        """
        return self._ensureDir("Resources")

    @cached_property
    def ToolsDir(self) -> Path:
        """
        return: Tools目录的Path对象
        """
        return self._ensureSubDir(self.ResourcesDir, "Tools")

    @cached_property
    def FirmwareDir(self) -> Path:
        """
        return: Firmware目录的Path对象
        """
        return self._ensureSubDir(self.ToolsDir, "Firmware")

    @cached_property
    def McuPackDir(self) -> Path:
        """
        return: Pack目录的Path对象
        """
        return self._ensureSubDir(self.ToolsDir, "Pack")

    @cached_property
    def McuPack(self) -> Path:
        """
        return: McuPack目录的Path对象，0.1.3 之后弃用
        """
        return self.McuPackDir

    @cached_property
    def LanguageDir(self) -> Path:
        """
        return: Language目录的Path对象
        """
        return self._ensureSubDir(self.ResourcesDir, "Language")

    @cached_property
    def FirmwarePowerDir(self) -> Path:
        """
        return: Power固件目录的Path对象
        """
        return self._ensureSubDir(self.FirmwareDir, "Power")

    @cached_property
    def FirmwarePower(self) -> Path:
        return self.FirmwarePowerDir

    @cached_property
    def FirmwareUpperDir(self) -> Path:
        """
        return: Upper固件目录的Path对象
        """
        return self._ensureSubDir(self.FirmwareDir, "Upper")

    @cached_property
    def FirmwareUpper(self) -> Path:
        return self.FirmwareUpperDir


_dirPaths = _DirPaths()
DirPathsInstance = _dirPaths

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


VERSION_LOCAL_SECTION = "OldVersion"
VERSION_REMOTE_SECTION = "NewVersion"
UPDATE_SECTION = "update"

LOCAL_APP_VERSION_OPTION = "OldLocalVersion"
LOCAL_UPPER_VERSION_OPTION = "OldUpperVersion"
LOCAL_LOWER_VERSION_OPTION = "OldLowerVersion"

LATEST_APP_VERSION_OPTION = "NewLocalVersion"
LATEST_UPPER_VERSION_OPTION = "NewUpperVersion"
LATEST_LOWER_VERSION_OPTION = "NewLowerVersion"

UPDATE_URL_OPTION = "UpdateUrl"


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
APP_CONFIG_PATH = _dirPaths.ConfigDir / "config.ini"

SettingMangerInstance = SettingsManager(APP_CONFIG_PATH)
logger.info(f"SettingsManager initialized with config path: {APP_CONFIG_PATH}")

# -------------------------------config of qfluentwidgets-------------------------------
cfg = Config()
# cfg.themeMode.value = Theme.AUTO
_config_json_path = _dirPaths.ConfigDir / "config.json"
qconfig.load(_config_json_path, cfg)

logger.info(f"Config loaded from {_config_json_path}")

AppIconPath = str(_dirPaths.AssetsDir / "F4CP_ICO_256.ico")
