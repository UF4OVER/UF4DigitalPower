# -*- coding: utf-8 -*-

from __future__ import annotations

import configparser
import json
import socket
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.error import URLError
from urllib.request import Request, urlopen

from PyQt5.QtCore import QCoreApplication, QEvent, QObject, QThread, pyqtSignal

from config import (
	CTX,
	LATEST_APP_VERSION_OPTION,
	LATEST_LOWER_VERSION_OPTION,
	LATEST_UPPER_VERSION_OPTION,
	LOCAL_APP_VERSION_OPTION,
	LOCAL_LOWER_VERSION_OPTION,
	LOCAL_UPPER_VERSION_OPTION,
	UPDATE_SECTION,
	UPDATE_URL_OPTION,
	VERSION_LOCAL_SECTION,
	VERSION_REMOTE_SECTION,
logger,
)
from .manage_firmware import firmware_manager

UPDATE_FETCH_EXCEPTIONS = (URLError, TimeoutError, socket.timeout)


def _normalize_version(value: object, fallback: str = "--") -> str:
	text = str(value or "").strip()
	return text or fallback


@dataclass(frozen=True)
class FirmwareVersionSnapshot:
	local_app_version: str
	latest_app_version: str
	local_upper_version: str
	latest_upper_version: str
	local_lower_version: str
	latest_lower_version: str


@dataclass(frozen=True)
class UpdateCheckResult:
	success: bool
	manual: bool
	message: str
	snapshot: FirmwareVersionSnapshot
	has_changes: bool = False
	release_tag: str = ""
	release_url: str = ""
	release_notes: str = ""


class UpdateCheckFinishedEvent(QEvent):
	EVENT_TYPE = QEvent.Type(QEvent.registerEventType())

	def __init__(self, result: UpdateCheckResult):
		super().__init__(self.EVENT_TYPE)
		self.result = result


class UpdateCheckThread(QThread):
	resultReady = pyqtSignal(object)

	def __init__(self, manager: "UpdateManager", manual: bool, parent: QObject | None = None):
		super().__init__(parent)
		self.manager = manager
		self.manual = manual

	def run(self) -> None:
		try:
			result = self.manager._perform_check(self.manual)
		except Exception:
			logger.exception("Unexpected error during app update check")
			result = UpdateCheckResult(
				success=False,
				manual=self.manual,
				message="Failed to check updates.",
				snapshot=self.manager.get_cached_versions(),
			)
		self.resultReady.emit(result)


