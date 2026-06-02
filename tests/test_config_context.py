# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_config_context.py
#  @FileType: 自动化测试文件，用来守住关键功能行为
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

"""Tests for AppContext dependency injection and backward compatibility."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from config.config import (
    AppContext,
    CTX,
    DirPaths,
    get_default_context,
    reset_app_context,
    set_app_context,
)
from qfluentwidgets import Theme, qconfig


def _restore_global_qconfig():
    qconfig.load(str(CTX.dirs.ConfigJsonPath), CTX.cfg)


class DirPathsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="f4cp_test_"))

    def tearDown(self):
        import shutil
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_default_base_dir(self):
        """DirPaths should resolve base_dir to project root."""
        dp = DirPaths()
        self.assertTrue(dp.base_dir.exists())
        self.assertTrue((dp.base_dir / "config").exists())

    def test_custom_base_dir_injection(self):
        """DI: inject custom base_dir for test isolation."""
        dp = DirPaths(base_dir=self.tmp)
        self.assertEqual(dp.base_dir, self.tmp)

    def test_lazy_directory_creation(self):
        """Directories are created on first property access."""
        dp = DirPaths(base_dir=self.tmp)
        self.assertFalse((self.tmp / "Logs").exists())

        log_dir = dp.LogDir
        self.assertTrue((self.tmp / "Logs").exists())
        self.assertEqual(log_dir, self.tmp / "Logs")

    def test_resources_sub_dirs(self):
        """Resource subdirectories chain correctly."""
        dp = DirPaths(base_dir=self.tmp)
        self.assertEqual(dp.ResourcesDir, self.tmp / "Resources")
        self.assertEqual(dp.ThemeDir, self.tmp / "Resources" / "Theme")
        self.assertEqual(dp.FontDir, self.tmp / "Resources" / "Font")
        self.assertEqual(dp.FirmwareDir, self.tmp / "Resources" / "Firmware")

    def test_backward_compat_base_dir_alias(self):
        """BaseDir is an alias for base_dir."""
        dp = DirPaths(base_dir=self.tmp)
        self.assertEqual(dp.BaseDir, dp.base_dir)
        self.assertEqual(dp.BaseDir, self.tmp)

    def test_app_icon_path(self):
        """AppIconPath points to the ico under Assets."""
        dp = DirPaths(base_dir=self.tmp)
        expected = str(self.tmp / "Resources" / "Assets" / "F4CP_ICO_256.ico")
        self.assertEqual(dp.AppIconPath, expected)

    def test_config_paths(self):
        """ConfigJsonPath resolves correctly."""
        dp = DirPaths(base_dir=self.tmp)
        self.assertEqual(dp.ConfigJsonPath, self.tmp / "Resources" / "config" / "config.json")


class AppContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="f4cp_test_"))
        reset_app_context()

    def tearDown(self):
        import shutil
        reset_app_context()
        _restore_global_qconfig()
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_creates_directories(self):
        """AppContext initializes DirPaths, logger, and JSON config."""
        ctx = AppContext(base_dir=self.tmp)
        self.assertIsInstance(ctx.dirs, DirPaths)
        self.assertTrue((self.tmp / "Logs").exists())
        self.assertTrue((self.tmp / "Resources" / "config").exists())

    def test_cfg_loaded(self):
        """AppContext.cfg is an F4CPConfig instance."""
        ctx = AppContext(base_dir=self.tmp)
        from config.config import F4CPConfig
        self.assertIsInstance(ctx.cfg, F4CPConfig)

    def test_theme_items_are_qfluentwidgets_items(self):
        """Theme switching uses qfluentwidgets' global config items."""
        ctx = AppContext(base_dir=self.tmp)
        self.assertIs(ctx.cfg.themeMode, qconfig.themeMode)
        self.assertIs(ctx.cfg.themeColor, qconfig.themeColor)
        self.assertIs(ctx.cfg.fontFamilies, qconfig.fontFamilies)

    def test_app_icon_path(self):
        """app_icon_path delegates to DirPaths."""
        ctx = AppContext(base_dir=self.tmp)
        expected = str(self.tmp / "Resources" / "Assets" / "F4CP_ICO_256.ico")
        self.assertEqual(ctx.app_icon_path, expected)

    def test_reload_does_not_crash(self):
        """reload() should not raise even without config.json."""
        ctx = AppContext(base_dir=self.tmp)
        try:
            ctx.reload()
        except Exception as exc:
            self.fail(f"reload() raised {exc}")

    def test_default_context_singleton(self):
        """get_default_context returns same instance on repeated calls."""
        ctx1 = get_default_context()
        ctx2 = get_default_context()
        self.assertIs(ctx1, ctx2)
        reset_app_context()

    def test_set_app_context_override(self):
        """set_app_context replaces the default context."""
        ctx1 = AppContext(base_dir=self.tmp)
        set_app_context(ctx1)
        ctx2 = get_default_context()
        self.assertIs(ctx1, ctx2)

    def test_reset_app_context(self):
        """reset_app_context clears the cached default."""
        ctx1 = AppContext(base_dir=self.tmp)
        set_app_context(ctx1)
        reset_app_context()
        ctx2 = get_default_context()
        self.assertIsNot(ctx1, ctx2)


