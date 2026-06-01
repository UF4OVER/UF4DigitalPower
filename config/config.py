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
import os
import shutil
import sys
from datetime import datetime
from functools import cached_property
from pathlib import Path
from PyQt5.QtCore import pyqtSignal
from qfluentwidgets import (
    BoolValidator,
    ConfigItem,
    QConfig,
    qconfig,
)


# ============================================================================
#  Private helpers
# ============================================================================

def _detect_base_dir() -> Path:
    """Return the project root, respecting frozen (cx_Freeze) layouts."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _detect_data_dir(base_dir: Path, explicit_base_dir: bool) -> Path:
    """Return the writable per-user data directory for installed apps."""
    if explicit_base_dir:
        return base_dir
    if getattr(sys, "frozen", False):
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "F4CP"
        return Path.home() / "AppData" / "Local" / "F4CP"
    return base_dir


# ============================================================================
#  DirPaths — path resolver
# ============================================================================

class DirPaths:
    """Resolves and ensures existence of canonical application directories.

    Uses *cached_property* so each directory is created on first access.
    """

    def __init__(self, base_dir: Path | None = None, data_dir: Path | None = None):
        explicit_base_dir = base_dir is not None
        self._base = base_dir if base_dir is not None else _detect_base_dir()
        self._data = data_dir if data_dir is not None else _detect_data_dir(self._base, explicit_base_dir)

    @property
    def base_dir(self) -> Path:
        return self._base

    @property
    def BaseDir(self) -> Path:
        """Backward-compatible alias for base_dir."""
        return self._base

    @property
    def data_dir(self) -> Path:
        return self._data

    def _ensure_dir(self, *parts: str) -> Path:
        directory = self._base.joinpath(*parts)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _ensure_data_dir(self, *parts: str) -> Path:
        directory = self._data.joinpath(*parts)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _ensure_sub_dir(self, parent: Path, *parts: str) -> Path:
        directory = parent.joinpath(*parts)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _copy_seed_dir(self, source: Path, target: Path) -> None:
        if not source.exists():
            return
        for item in source.rglob("*"):
            relative = item.relative_to(source)
            destination = target / relative
            if item.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            elif not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, destination)

    # ---- public cached properties ----

    @cached_property
    def ResourcesDir(self) -> Path:
        directory = self._base / "Resources"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @cached_property
    def UserResourcesDir(self) -> Path:
        return self._ensure_data_dir("Resources")

    @cached_property
    def AssetsDir(self) -> Path:
        return self._ensure_sub_dir(self.ResourcesDir, "Assets")

    @cached_property
    def ConfigDir(self) -> Path:
        config_dir = self._ensure_sub_dir(self.UserResourcesDir, "config")
        bundled_config_dir = self.ResourcesDir / "config"
        self._copy_seed_dir(bundled_config_dir, config_dir)
        return config_dir

    @cached_property
    def ThemeDir(self) -> Path:
        return self._ensure_sub_dir(self.ResourcesDir, "Theme")

    @cached_property
    def FontDir(self) -> Path:
        return self._ensure_sub_dir(self.ResourcesDir, "Font")

    @cached_property
    def LogDir(self) -> Path:
        return self._ensure_data_dir("Logs")

    @cached_property
    def ToolsDir(self) -> Path:
        return self._ensure_sub_dir(self.ResourcesDir, "Tools")

    @cached_property
    def FirmwareDir(self) -> Path:
        firmware_dir = self._ensure_sub_dir(self.UserResourcesDir, "Firmware")
        bundled_firmware_dir = self.ResourcesDir / "Firmware"
        self._copy_seed_dir(bundled_firmware_dir, firmware_dir)
        return firmware_dir

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
#  F4CP QConfig (qfluentwidgets)
# ============================================================================


def _is_win11() -> bool:
    return sys.platform == "win32" and sys.getwindowsversion().build >= 22000


class F4CPConfig(QConfig):
    micaEnabled = ConfigItem("MainWindow", "MicaEnabled", _is_win11(), BoolValidator())
    enableAcrylicBackground = ConfigItem("MainWindow", "EnableAcrylicBackground", False, BoolValidator())
    highDpiScaling = ConfigItem("MainWindow", "HighDpiScaling", True, BoolValidator(), restart=True)

    checkUpdateAtStartUp = ConfigItem("Update", "CheckUpdateAtStartUp", True, BoolValidator())
    updateUrl = ConfigItem("Update", "UpdateUrl", "https://github.com/UF4OVER/UF4DigitalPower/releases")

    firmwareBaseUrl = ConfigItem("FirmwareRemote", "BaseUrl", "")
    firmwareGithubOwner = ConfigItem("FirmwareRemote", "GithubOwner", "UF4OVER")
    firmwareGithubRepo = ConfigItem("FirmwareRemote", "GithubRepo", "UF4DigitalPower")

    localAppVersion = ConfigItem("OldVersion", "OldLocalVersion", "")
    localUpperVersion = ConfigItem("OldVersion", "OldUpperVersion", "")
    localLowerVersion = ConfigItem("OldVersion", "OldLowerVersion", "")
    latestAppVersion = ConfigItem("NewVersion", "NewLocalVersion", "v0.5.3")
    latestUpperVersion = ConfigItem("NewVersion", "NewUpperVersion", "v0.0.2")
    latestLowerVersion = ConfigItem("NewVersion", "NewLowerVersion", "v0.0.2")

    appYear = ConfigItem("Application", "Year", 2026)
    appAuthor = ConfigItem("Application", "Author", "UF4OVER")
    appVersion = ConfigItem("Application", "Version", "0.5.3.rc1")
    appHelpUrl = ConfigItem("Application", "HelpUrl", "https://update.hepi.ng/docs/help")
    appRepoUrl = ConfigItem("Application", "RepoUrl", "https://github.com/UF4OVER/UF4DigitalPower")
    appExampleUrl = ConfigItem("Application", "ExampleUrl", "https://github.com/UF4OVER/UF4DigitalPower")
    appFeedbackUrl = ConfigItem("Application", "FeedbackUrl", "https://github.com/UF4OVER/UF4DigitalPower/issues")
    appReleaseUrl = ConfigItem("Application", "ReleaseUrl", "https://github.com/UF4OVER/UF4DigitalPower/releases/latest")
    appZhSupportUrl = ConfigItem("Application", "ZhSupportUrl", "https://github.com/UF4OVER/UF4DigitalPower")
    appEnSupportUrl = ConfigItem("Application", "EnSupportUrl", "https://github.com/UF4OVER/UF4DigitalPower")

    fontFile = ConfigItem("Appearance", "FontFile", "__system__")
    fontFamily = ConfigItem("Appearance", "FontFamily", "")

    appRestartSig = pyqtSignal()


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
        ctx.cfg.themeMode.value
    """

    def __init__(self, *, base_dir: Path | None = None, data_dir: Path | None = None):
        self._dirs = DirPaths(base_dir, data_dir)
        _init_logger_once(self._dirs.LogDir)

        self._qconfig = F4CPConfig()

        json_path = self._dirs.ConfigJsonPath
        json_path.parent.mkdir(parents=True, exist_ok=True)
        if not json_path.exists():
            json_path.write_text("{}", encoding="utf-8")
        if json_path.exists():
            qconfig.load(str(json_path), self._qconfig)

    # ---- properties ----

    @property
    def dirs(self) -> DirPaths:
        """Path resolver for canonical directories."""
        return self._dirs

    @property
    def qcfg(self) -> F4CPConfig:
        """qfluentwidgets application config."""
        return self._qconfig

    @property
    def cfg(self) -> F4CPConfig:
        """JSON-backed application config."""
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