class UpdateManager:
	def __init__(self):
		self._worker: UpdateCheckThread | None = None

	@property
	def is_checking(self) -> bool:
		return bool(self._worker and self._worker.isRunning())

	def get_cached_versions(self) -> FirmwareVersionSnapshot:
		settings = CTX.settings
		local_upper = firmware_manager.get_latest_local_release("Upper")
		local_lower = firmware_manager.get_latest_local_release("Power")
		return FirmwareVersionSnapshot(
			local_app_version=_normalize_version(
				settings.get(VERSION_LOCAL_SECTION, LOCAL_APP_VERSION_OPTION, "--")
			),
			latest_app_version=_normalize_version(
				settings.get(VERSION_REMOTE_SECTION, LATEST_APP_VERSION_OPTION, "--")
			),
			local_upper_version=_normalize_version(
				local_upper.version if local_upper else settings.get(VERSION_LOCAL_SECTION, LOCAL_UPPER_VERSION_OPTION, "--")
			),
			latest_upper_version=_normalize_version(
				settings.get(VERSION_REMOTE_SECTION, LATEST_UPPER_VERSION_OPTION, "--")
			),
			local_lower_version=_normalize_version(
				local_lower.version if local_lower else settings.get(VERSION_LOCAL_SECTION, LOCAL_LOWER_VERSION_OPTION, "--")
			),
			latest_lower_version=_normalize_version(
				settings.get(VERSION_REMOTE_SECTION, LATEST_LOWER_VERSION_OPTION, "--")
			),
		)

	def check_for_updates(self, receiver: QObject, manual: bool = False) -> bool:
		if self.is_checking:
			logger.info("UpdateManager skipped app update check because another check is running")
			return False

		self._worker = UpdateCheckThread(self, manual)
		self._worker.resultReady.connect(lambda result, target=receiver: self._publish_result(target, result))
		self._worker.finished.connect(self._cleanup_worker)
		self._worker.start()
		return True

	def _publish_result(self, receiver: QObject, result: UpdateCheckResult) -> None:
		QCoreApplication.postEvent(receiver, UpdateCheckFinishedEvent(result))

	def _cleanup_worker(self) -> None:
		if self._worker is not None:
			self._worker.deleteLater()
			self._worker = None

	def _perform_check(self, manual: bool) -> UpdateCheckResult:
		snapshot_before = self.get_cached_versions()
		settings = CTX.settings
		update_url = str(settings.get(UPDATE_SECTION, UPDATE_URL_OPTION, "") or "").strip()

		if not update_url:
			logger.info("UpdateManager skipped app update check because UpdateUrl is empty")
			return UpdateCheckResult(
				success=False,
				manual=manual,
				message="app update URL is not configured.",
				snapshot=snapshot_before,
			)

		logger.info(f"UpdateManager fetching remote firmware version info from {update_url}")
		try:
			remote_result = self._fetch_remote_update(update_url)
		except UPDATE_FETCH_EXCEPTIONS as exc:
			logger.warning(f"UpdateManager failed to fetch update data: {exc}")
			return UpdateCheckResult(
				success=False,
				manual=manual,
				message="Failed to connect to the update server.",
				snapshot=snapshot_before,
			)

		latest_versions = remote_result.get("versions")
		if latest_versions is None:
			logger.warning("UpdateManager received an unsupported update payload")
			return UpdateCheckResult(
				success=False,
				manual=manual,
				message="The update server returned invalid version data.",
				snapshot=snapshot_before,
			)

		settings.set(VERSION_REMOTE_SECTION, LATEST_APP_VERSION_OPTION, latest_versions["app"])

		snapshot_after = self.get_cached_versions()
		has_changes = snapshot_before.latest_app_version != snapshot_after.latest_app_version
		logger.info(
			"UpdateManager refreshed latest app version: "
			f"app={snapshot_after.latest_app_version}"
		)
		return UpdateCheckResult(
			success=True,
			manual=manual,
			message="Latest app version has been refreshed.",
			snapshot=snapshot_after,
			has_changes=has_changes,
			release_tag=str(remote_result.get("release_tag") or latest_versions["app"]),
			release_url=str(remote_result.get("release_url") or update_url),
			release_notes=str(remote_result.get("release_notes") or ""),
		)

	def _fetch_remote_update(self, update_url: str) -> dict[str, object]:
		github_api_url = self._github_release_api_url(update_url)
		if github_api_url:
			return self._fetch_github_latest_release(github_api_url)

		request = Request(update_url, headers={"User-Agent": "F4CP-UpdateChecker"})
		with urlopen(request, timeout=8) as response:
			payload = response.read().decode("utf-8-sig")
		return {"versions": self._parse_remote_versions(payload)}

	def _fetch_github_latest_release(self, api_url: str) -> dict[str, object]:
		request = Request(
			api_url,
			headers={
				"Accept": "application/vnd.github+json",
				"User-Agent": "F4CP-UpdateChecker",
			},
		)
		with urlopen(request, timeout=8) as response:
			data = json.loads(response.read().decode("utf-8-sig"))

		if not isinstance(data, dict):
			return {"versions": None}

		tag = _normalize_version(data.get("tag_name"), "")
		if not tag:
			return {"versions": None}

		return {
			"versions": {
				"app": tag,
				"upper": self.get_cached_versions().latest_upper_version,
				"lower": self.get_cached_versions().latest_lower_version,
			},
			"release_tag": tag,
			"release_url": _normalize_version(data.get("html_url"), ""),
			"release_notes": _normalize_version(data.get("body"), ""),
		}

	@staticmethod
	def _github_release_api_url(update_url: str) -> str:
		parsed = urlparse(update_url.strip())
		if parsed.netloc.lower() != "github.com":
			return ""
		parts = [part for part in parsed.path.split("/") if part]
		if len(parts) < 3 or parts[2].lower() != "releases":
			return ""
		owner, repo = parts[0], parts[1]
		return f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

	def _parse_remote_versions(self, payload: str) -> dict[str, str] | None:
		text = payload.strip()
		if not text:
			return None

		if text.startswith("{"):
			return self._parse_json_versions(text)

		return self._parse_ini_versions(text)

	def _parse_json_versions(self, payload: str) -> dict[str, str] | None:
		try:
			data = json.loads(payload)
		except json.JSONDecodeError as exc:
			logger.warning(f"UpdateManager failed to parse JSON update payload: {exc}")
			return None

		if not isinstance(data, dict):
			return None

		latest_section = data.get(VERSION_REMOTE_SECTION)
		if not isinstance(latest_section, dict):
			latest_section = data

		return self._build_remote_version_map(latest_section)

	def _parse_ini_versions(self, payload: str) -> dict[str, str] | None:
		parser = configparser.ConfigParser()
		try:
			parser.read_string(payload)
		except configparser.Error as exc:
			logger.warning(f"UpdateManager failed to parse INI update payload: {exc}")
			return None

		latest_section_name = self._find_section(parser, VERSION_REMOTE_SECTION)
		if latest_section_name is not None:
			return self._build_remote_version_map(dict(parser[latest_section_name]))

		legacy_section_name = self._find_section(parser, "version")
		if legacy_section_name is None:
			return None

		section = parser[legacy_section_name]
		return self._build_remote_version_map(
			{
				LATEST_APP_VERSION_OPTION: section.get("RemoteVersion", section.get("LocalVersion", "")),
				LATEST_UPPER_VERSION_OPTION: section.get("UpperVersion", ""),
				LATEST_LOWER_VERSION_OPTION: section.get("LowerVersion", ""),
			}
		)

	@staticmethod
	def _find_section(parser: configparser.ConfigParser, name: str) -> str | None:
		for section_name in parser.sections():
			if section_name.lower() == name.lower():
				return section_name
		return None

	@staticmethod
	def _get_mapping_value(source: dict[str, object], *keys: str) -> object:
		normalized = {str(key).lower(): value for key, value in source.items()}
		for key in keys:
			value = normalized.get(key.lower())
			if value not in (None, ""):
				return value
		return None

	def _build_remote_version_map(self, source: dict[str, object]) -> dict[str, str] | None:
		latest_app = _normalize_version(
			self._get_mapping_value(
				source,
				LATEST_APP_VERSION_OPTION,
				"RemoteVersion",
				"LocalVersion",
			),
			"",
		)
		latest_upper = _normalize_version(
			self._get_mapping_value(source, LATEST_UPPER_VERSION_OPTION, "UpperVersion"),
			"",
		)
		latest_lower = _normalize_version(
			self._get_mapping_value(source, LATEST_LOWER_VERSION_OPTION, "LowerVersion"),
			"",
		)

		if not any((latest_app, latest_upper, latest_lower)):
			return None

		snapshot = self.get_cached_versions()
		return {
			"app": latest_app or snapshot.latest_app_version,
			"upper": latest_upper or snapshot.latest_upper_version,
			"lower": latest_lower or snapshot.latest_lower_version,
		}


update_manager = UpdateManager()
