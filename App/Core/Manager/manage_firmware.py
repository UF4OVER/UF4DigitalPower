# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/5/3
#  @FileName: manage_firmware.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact :
#  @Python  :
# -------------------------------

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PyQt5.QtCore import QCoreApplication, QEvent, QObject, QThread, pyqtSignal

from Config import (
    CTX,
    FIRMWARE_GITHUB_OWNER_OPTION,
    FIRMWARE_GITHUB_REPO_OPTION,
    FIRMWARE_REMOTE_SECTION,
    LATEST_LOWER_VERSION_OPTION,
    LATEST_UPPER_VERSION_OPTION,
    LOCAL_LOWER_VERSION_OPTION,
    LOCAL_UPPER_VERSION_OPTION,
    VERSION_LOCAL_SECTION,
    VERSION_REMOTE_SECTION,
    logger,
)

FIRMWARE_EXTENSIONS = {".hex", ".bin", ".elf", ".axf"}


@dataclass(frozen=True)
class FirmwareRelease:
    kind: str
    tag: str
    version: str
    date: str
    suffix: int
    asset_name: str = ""
    download_url: str = ""
    path: Path | None = None


@dataclass(frozen=True)
class FirmwareDownloadResult:
    success: bool
    kind: str
    message: str
    release: FirmwareRelease | None = None


@dataclass(frozen=True)
class FirmwareCheckResult:
    success: bool
    message: str
    latest: dict[str, FirmwareRelease]
    has_updates: dict[str, bool]


class FirmwareDownloadFinishedEvent(QEvent):
    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())

    def __init__(self, result: FirmwareDownloadResult):
        super().__init__(self.EVENT_TYPE)
        self.result = result


class FirmwareCheckFinishedEvent(QEvent):
    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())

    def __init__(self, result: FirmwareCheckResult):
        super().__init__(self.EVENT_TYPE)
        self.result = result


class FirmwareCheckThread(QThread):
    resultReady = pyqtSignal(object)

    def run(self) -> None:
        try:
            latest = firmware_manager.get_latest_remote_releases()
            firmware_manager.write_latest_versions(latest)
            has_updates = firmware_manager.build_update_flags(latest)
            result = FirmwareCheckResult(
                success=True,
                message="Latest firmware versions have been refreshed.",
                latest=latest,
                has_updates=has_updates,
            )
        except Exception as exc:
            logger.exception("Failed to check firmware updates")
            result = FirmwareCheckResult(
                success=False,
                message=str(exc) or "Failed to check firmware updates.",
                latest={},
                has_updates={},
            )
        self.resultReady.emit(result)


class FirmwareDownloadThread(QThread):
    resultReady = pyqtSignal(object)

    def __init__(self, kind: str, parent: QObject | None = None):
        super().__init__(parent)
        self.kind = kind

    def run(self) -> None:
        try:
            release = firmware_manager.download_latest(self.kind)
            firmware_manager.write_local_version(release)
            result = FirmwareDownloadResult(
                success=True,
                kind=release.kind,
                message="Firmware has been downloaded.",
                release=release,
            )
        except Exception as exc:
            logger.exception(f"Failed to download {self.kind} firmware")
            result = FirmwareDownloadResult(
                success=False,
                kind=self.kind,
                message=str(exc) or "Failed to download firmware.",
            )
        self.resultReady.emit(result)


