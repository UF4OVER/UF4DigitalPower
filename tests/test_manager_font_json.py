# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_manager_font_json.py
#  @FileType: 自动化测试文件，用来守住关键功能行为
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.manager.manager_font import (
    FontOption,
    get_saved_font_key,
    save_font_selection,
)
from config.config import AppContext, CTX
from qfluentwidgets import qconfig


def _restore_global_qconfig():
    qconfig.load(str(CTX.dirs.ConfigJsonPath), CTX.cfg)


class FontJsonPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="f4cp_font_json_"))
        self.ctx = AppContext(base_dir=self.tmp)
        qconfig.set(self.ctx.cfg.fontFile, "__system__", save=False)
        qconfig.set(self.ctx.cfg.fontFamily, "", save=False)

    def tearDown(self):
        import shutil

        _restore_global_qconfig()
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_save_font_selection_writes_json(self):
        save_font_selection(FontOption("demo.ttf", "Demo", "Demo", "demo.ttf"), ctx=self.ctx)

        data = json.loads(self.ctx.dirs.ConfigJsonPath.read_text(encoding="utf-8"))
        self.assertEqual(data["Appearance"]["FontFile"], "demo.ttf")
        self.assertEqual(data["Appearance"]["FontFamily"], "Demo")

    def test_get_saved_font_key_reads_json_config(self):
        qconfig.set(self.ctx.cfg.fontFile, "demo.ttf")
        qconfig.set(self.ctx.cfg.fontFamily, "Demo")

        key = get_saved_font_key(ctx=self.ctx)

        data = json.loads(self.ctx.dirs.ConfigJsonPath.read_text(encoding="utf-8"))
        self.assertEqual(key, "demo.ttf")
        self.assertEqual(data["Appearance"]["FontFile"], "demo.ttf")
        self.assertEqual(data["Appearance"]["FontFamily"], "Demo")


if __name__ == "__main__":
    unittest.main()

