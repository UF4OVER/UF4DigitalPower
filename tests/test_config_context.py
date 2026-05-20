# -*- coding: utf-8 -*-
"""Tests for AppContext dependency injection and backward compatibility."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from Config.config import (
    AppContext,
    DirPaths,
    SettingsManager,
    get_default_context,
    reset_app_context,
    set_app_context,
)


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
        self.assertTrue((dp.base_dir / "Config").exists())

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
        """ConfigIniPath and ConfigJsonPath resolve correctly."""
        dp = DirPaths(base_dir=self.tmp)
        self.assertEqual(dp.ConfigIniPath, self.tmp / "Resources" / "Config" / "config.ini")
        self.assertEqual(dp.ConfigJsonPath, self.tmp / "Resources" / "Config" / "config.json")


class SettingsManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="f4cp_test_"))
        self.config_path = self.tmp / "test.ini"
        self.sm = SettingsManager(self.config_path)

    def tearDown(self):
        import shutil
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_get_fallback(self):
        """Missing key returns fallback."""
        self.assertEqual(self.sm.get("NoSection", "NoKey", "default"), "default")
        self.assertEqual(self.sm.get("S", "K", 42), 42)
        self.assertEqual(self.sm.get("S", "K", True), True)

    def test_set_and_get(self):
        """Set then get returns the stored value."""
        self.sm.set("Test", "name", "hello")
        self.assertEqual(self.sm.get("Test", "name"), "hello")

    def test_contains(self):
        """contains returns True after set."""
        self.assertFalse(self.sm.contains("Test", "flag"))
        self.sm.set("Test", "flag", "1")
        self.assertTrue(self.sm.contains("Test", "flag"))

    def test_int_type_coercion(self):
        """get returns int when fallback is int."""
        self.sm.set("Numbers", "count", 99)
        self.assertIsInstance(self.sm.get("Numbers", "count", 0), int)
        self.assertEqual(self.sm.get("Numbers", "count", 0), 99)

    def test_bool_type_coercion(self):
        """get returns bool when fallback is bool."""
        self.sm.set("Flags", "enabled", "true")
        self.assertIs(self.sm.get("Flags", "enabled", False), True)


class AppContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="f4cp_test_"))
        reset_app_context()

    def tearDown(self):
        import shutil
        reset_app_context()
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_creates_directories(self):
        """AppContext initializes DirPaths, logger, and settings manager."""
        ctx = AppContext(base_dir=self.tmp)
        self.assertIsInstance(ctx.dirs, DirPaths)
        self.assertIsInstance(ctx.settings, SettingsManager)
        self.assertTrue((self.tmp / "Logs").exists())
        self.assertTrue((self.tmp / "Resources" / "Config").exists())

    def test_qcfg_loaded(self):
        """AppContext.qcfg is an F4CPConfig instance."""
        ctx = AppContext(base_dir=self.tmp)
        from Config.config import F4CPConfig
        self.assertIsInstance(ctx.qcfg, F4CPConfig)

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


class BackwardCompatTests(unittest.TestCase):
    """Verify legacy `from Config import X` names still resolve correctly.

    These names are eagerly initialized at import time from the real project
    root.  ``set_app_context()`` does NOT retroactively update them (by design:
    they exist for backward compatibility; new code should use ``AppContext``).
    """

    def test_dir_paths_instance_proxy(self):
        from Config import DirPathsInstance
        self.assertIsInstance(DirPathsInstance, DirPaths)
        self.assertTrue(DirPathsInstance.base_dir.exists())

    def test_setting_manager_instance_proxy(self):
        from Config import SettingMangerInstance
        self.assertIsInstance(SettingMangerInstance, SettingsManager)
        self.assertTrue(SettingMangerInstance.config_path.endswith("config.ini"))

    def test_cfg_proxy(self):
        from Config import cfg
        from Config.config import F4CPConfig
        self.assertIsInstance(cfg, F4CPConfig)

    def test_app_icon_path_proxy(self):
        from Config import AppIconPath
        self.assertIsInstance(AppIconPath, str)
        self.assertTrue(AppIconPath.endswith(".ico"))

    def test_app_config_path_proxy(self):
        from Config import APP_CONFIG_PATH
        self.assertIsInstance(APP_CONFIG_PATH, Path)
        self.assertEqual(APP_CONFIG_PATH.name, "config.ini")


class ManagerFontInjectTests(unittest.TestCase):
    """Verify manager_font functions accept optional ctx."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="f4cp_test_"))
        self.ctx = AppContext(base_dir=self.tmp)
        # Create a minimal font in FontDir
        self.ctx.dirs.FontDir  # ensure dir exists

    def tearDown(self):
        import shutil
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_discover_font_options_with_ctx(self):
        from App.Core.Manager.manager_font import discover_font_options
        options = discover_font_options(ctx=self.ctx)
        self.assertGreaterEqual(len(options), 1)
        self.assertEqual(options[0].key, "__system__")

    def test_get_saved_font_key_with_ctx(self):
        from App.Core.Manager.manager_font import get_saved_font_key
        key = get_saved_font_key(ctx=self.ctx)
        self.assertIsInstance(key, str)
        self.assertTrue(len(key) > 0)

    def test_discover_font_options_without_ctx(self):
        """Backward compat: calling without ctx still works."""
        from App.Core.Manager.manager_font import discover_font_options
        options = discover_font_options()
        self.assertGreaterEqual(len(options), 1)


class StyleSheetInjectTests(unittest.TestCase):
    """Verify StyleSheet.set_dirs() injection."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="f4cp_test_"))
        self.dirs = DirPaths(base_dir=self.tmp)
        self.dirs.ThemeDir  # ensure directory exists

    def tearDown(self):
        import shutil
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_injected_dirs_used_in_path(self):
        from App.Core.Manager.manager_stylesheet import StyleSheet
        StyleSheet.set_dirs(self.dirs)
        try:
            p = StyleSheet.HOME_PAGE.path()
            self.assertIn(str(self.tmp), p)
        finally:
            StyleSheet.set_dirs(None)


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
        from App.Core.Session.session_daplink import DaplinkPyocdSession
        DaplinkPyocdSession.set_dirs(self.dirs)
        try:
            resolved = DaplinkPyocdSession._resolve_dirs()
            self.assertEqual(resolved.base_dir, self.tmp)
            self.assertEqual(resolved.McuPackDir, self.tmp / "Resources" / "Tools" / "Pack")
        finally:
            DaplinkPyocdSession.set_dirs(None)

    def test_pack_dir_uses_injected_dirs(self):
        from App.Core.Session.session_daplink import DaplinkPyocdSession
        DaplinkPyocdSession.set_dirs(self.dirs)
        try:
            pd = DaplinkPyocdSession.pack_dir()
            self.assertEqual(pd, self.tmp / "Resources" / "Tools" / "Pack")
        finally:
            DaplinkPyocdSession.set_dirs(None)


if __name__ == "__main__":
    unittest.main()