_default_context: AppContext | None = None


def get_default_context() -> AppContext:
    global _default_context
    if _default_context is None:
        _default_context = CTX
    return _default_context


def set_app_context(ctx: AppContext) -> None:
    global _default_context
    _default_context = ctx


def reset_app_context() -> None:
    global _default_context
    _default_context = None

# ============================================================================
#  CTX — module-level singleton, the one thing you need to import
# ============================================================================

CTX: AppContext = AppContext()

# CTX: AppContext  = AppContext(base_dir=Path(__file__).resolve().parent.parent / ".config")
# Convenience shortcuts derived from CTX
cfg         = CTX.cfg          # F4CPConfig (qfluentwidgets)
_config_json_path = CTX.dirs.ConfigDir / "config.json"
if not _config_json_path.exists():
    _config_json_path.parent.mkdir(parents=True, exist_ok=True)
    _config_json_path.write_text("{}", encoding="utf-8")

qconfig.load(_config_json_path, cfg)

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

YEAR = cfg.appYear.value
AUTHOR = cfg.appAuthor.value
VERSION = cfg.appVersion.value
HELP_URL = cfg.appHelpUrl.value
REPO_URL = cfg.appRepoUrl.value
EXAMPLE_URL = cfg.appExampleUrl.value
FEEDBACK_URL = cfg.appFeedbackUrl.value
RELEASE_URL = cfg.appReleaseUrl.value
ZH_SUPPORT_URL = cfg.appZhSupportUrl.value
EN_SUPPORT_URL = cfg.appEnSupportUrl.value
