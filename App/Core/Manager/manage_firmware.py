# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/5/3
#  @FileName: manage_firmware.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------
import pathlib
from pathlib import Path

from Config.config import _dirPaths as DirPaths, SettingMangerInstance as SMI  # NOQA

class FirmwareManager:
    def __init__(self):
        pass

    def _ensureFirmwareDir(self, *parts: str) -> Path:
        """根据基础目录创建并返回固件目录。"""
        firmwareDir = DirPaths.BaseDir.joinpath("Firmware", *parts)
        firmwareDir.mkdir(parents=True, exist_ok=True)
        return firmwareDir

    def GetUpperFirmware(self) -> list[Path]:
        """
        return: 上位机固件目录的Path对象
        """
        pass
    def GetLowerFirmware(self) -> list[Path]:
        """
        return: 下位机电源板固件Path
        """
        pass
