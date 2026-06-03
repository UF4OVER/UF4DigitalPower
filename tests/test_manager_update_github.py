# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_manager_update_github.py
#  @FileType: 自动化测试文件，用来守住关键功能行为
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.manager.manager_update import UpdateManager


class _FakeResponse:
    def __init__(self, data: dict):
        self._payload = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._payload


class _FakeItem:
    def __init__(self, value):
        self.value = value


class _FakeCfg:
    def __init__(self):
        self.updateUrl = _FakeItem("https://github.com/UF4OVER/UF4DigitalPower/releases")
        self.appVersion = _FakeItem("v0.1.0")
        self.localAppVersion = _FakeItem("v0.1.0")
        self.latestAppVersion = _FakeItem("v0.1.0")
        self.localUpperVersion = _FakeItem("--")
        self.latestUpperVersion = _FakeItem("--")
        self.localLowerVersion = _FakeItem("--")
        self.latestLowerVersion = _FakeItem("--")


class UpdateManagerGithubTests(unittest.TestCase):
    def test_github_releases_url_returns_latest_tag_without_writing_cached_version(self):
        manager = UpdateManager()
        fake_cfg = _FakeCfg()
        release = {
            "tag_name": "v0.2.0",
            "html_url": "https://github.com/UF4OVER/UF4DigitalPower/releases/tag/v0.2.0",
            "body": "## 更新内容\n- 新增 Power 页面",
        }

        with patch("app.manager.manager_update.CTX", SimpleNamespace(cfg=fake_cfg)), patch(
            "app.manager.manager_update.firmware_manager.get_latest_local_release",
            return_value=None,
        ), patch("app.manager.manager_update.qconfig.set") as mocked_set, patch(
            "app.manager.manager_update.urlopen", return_value=_FakeResponse(release)
        ) as mocked_urlopen:
            result = manager._perform_check(manual=True)

        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://api.github.com/repos/UF4OVER/UF4DigitalPower/releases/latest",
        )
        self.assertTrue(result.success)
        self.assertTrue(result.has_changes)
        self.assertEqual(result.snapshot.latest_app_version, "v0.2.0")
        self.assertEqual(result.release_tag, "v0.2.0")
        self.assertIn("Power 页面", result.release_notes)
        self.assertEqual(result.release_url, release["html_url"])
        self.assertIn((fake_cfg.latestAppVersion, "v0.2.0"), [call.args for call in mocked_set.call_args_list])

    def test_same_version_with_v_prefix_does_not_report_update(self):
        manager = UpdateManager()
        fake_cfg = _FakeCfg()
        fake_cfg.appVersion.value = "0.5.3.rc2"
        release = {
            "tag_name": "v0.5.3.rc2",
            "html_url": "https://github.com/UF4OVER/UF4DigitalPower/releases/tag/v0.5.3.rc2",
            "body": "",
        }

        with patch("app.manager.manager_update.CTX", SimpleNamespace(cfg=fake_cfg)), patch(
            "app.manager.manager_update.firmware_manager.get_latest_local_release",
            return_value=None,
        ), patch("app.manager.manager_update.qconfig.set"), patch(
            "app.manager.manager_update.urlopen", return_value=_FakeResponse(release)
        ):
            result = manager._perform_check(manual=True)

        self.assertTrue(result.success)
        self.assertFalse(result.has_changes)
        self.assertEqual(result.snapshot.local_app_version, "0.5.3.rc2")
        self.assertEqual(result.snapshot.latest_app_version, "v0.5.3.rc2")

    def test_newer_rc_version_reports_update(self):
        manager = UpdateManager()
        fake_cfg = _FakeCfg()
        fake_cfg.appVersion.value = "v0.5.3.rc1"
        release = {
            "tag_name": "v0.5.3.rc2",
            "html_url": "https://github.com/UF4OVER/UF4DigitalPower/releases/tag/v0.5.3.rc2",
            "body": "",
        }

        with patch("app.manager.manager_update.CTX", SimpleNamespace(cfg=fake_cfg)), patch(
            "app.manager.manager_update.firmware_manager.get_latest_local_release",
            return_value=None,
        ), patch("app.manager.manager_update.qconfig.set"), patch(
            "app.manager.manager_update.urlopen", return_value=_FakeResponse(release)
        ):
            result = manager._perform_check(manual=True)

        self.assertTrue(result.success)
        self.assertTrue(result.has_changes)


if __name__ == "__main__":
    unittest.main()
