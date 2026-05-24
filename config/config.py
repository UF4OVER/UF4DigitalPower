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
from __future__ import annotations

import logging
import sys
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Any, Union

from PyQt5.QtCore import QSettings
from qfluentwidgets import ConfigItem, BoolValidator, QConfig, qconfig


# ============================================================================
#  Private helpers
# ============================================================================

def _detect_base_dir() -> Path:
    """Return the project root, respecting frozen (cx_Freeze) layouts."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


# ============================================================================
#  DirPaths — path resolver
# ============================================================================

class DirPaths:
    """Resolves and ensures existence of canonical application directories.

    Uses *cached_property* so each directory is created on first access.
    """

    def __init__(self, base_dir: Path | None = None):
        self._base = base_dir if base_dir is not None else _detect_base_dir()

    @property
    def base_dir(self) -> Path:
        return self._base

    @property
    def BaseDir(self) -> Path:
        """Backward-compatible alias for base_dir."""
        return self._base

    def _ensure_dir(self, *parts: str) -> Path:
        directory = self._base.joinpath(*parts)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _ensure_sub_dir(self, parent: Path, *parts: str) -> Path:
        directory = parent.joinpath(*parts)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    # ---- public cached properties ----

    @cached_property
    def ResourcesDir(self) -> Path:
        return self._ensure_dir("Resources")

    @cached_property
    def AssetsDir(self) -> Path:
        return self._ensure_sub_dir(self.ResourcesDir, "Assets")

    @cached_property
    def ConfigDir(self) -> Path:
        return self._ensure_sub_dir(self.ResourcesDir, "config")

    @cached_property
    def ThemeDir(self) -> Path:
        return self._ensure_sub_dir(self.ResourcesDir, "Theme")

    @cached_property
    def FontDir(self) -> Path:
        return self._ensure_sub_dir(self.ResourcesDir, "Font")

    @cached_property
    def LogDir(self) -> Path:
        return self._ensure_dir("Logs")

    @cached_property
    def ToolsDir(self) -> Path:
        return self._ensure_sub_dir(self.ResourcesDir, "Tools")

    @cached_property
    def FirmwareDir(self) -> Path:
        return self._ensure_sub_dir(self.ResourcesDir, "Firmware")

    @cached_property
    def McuPackDir(self) -> Path:
        return self._ensure_sub_dir(self.ToolsDir, "Pack")

    @cached_property
    def FirmwarePowerDir(self) -> Path:
        return self._ensure_sub_dir(self.FirmwareDir, "Power")

    @cached_property
    def FirmwarePower(self) -> Path:
        return self.FirmwarePowerDir

    @cached_property
    def FirmwareUpperDir(self) -> Path:
        return self._ensure_sub_dir(self.FirmwareDir, "Upper")

    @cached_property
    def FirmwareUpper(self) -> Path:
        return self.FirmwareUpperDir

    @cached_property
    def AppIconPath(self) -> str:
        return str(self.AssetsDir / "F4CP_ICO_256.ico")

    @cached_property
    def ConfigIniPath(self) -> Path:
        return self.ConfigDir / "config.ini"

    @cached_property
    def ConfigJsonPath(self) -> Path:
        return self.ConfigDir / "config.json"


# ============================================================================
#  Logger factory
# ============================================================================

_logger_initialized: bool = False
logger = logging.getLogger("F4CP")
logger.setLevel(logging.DEBUG)


def _init_logger_once(log_dir: Path):
    global _logger_initialized
    if _logger_initialized:
        return
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    log_path = log_dir / f"{timestamp}.log"

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    if not logger.hasHandlers():
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    _logger_initialized = True


# ============================================================================
#  SettingsManager
# ============================================================================

class SettingsManager:
    """Thin wrapper around QSettings with typed get/set."""

    def __init__(self, config_path: Path):
        self._config_path = str(config_path.resolve())
        self._settings = QSettings(self._config_path, QSettings.Format.IniFormat)

    @property
    def config_path(self) -> str:
        return self._config_path

    def get(self, section: str, option: str, fallback: Any = None) -> Any:
        key = f"{section}/{option}"
        if self._settings.contains(key):
            value = self._settings.value(key)
            if isinstance(fallback, bool):
                return value.lower() == "true" if isinstance(value, str) else bool(value)
            if isinstance(fallback, int):
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return fallback
            return value
        return fallback

    def set(self, section: str, option: str, value: Any):
        key = f"{section}/{option}"
        logger.info(f"SettingsManager: {key} = {value}")
        self._settings.setValue(key, value)
        self._settings.sync()

    def contains(self, section: str, option: str) -> bool:
        key = f"{section}/{option}"
        return self._settings.contains(key)


# ============================================================================
#  F4CP QConfig (qfluentwidgets)
# ============================================================================


def _is_win11() -> bool:
    return sys.platform == "win32" and sys.getwindowsversion().build >= 22000


class F4CPConfig(QConfig):
    micaEnabled = ConfigItem("MainWindow", "MicaEnabled", _is_win11(), BoolValidator())
    checkUpdateAtStartUp = ConfigItem("Update", "CheckUpdateAtStartUp", True, BoolValidator())
    enableAcrylicBackground = ConfigItem("MainWindow", "EnableAcrylicBackground", False, BoolValidator())


# ============================================================================
#  AppContext — injectable dependency container
# ============================================================================

class AppContext:
    """Injectable application context replacing global singletons.

    Usage::

        # Production — context built from the real filesystem
        ctx = AppContext()

        # Testing — inject a temporary directory
        ctx = AppContext(base_dir=tmp_path)

        # Access
        ctx.dirs.FontDir
        ctx.settings.get("section", "key")
        ctx.qcfg.themeMode.value
    """

    def __init__(self, *, base_dir: Path | None = None):
        self._dirs = DirPaths(base_dir)
        _init_logger_once(self._dirs.LogDir)

        self._settings = SettingsManager(self._dirs.ConfigIniPath)
        self._qconfig = F4CPConfig()

        json_path = self._dirs.ConfigJsonPath
        if json_path.exists():
            qconfig.load(str(json_path), self._qconfig)

    # ---- properties ----

    @property
    def dirs(self) -> DirPaths:
        """Path resolver for canonical directories."""
        return self._dirs

    @property
    def settings(self) -> SettingsManager:
        """Typed QSettings wrapper."""
        return self._settings

    @property
    def qcfg(self) -> F4CPConfig:
        """qfluentwidgets application config."""
        return self._qconfig

    @property
    def app_icon_path(self) -> str:
        return self._dirs.AppIconPath

    # ---- lifecycle ----

    def reload(self):
        """Reload QConfig from disk (e.g. after external changes)."""
        json_path = self._dirs.ConfigJsonPath
        if json_path.exists():
            qconfig.load(str(json_path), self._qconfig)


# ============================================================================
#  Default context
# ============================================================================

_default_ctx: AppContext | None = None

def get_default_context() -> AppContext:
    """Return the singleton default AppContext, creating it on first call."""
    global _default_ctx
    if _default_ctx is None:
        _default_ctx = AppContext()
    return _default_ctx


def set_app_context(ctx: AppContext):
    """Override the default context (intended for testing)."""
    global _default_ctx
    _default_ctx = ctx


def reset_app_context():
    """Reset the default context to None so the next call rebuilds it."""
    global _default_ctx
    _default_ctx = None


# ============================================================================
#  CTX — module-level singleton, the one thing you need to import
# ============================================================================

CTX: AppContext = get_default_context()

# CTX: AppContext  = AppContext(base_dir=Path(__file__).resolve().parent.parent / ".config")
# Convenience shortcuts derived from CTX
cfg         = CTX.qcfg          # F4CPConfig (qfluentwidgets)
AppIconPath = CTX.app_icon_path  # str — path to app icon


# ============================================================================
#  Application constants (stateless — no DI needed)
# ============================================================================


VERSION_LOCAL_SECTION = "OldVersion"
VERSION_REMOTE_SECTION = "NewVersion"
UPDATE_SECTION = "update"
FIRMWARE_REMOTE_SECTION = "FirmwareRemote"

LOCAL_APP_VERSION_OPTION = "OldLocalVersion"
LOCAL_UPPER_VERSION_OPTION = "OldUpperVersion"
LOCAL_LOWER_VERSION_OPTION = "OldLowerVersion"

LATEST_APP_VERSION_OPTION = "NewLocalVersion"
LATEST_UPPER_VERSION_OPTION = "NewUpperVersion"
LATEST_LOWER_VERSION_OPTION = "NewLowerVersion"

UPDATE_URL_OPTION = "UpdateUrl"
FIRMWARE_GITHUB_OWNER_OPTION = "GithubOwner"
FIRMWARE_GITHUB_REPO_OPTION = "GithubRepo"
FIRMWARE_BASE_URL_OPTION = "BaseUrl"  # FastAPI firmware update server base URL

YEAR = 2026
AUTHOR = "UF4OVER"
VERSION = "1.4.0423"
HELP_URL = "https://hepi.ng/docs/help"
REPO_URL = "https://github.com/UF4OVER/UF4DigitalPower"
EXAMPLE_URL = "https://github.com/UF4OVER/UF4DigitalPower"
FEEDBACK_URL = "https://github.com/UF4OVER/UF4DigitalPower/issues"
RELEASE_URL = "https://github.com/UF4OVER/UF4DigitalPower/releases/latest"
ZH_SUPPORT_URL = "https://github.com/UF4OVER/UF4DigitalPower"
EN_SUPPORT_URL = "https://github.com/UF4OVER/UF4DigitalPower"
