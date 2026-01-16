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
from pathlib import Path
from typing import Union

from PyQt5.QtCore import QSettings


class SettingsManager:
    def __init__(self, config_path: Path):
        self.config_path = str(config_path.resolve())
        self.settings = QSettings(self.config_path, QSettings.IniFormat)

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

    @property
    def BaseDir(self) -> Path:
        if getattr(sys, 'frozen', False):
            # 打包后
            return Path(sys.executable).resolve().parent
        else:
            # 正常运行
            return Path(__file__).resolve().parent.parent

    @property
    def AssetsDir(self) -> Path:
        return self.BaseDir / "Assets"


SettingMangerInstance = SettingsManager(config_path=Path("config.ini"))