class ConfigExportTests(unittest.TestCase):
    def test_cfg_proxy(self):
        from config import cfg
        from config.config import F4CPConfig
        self.assertIsInstance(cfg, F4CPConfig)

    def test_app_icon_path_proxy(self):
        from config import AppIconPath
        self.assertIsInstance(AppIconPath, str)
        self.assertTrue(AppIconPath.endswith(".ico"))

class ManagerFontInjectTests(unittest.TestCase):
    """Verify manager_font functions accept optional ctx."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="f4cp_test_"))
        self.ctx = AppContext(base_dir=self.tmp)
        # Create a minimal font in FontDir
        self.ctx.dirs.FontDir  # ensure dir exists

    def tearDown(self):
        import shutil
        _restore_global_qconfig()
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_discover_font_options_with_ctx(self):
        from app.manager import discover_font_options
        options = discover_font_options(ctx=self.ctx)
        self.assertGreaterEqual(len(options), 1)
        self.assertEqual(options[0].key, "__system__")

    def test_get_saved_font_key_with_ctx(self):
        from app.manager import get_saved_font_key
        key = get_saved_font_key(ctx=self.ctx)
        self.assertIsInstance(key, str)
        self.assertTrue(len(key) > 0)

    def test_discover_font_options_without_ctx(self):
        from app.manager import discover_font_options
        options = discover_font_options()
        self.assertGreaterEqual(len(options), 1)


class StyleSheetPathTests(unittest.TestCase):
    """Verify StyleSheet.path() uses the global CTX directories."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="f4cp_test_"))
        self.dirs = DirPaths(base_dir=self.tmp)
        self.dirs.ThemeDir  # ensure directory exists

    def tearDown(self):
        import shutil
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_injected_dirs_used_in_path(self):
        from app.manager import StyleSheet
        p = StyleSheet.HOME_PAGE.path(Theme.LIGHT)
        expected = str(CTX.dirs.ThemeDir / "qss" / "light" / "HomePage.qss")
        self.assertEqual(p, expected)


class DaplinkSessionInjectTests(unittest.TestCase):
    """Verify DaplinkPyocdSession.set_dirs() injection."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="f4cp_test_"))
        self.dirs = DirPaths(base_dir=self.tmp)
        self.dirs.McuPackDir  # ensure directory exists
        self.dirs.base_dir  # ensure directory exists

    def tearDown(self):
        import shutil
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_injected_dirs_resolve(self):
        from app.session.session_daplink import DaplinkPyocdSession
        DaplinkPyocdSession.set_dirs(self.dirs)
        try:
            resolved = DaplinkPyocdSession._resolve_dirs()
            self.assertEqual(resolved.base_dir, self.tmp)
            self.assertEqual(resolved.McuPackDir, self.tmp / "Resources" / "Tools" / "Pack")
        finally:
            DaplinkPyocdSession.set_dirs(None)

    def test_pack_dir_uses_injected_dirs(self):
        from app.session.session_daplink import DaplinkPyocdSession
        DaplinkPyocdSession.set_dirs(self.dirs)
        try:
            pd = DaplinkPyocdSession.pack_dir()
            self.assertEqual(pd, self.tmp / "Resources" / "Tools" / "Pack")
        finally:
            DaplinkPyocdSession.set_dirs(None)


if __name__ == "__main__":
    unittest.main()
