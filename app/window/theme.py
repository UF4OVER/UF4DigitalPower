# -*- coding: utf-8 -*-
from __future__ import annotations

from qfluentwidgets import isDarkTheme

from config import cfg


class ThemeBackgroundMixin:
    """Theme and Fluent background refresh coordination."""

    def initThemeBackground(self) -> None:
        self.setMicaEffectEnabled(bool(getattr(cfg.micaEnabled, "value", False)))
        self.refreshTheme()
        cfg.themeChanged.connect(self.refreshTheme)

    def refreshTheme(self, *_args) -> None:
        dark = isDarkTheme()
        if hasattr(self, "dynamicIsland"):
            self.dynamicIsland.setDarkTheme(dark)

        for widget in (self, self.navigationInterface, self.titleBar):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