class FirmwareManager:
    _tagPattern = re.compile(r"^(Power|Upper)_(\d{2})_(\d{2})_(\d{3})$", re.IGNORECASE)
    _assetPattern = re.compile(r"^UF4DP_(Power|Upper)_(\d{2})_(\d{2})\.(hex|bin|elf|axf)$", re.IGNORECASE)
    _datedDirPattern = re.compile(r"^(?:(\d{4})[-_])?(\d{2})(\d{2})(?:[-_](\d{3}))?$")

    def __init__(self, api_root: str = ""):
        self._apiRoot = api_root.rstrip("/")

    @property
    def firmware_dir(self) -> Path:
        return CTX.dirs.FirmwareDir

    @property
    def api_root(self) -> str:
        if self._apiRoot:
            return self._apiRoot

        owner = str(
            CTX.settings.get(
                FIRMWARE_REMOTE_SECTION,
                FIRMWARE_GITHUB_OWNER_OPTION,
                "",
            )
            or ""
        ).strip()
        repo = str(
            CTX.settings.get(
                FIRMWARE_REMOTE_SECTION,
                FIRMWARE_GITHUB_REPO_OPTION,
                "",
            )
            or ""
        ).strip()
        if not owner or not repo:
            raise RuntimeError("Firmware GitHub owner/repo is not configured.")
        return f"https://api.github.com/repos/{owner}/{repo}"

    @property
    def power_dir(self) -> Path:
        return self._ensureFirmwareDir("Power")

    @property
    def upper_dir(self) -> Path:
        return self._ensureFirmwareDir("Upper")

    def _ensureFirmwareDir(self, *parts: str) -> Path:
        firmwareDir = self.firmware_dir.joinpath(*parts)
        firmwareDir.mkdir(parents=True, exist_ok=True)
        return firmwareDir

    def GetUpperFirmware(self) -> list[Path]:
        """
        return: 上位机固件文件Path对象列表
        """
        return self.list_firmware_files("Upper")

    def GetLowerFirmware(self) -> list[Path]:
        """
        return: 下位机电源板固件Path对象列表
        """
        return self.list_firmware_files("Power")

    def list_firmware_files(self, kind: str) -> list[Path]:
        firmware_dir = self._kind_dir(kind)
        files = [
            path
            for path in firmware_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in FIRMWARE_EXTENSIONS
        ]
        return sorted(files, key=self._local_sort_key, reverse=True)

    def get_latest_local_release(self, kind: str) -> FirmwareRelease | None:
        releases = [
            release
            for release in (self._release_from_local_file(path) for path in self.list_firmware_files(kind))
            if release is not None and release.kind.lower() == kind.lower()
        ]
        return max(releases, key=lambda item: (item.date, item.suffix, item.path.stat().st_mtime if item.path else 0), default=None)

    def get_latest_remote_releases(self) -> dict[str, FirmwareRelease]:
        releases = self.fetch_releases()
        latest: dict[str, FirmwareRelease] = {}
        for release in releases:
            current = latest.get(release.kind)
            if current is None or (release.date, release.suffix) > (current.date, current.suffix):
                latest[release.kind] = release
        return latest

    def fetch_releases(self) -> list[FirmwareRelease]:
        payload = self._github_get_json(f"{self.api_root}/releases")
        if not isinstance(payload, list):
            return []

        releases: list[FirmwareRelease] = []
        for item in payload:
            if not isinstance(item, dict):
                continue

            tag = str(item.get("tag_name") or "").strip()
            release = self._release_from_tag(tag)
            if release is None:
                continue

            asset = self._find_release_asset(item, release.kind, release.date)
            if asset is not None:
                release = FirmwareRelease(
                    kind=release.kind,
                    tag=release.tag,
                    version=release.version,
                    date=release.date,
                    suffix=release.suffix,
                    asset_name=str(asset.get("name") or ""),
                    download_url=str(asset.get("browser_download_url") or ""),
                )
            releases.append(release)

        return releases

    def download_latest(self, kind: str) -> FirmwareRelease:
        latest = self.get_latest_remote_releases().get(self._normalize_kind(kind))
        if latest is None:
            raise RuntimeError(f"No remote {kind} firmware release was found.")
        return self.download_release(latest)

    def download_release(self, release: FirmwareRelease) -> FirmwareRelease:
        if not release.download_url:
            raise RuntimeError(f"Release {release.tag} does not contain a downloadable firmware asset.")

        target_dir = self._kind_dir(release.kind) / self._version_dir_name(release)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / release.asset_name

        request = self._build_request(release.download_url)
        tmp_path: Path | None = None
        try:
            with urlopen(request, timeout=60) as response:
                with tempfile.NamedTemporaryFile(delete=False, dir=str(target_dir), suffix=target_path.suffix) as tmp_file:
                    shutil.copyfileobj(response, tmp_file)
                    tmp_path = Path(tmp_file.name)
            tmp_path.replace(target_path)
        except (HTTPError, URLError, OSError) as exc:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            logger.warning(f"FirmwareManager failed to download {release.tag}: {exc}")
            raise

        return FirmwareRelease(
            kind=release.kind,
            tag=release.tag,
            version=release.version,
            date=release.date,
            suffix=release.suffix,
            asset_name=release.asset_name,
            download_url=release.download_url,
            path=target_path,
        )

    def write_local_version(self, release: FirmwareRelease) -> None:
        if release.kind == "Upper":
            local_option = LOCAL_UPPER_VERSION_OPTION
            latest_option = LATEST_UPPER_VERSION_OPTION
        else:
            local_option = LOCAL_LOWER_VERSION_OPTION
            latest_option = LATEST_LOWER_VERSION_OPTION

        CTX.settings.set(VERSION_LOCAL_SECTION, local_option, release.version)
        CTX.settings.set(VERSION_REMOTE_SECTION, latest_option, release.version)

    def write_latest_versions(self, latest: dict[str, FirmwareRelease]) -> None:
        upper = latest.get("Upper")
        power = latest.get("Power")
        if upper is not None:
            CTX.settings.set(VERSION_REMOTE_SECTION, LATEST_UPPER_VERSION_OPTION, upper.version)
        if power is not None:
            CTX.settings.set(VERSION_REMOTE_SECTION, LATEST_LOWER_VERSION_OPTION, power.version)

    def build_update_flags(self, latest: dict[str, FirmwareRelease]) -> dict[str, bool]:
        flags: dict[str, bool] = {}
        for kind in ("Power", "Upper"):
            remote = latest.get(kind)
            local = self.get_latest_local_release(kind)
            flags[kind] = remote is not None and (
                local is None or (remote.date, remote.suffix) > (local.date, local.suffix)
            )
        return flags

    def _kind_dir(self, kind: str) -> Path:
        normalized = self._normalize_kind(kind)
        return self.power_dir if normalized == "Power" else self.upper_dir

    @staticmethod
    def _normalize_kind(kind: str) -> str:
        text = str(kind or "").strip().lower()
        if text in {"power", "lower", "stm32g474"}:
            return "Power"
        if text in {"upper", "stm32h750"}:
            return "Upper"
        raise ValueError(f"Unsupported firmware kind: {kind}")

    def _release_from_tag(self, tag: str) -> FirmwareRelease | None:
        match = self._tagPattern.match(tag)
        if match is None:
            return None
        kind = self._normalize_kind(match.group(1))
        date = f"{match.group(2)}_{match.group(3)}"
        suffix = int(match.group(4))
        return FirmwareRelease(kind=kind, tag=tag, version=tag, date=date, suffix=suffix)

    def _release_from_local_file(self, path: Path) -> FirmwareRelease | None:
        asset_match = self._assetPattern.match(path.name)
        if asset_match is None:
            return None

        kind = self._normalize_kind(asset_match.group(1))
        date = f"{asset_match.group(2)}_{asset_match.group(3)}"
        suffix = self._suffix_from_parent(path.parent, date)
        tag = f"{kind}_{date}_{suffix:03d}"
        return FirmwareRelease(
            kind=kind,
            tag=tag,
            version=tag,
            date=date,
            suffix=suffix,
            asset_name=path.name,
            path=path,
        )

    def _suffix_from_parent(self, parent: Path, date: str) -> int:
        release = self._release_from_tag(parent.name)
        if release is not None and release.date == date:
            return release.suffix
        dir_match = self._datedDirPattern.match(parent.name)
        if dir_match is not None and f"{dir_match.group(2)}_{dir_match.group(3)}" == date:
            suffix = dir_match.group(4)
            return int(suffix) if suffix else 0
        return 0

    def _find_release_asset(self, item: dict[str, object], kind: str, date: str) -> dict[str, object] | None:
        assets = item.get("assets")
        if not isinstance(assets, list):
            return None

        expected_prefix = f"UF4DP_{kind}_{date}"
        matched_assets: list[dict[str, object]] = []
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "")
            if name.lower().startswith(expected_prefix.lower()) and Path(name).suffix.lower() in FIRMWARE_EXTENSIONS:
                matched_assets.append(asset)

        if not matched_assets:
            return None

        extension_priority = {".hex": 0, ".bin": 1, ".elf": 2, ".axf": 3}
        return min(
            matched_assets,
            key=lambda asset: extension_priority.get(Path(str(asset.get("name") or "")).suffix.lower(), 99),
        )

    def _github_get_json(self, url: str) -> object:
        request = self._build_request(url)
        try:
            with urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, json.JSONDecodeError) as exc:
            logger.warning(f"FirmwareManager failed to fetch GitHub releases: {exc}")
            return []

    @staticmethod
    def _build_request(url: str) -> Request:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "F4CP-FirmwareManager",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return Request(url, headers=headers)

    @staticmethod
    def _local_sort_key(path: Path) -> tuple[str, int, float, str]:
        date = ""
        suffix = 0
        asset_match = FirmwareManager._assetPattern.match(path.name)
        if asset_match is not None:
            date = f"{asset_match.group(2)}_{asset_match.group(3)}"

        release_match = FirmwareManager._tagPattern.match(path.parent.name)
        if release_match is not None:
            suffix = int(release_match.group(4))
        elif path.parent.name:
            dir_match = FirmwareManager._datedDirPattern.match(path.parent.name)
            if dir_match is not None:
                date = f"{dir_match.group(2)}_{dir_match.group(3)}"
                suffix_text = dir_match.group(4)
                suffix = int(suffix_text) if suffix_text else 0

        return date, suffix, path.stat().st_mtime, path.name

    @staticmethod
    def _version_dir_name(release: FirmwareRelease) -> str:
        year = datetime.now().strftime("%Y")
        month, day = release.date.split("_", 1)
        return f"{year}-{month}{day}-{release.suffix:03d}"


