# -*- coding: utf-8 -*-

from __future__ import annotations

import configparser
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from PyQt5.QtCore import QCoreApplication, QEvent, QObject

from Config import (
	APP_CONFIG_PATH,
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
	SettingsManager,
	logger,
)


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


class UpdateCheckFinishedEvent(QEvent):
	EVENT_TYPE = QEvent.Type(QEvent.registerEventType())

	def __init__(self, result: UpdateCheckResult):
		super().__init__(self.EVENT_TYPE)
		self.result = result


class UpdateManager:
	def __init__(self, config_path: Path):
		self._config_path = Path(config_path)
		self._lock = threading.Lock()
		self._is_checking = False

	@property
	def is_checking(self) -> bool:
		with self._lock:
			return self._is_checking

	def _set_checking(self, checking: bool) -> None:
		with self._lock:
			self._is_checking = checking

	def _settings(self) -> SettingsManager:
		return SettingsManager(self._config_path)

	def get_cached_versions(self) -> FirmwareVersionSnapshot:
		settings = self._settings()
		return FirmwareVersionSnapshot(
			local_app_version=_normalize_version(
				settings.get(VERSION_LOCAL_SECTION, LOCAL_APP_VERSION_OPTION, "--")
			),
			latest_app_version=_normalize_version(
				settings.get(VERSION_REMOTE_SECTION, LATEST_APP_VERSION_OPTION, "--")
			),
			local_upper_version=_normalize_version(
				settings.get(VERSION_LOCAL_SECTION, LOCAL_UPPER_VERSION_OPTION, "--")
			),
			latest_upper_version=_normalize_version(
				settings.get(VERSION_REMOTE_SECTION, LATEST_UPPER_VERSION_OPTION, "--")
			),
			local_lower_version=_normalize_version(
				settings.get(VERSION_LOCAL_SECTION, LOCAL_LOWER_VERSION_OPTION, "--")
			),
			latest_lower_version=_normalize_version(
				settings.get(VERSION_REMOTE_SECTION, LATEST_LOWER_VERSION_OPTION, "--")
			),
		)

	def check_for_updates(self, receiver: QObject, manual: bool = False) -> bool:
		if self.is_checking:
			logger.info("UpdateManager skipped update check because another check is running")
			return False

		self._set_checking(True)
		worker = threading.Thread(
			target=self._run_check,
			args=(receiver, manual),
			name="FirmwareUpdateChecker",
			daemon=True,
		)
		worker.start()
		return True

	def _run_check(self, receiver: QObject, manual: bool) -> None:
		try:
			result = self._perform_check(manual)
		except Exception as exc:
			logger.exception("Unexpected error during firmware update check")
			result = UpdateCheckResult(
				success=False,
				manual=manual,
				message="Failed to check updates.",
				snapshot=self.get_cached_versions(),
			)
		finally:
			self._set_checking(False)

		QCoreApplication.postEvent(receiver, UpdateCheckFinishedEvent(result))

	def _perform_check(self, manual: bool) -> UpdateCheckResult:
		snapshot_before = self.get_cached_versions()
		settings = self._settings()
		update_url = str(settings.get(UPDATE_SECTION, UPDATE_URL_OPTION, "") or "").strip()

		if not update_url:
			logger.warning("UpdateManager skipped update check because UpdateUrl is empty")
			return UpdateCheckResult(
				success=False,
				manual=manual,
				message="Update URL is not configured.",
				snapshot=snapshot_before,
			)

		logger.info(f"UpdateManager fetching remote firmware version info from {update_url}")
		try:
			with urlopen(update_url, timeout=8) as response:
				payload = response.read().decode("utf-8-sig")
		except URLError as exc:
			logger.warning(f"UpdateManager failed to fetch update data: {exc}")
			return UpdateCheckResult(
				success=False,
				manual=manual,
				message="Failed to connect to the update server.",
				snapshot=snapshot_before,
			)

		latest_versions = self._parse_remote_versions(payload)
		if latest_versions is None:
			logger.warning("UpdateManager received an unsupported update payload")
			return UpdateCheckResult(
				success=False,
				manual=manual,
				message="The update server returned invalid version data.",
				snapshot=snapshot_before,
			)

		settings.set(VERSION_REMOTE_SECTION, LATEST_APP_VERSION_OPTION, latest_versions["app"])
		settings.set(VERSION_REMOTE_SECTION, LATEST_UPPER_VERSION_OPTION, latest_versions["upper"])
		settings.set(VERSION_REMOTE_SECTION, LATEST_LOWER_VERSION_OPTION, latest_versions["lower"])

		snapshot_after = self.get_cached_versions()
		has_changes = (
			snapshot_before.latest_app_version != snapshot_after.latest_app_version
			or snapshot_before.latest_upper_version != snapshot_after.latest_upper_version
			or snapshot_before.latest_lower_version != snapshot_after.latest_lower_version
		)
		logger.info(
			"UpdateManager refreshed latest versions: "
			f"app={snapshot_after.latest_app_version}, "
			f"upper={snapshot_after.latest_upper_version}, "
			f"lower={snapshot_after.latest_lower_version}"
		)
		return UpdateCheckResult(
			success=True,
			manual=manual,
			message="Latest firmware versions have been refreshed.",
			snapshot=snapshot_after,
			has_changes=has_changes,
		)

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


update_manager = UpdateManager(APP_CONFIG_PATH)
