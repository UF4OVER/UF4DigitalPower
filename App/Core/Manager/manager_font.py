# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import qconfig

from Config import DirPathsInstance, SettingMangerInstance, logger

FONT_SECTION = "Appearance"
FONT_FILE_OPTION = "FontFile"
FONT_FAMILY_OPTION = "FontFamily"
SYSTEM_FONT_KEY = "__system__"
FONT_EXTENSIONS = {".ttf", ".otf", ".ttc", ".otc"}
FALLBACK_FONT_FAMILIES = ["Segoe UI", "Microsoft YaHei", "PingFang SC"]
DEFAULT_FONT_FILE_NAME = "blender-pro-bold.otf"
_FONT_OPTION_CACHE: list[FontOption] | None = None
_FONT_FAMILY_CACHE: dict[Path, list[str]] = {}


@dataclass(frozen=True)
class FontOption:
    key: str
    label: str
    family: str
    file_name: str | None = None


def _iter_font_files():
    for path in sorted(DirPathsInstance.FontDir.iterdir(), key=lambda item: item.name.lower()):
        if path.is_file() and path.suffix.lower() in FONT_EXTENSIONS:
            yield path


def _load_font_file(path: Path) -> list[str]:
    cached = _FONT_FAMILY_CACHE.get(path)
    if cached is not None:
        return list(cached)

    font_id = QFontDatabase.addApplicationFont(str(path))
    if font_id == -1:
        logger.warning(f"Failed to load application font from {path}")
        _FONT_FAMILY_CACHE[path] = []
        return []

    families = QFontDatabase.applicationFontFamilies(font_id)
    if not families:
        logger.warning(f"No font families found in {path}")
        _FONT_FAMILY_CACHE[path] = []
        return []

    _FONT_FAMILY_CACHE[path] = list(families)
    return list(families)


def _merge_font_families(primary_family: str | None) -> list[str]:
    families = list(FALLBACK_FONT_FAMILIES)
    if primary_family:
        families = [primary_family] + [family for family in families if family != primary_family]
    return families


def discover_font_options() -> list[FontOption]:
    global _FONT_OPTION_CACHE
    if _FONT_OPTION_CACHE is not None:
        return list(_FONT_OPTION_CACHE)

    options = [FontOption(SYSTEM_FONT_KEY, "System Default", "")]

    for path in _iter_font_files():
        families = _load_font_file(path)
        family = families[0] if families else path.stem
        label = f"{family} ({path.name})"
        if path.name == DEFAULT_FONT_FILE_NAME:
            label = f"Built-in Default - {family}"
        options.append(FontOption(path.name, label, family, path.name))

    _FONT_OPTION_CACHE = list(options)
    return list(options)


def _default_font_key() -> str:
    default_font_path = DirPathsInstance.FontDir / DEFAULT_FONT_FILE_NAME
    return DEFAULT_FONT_FILE_NAME if default_font_path.exists() else SYSTEM_FONT_KEY


def get_saved_font_key() -> str:
    default_key = _default_font_key()
    return SettingMangerInstance.get(FONT_SECTION, FONT_FILE_OPTION, default_key) or default_key


def save_font_selection(option: FontOption):
    SettingMangerInstance.set(FONT_SECTION, FONT_FILE_OPTION, option.key)
    SettingMangerInstance.set(FONT_SECTION, FONT_FAMILY_OPTION, option.family)


def apply_font_option(app: QApplication, option: FontOption) -> list[str]:
    families = _merge_font_families(option.family)
    qconfig.set(qconfig.fontFamilies, families, save=False)

    app_font = app.font()
    app_font.setFamilies(families)
    app.setFont(app_font)

    logger.info(f"Application font family applied: {families}")
    return families


def _system_font_option() -> FontOption:
    return FontOption(SYSTEM_FONT_KEY, "System Default", "")


def loadSavedFont(app: QApplication) -> list[str]:
    selected_key = get_saved_font_key()
    if selected_key == SYSTEM_FONT_KEY:
        return apply_font_option(app, _system_font_option())

    font_path = DirPathsInstance.FontDir / selected_key
    if not font_path.exists():
        logger.warning(f"Saved font file does not exist: {font_path}")
        return apply_font_option(app, _system_font_option())

    families = _load_font_file(font_path)
    if not families:
        return apply_font_option(app, _system_font_option())

    saved_family = SettingMangerInstance.get(FONT_SECTION, FONT_FAMILY_OPTION, families[0]) or families[0]
    primary_family = saved_family if saved_family in families else families[0]
    return apply_font_option(app, FontOption(selected_key, primary_family, primary_family, selected_key))