firmware_manager = FirmwareManager()


class FirmwareCheckManager:
    def __init__(self):
        self._worker: FirmwareCheckThread | None = None

    @property
    def is_checking(self) -> bool:
        return bool(self._worker and self._worker.isRunning())

    def check_updates(self, receiver: QObject) -> bool:
        if self.is_checking:
            logger.info("FirmwareCheckManager skipped because another check is running")
            return False

        self._worker = FirmwareCheckThread()
        self._worker.resultReady.connect(lambda result, target=receiver: self._publish_result(target, result))
        self._worker.finished.connect(self._cleanup)
        self._worker.start()
        return True

    def _publish_result(self, receiver: QObject, result: FirmwareCheckResult) -> None:
        QCoreApplication.postEvent(receiver, FirmwareCheckFinishedEvent(result))

    def _cleanup(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None


class FirmwareDownloadManager:
    def __init__(self):
        self._workers: dict[str, FirmwareDownloadThread] = {}

    def is_downloading(self, kind: str | None = None) -> bool:
        if kind is None:
            return any(worker.isRunning() for worker in self._workers.values())
        normalized = firmware_manager._normalize_kind(kind)
        worker = self._workers.get(normalized)
        return bool(worker and worker.isRunning())

    def download_latest(self, kind: str, receiver: QObject) -> bool:
        normalized = firmware_manager._normalize_kind(kind)
        if self.is_downloading(normalized):
            logger.info(f"FirmwareDownloadManager skipped {normalized} because it is already running")
            return False

        worker = FirmwareDownloadThread(normalized)
        worker.resultReady.connect(lambda result, target=receiver: self._publish_result(target, result))
        worker.finished.connect(lambda kind=normalized: self._cleanup(kind))
        self._workers[normalized] = worker
        worker.start()
        return True

    def _publish_result(self, receiver: QObject, result: FirmwareDownloadResult) -> None:
        QCoreApplication.postEvent(receiver, FirmwareDownloadFinishedEvent(result))

    def _cleanup(self, kind: str) -> None:
        worker = self._workers.pop(kind, None)
        if worker is not None:
            worker.deleteLater()


firmware_download_manager = FirmwareDownloadManager()
firmware_check_manager = FirmwareCheckManager()
