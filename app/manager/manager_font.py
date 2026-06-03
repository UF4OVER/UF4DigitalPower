# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: manager_font.py
#  @FileType: 字体管理文件，负责字体发现、保存和应用
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from qfluentwidgets import qconfig

from config import CTX, cfg, logger

if TYPE_CHECKING:
    from config import AppContext

FONT_SECTION = "Appearance"
FONT_FILE_OPTION = "FontFile"
FONT_FAMILY_OPTION = "FontFamily"
SYSTEM_FONT_KEY = "__system__"
FONT_EXTENSIONS = {".ttf", ".otf", ".ttc", ".otc"}
FALLBACK_FONT_FAMILIES = ["Segoe UI", "Microsoft YaHei", "PingFang SC"]
_FONT_OPTION_CACHE: list[FontOption] | None = None
_FONT_FAMILY_CACHE: dict[Path, list[str]] = {}


@dataclass(frozen=True)
class FontOption:
    key: str
    label: str
    family: str
    file_name: str | None = None


def _resolve_dirs(ctx: "AppContext | None" = None):
    """Resolve DirPaths from context or fall back to CTX."""
    return ctx.dirs if ctx is not None else CTX.dirs


def _resolve_qcfg(ctx: "AppContext | None" = None):
    """Resolve QConfig from context or fall back to module-level cfg."""
    return ctx.cfg if ctx is not None else cfg


def _iter_font_files(ctx: AppContext | None = None):
    dirs = _resolve_dirs(ctx)
    for path in sorted(dirs.FontDir.iterdir(), key=lambda item: item.name.lower()):
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


def discover_font_options(ctx: AppContext | None = None) -> list[FontOption]:
    global _FONT_OPTION_CACHE
    if _FONT_OPTION_CACHE is not None:
        return list(_FONT_OPTION_CACHE)

    dirs = _resolve_dirs(ctx)
    options = [FontOption(SYSTEM_FONT_KEY, "System Default", "")]

    for path in _iter_font_files(ctx):
        families = _load_font_file(path)
        family = families[0] if families else path.stem
        label = f"{family} ({path.name})"

        options.append(FontOption(path.name, label, family, path.name))

    _FONT_OPTION_CACHE = list(options)
    return list(options)


def get_saved_font_key(ctx: AppContext | None = None) -> str:
    default_key = SYSTEM_FONT_KEY
    qcfg_obj = _resolve_qcfg(ctx)
    configured_key = getattr(getattr(qcfg_obj, "fontFile", None), "value", default_key) or default_key
    return configured_key


def save_font_selection(option: FontOption, ctx: AppContext | None = None):
    qcfg_obj = _resolve_qcfg(ctx)
    qconfig.set(qcfg_obj.fontFile, option.key)
    qconfig.set(qcfg_obj.fontFamily, option.family)


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


def loadSavedFont(app: QApplication, ctx: AppContext | None = None) -> list[str]:
    dirs = _resolve_dirs(ctx)
    qcfg_obj = _resolve_qcfg(ctx)

    selected_key = get_saved_font_key(ctx)
    if selected_key == SYSTEM_FONT_KEY:
        return apply_font_option(app, _system_font_option())

    font_path = dirs.FontDir / selected_key
    if not font_path.exists():
        logger.warning(f"Saved font file does not exist: {font_path}")
        return apply_font_option(app, _system_font_option())

    families = _load_font_file(font_path)
    if not families:
        return apply_font_option(app, _system_font_option())

    saved_family = getattr(getattr(qcfg_obj, "fontFamily", None), "value", "") or ""
    if not saved_family:
        saved_family = families[0]
        qconfig.set(qcfg_obj.fontFamily, saved_family)
    primary_family = saved_family if saved_family in families else families[0]
    return apply_font_option(app, FontOption(selected_key, primary_family, primary_family, selected_key))
