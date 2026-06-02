# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: manage_firmware.py
#  @FileType: 固件管理文件，负责本地固件、远程版本和下载流程
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

import hashlib
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

from config import (
    CTX,
    logger,
)

FIRMWARE_EXTENSIONS = {".hex", ".bin", ".elf", ".axf"}


@dataclass(frozen=True)
class FirmwareRelease:
    kind: str
    tag: str
    version: str
    date: str
    suffix: int = 0
    asset_name: str = ""
    download_url: str = ""
    sha256: str = ""
    size: int = 0
    channel: str = "stable"
    device: str = ""
    hardware: str = ""
    changelog_url: str = ""
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
            has_updates = firmware_manager.build_update_flags(latest)
            result = FirmwareCheckResult(
                success=True,
                message="Latest firmware versions have been checked.",
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
    # Legacy tag/asset patterns for old GitHub-Releases-style firmware
    _tagPattern = re.compile(r"^(Power|Upper)_(\d{2})_(\d{2})_(\d{3})$", re.IGNORECASE)
    _assetPattern = re.compile(r"^UF4DP_(Power|Upper)_(\d{2})_(\d{2})\.(hex|bin|elf|axf)$", re.IGNORECASE)
    _datedDirPattern = re.compile(r"^(?:(\d{4})[-_])?(\d{2})(\d{2})(?:[-_](\d{3}))?$")

    # New semver-style patterns: F4CP-Power-v0.1.3.bin
    _newAssetPattern = re.compile(
        r"^F4CP-(Power|Upper)-v(\d+)\.(\d+)\.(\d+)\.(hex|bin|elf|axf)$",
        re.IGNORECASE,
    )
    _semverDirPattern = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

    def __init__(self, api_root: str = ""):
        self._apiRoot = api_root.rstrip("/")

    # ------------------------------------------------------------------
    # Directory helpers
    # ------------------------------------------------------------------

    @property
    def firmware_dir(self) -> Path:
        return CTX.dirs.FirmwareDir

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

    def _kind_dir(self, kind: str) -> Path:
        normalized = self._normalize_kind(kind)
        return self.power_dir if normalized == "Power" else self.upper_dir

    # ------------------------------------------------------------------
    # Public firmware file listing (used by DAPLink page)
    # ------------------------------------------------------------------

    def GetUpperFirmware(self) -> list[Path]:
        """Return list of all local Upper firmware file paths."""
        return self.list_firmware_files("Upper")

    def GetLowerFirmware(self) -> list[Path]:
        """Return list of all local Power firmware file paths."""
        return self.list_firmware_files("Power")

    def list_firmware_files(self, kind: str) -> list[Path]:
        """列出指定类型的本地固件文件，按版本/日期从新到旧排序。"""
        firmware_dir = self._kind_dir(kind)
        files = [
            path
            for path in firmware_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in FIRMWARE_EXTENSIONS
        ]
        return sorted(files, key=self._local_sort_key, reverse=True)

    # ------------------------------------------------------------------
    # Local release inspection
    # ------------------------------------------------------------------

    def get_latest_local_release(self, kind: str) -> FirmwareRelease | None:
        """从本地固件目录里解析出最新版本，供首页和烧录页显示。"""
        releases = [
            release
            for release in (self._release_from_local_file(path) for path in self.list_firmware_files(kind))
            if release is not None and release.kind.lower() == kind.lower()
        ]
        return max(releases, key=self._release_sort_key, default=None)

    # ------------------------------------------------------------------
    # Remote release fetching — routes to API server or GitHub fallback
    # ------------------------------------------------------------------

    def get_latest_remote_releases(self) -> dict[str, FirmwareRelease]:
        """获取远程最新固件。

        优先走 F4CP 更新服务；没有配置服务地址时，才回落到旧的 GitHub Releases。
        """
        base_url = self._get_base_url()
        if base_url:
            return self._fetch_from_api(base_url)
        # Fall back to the legacy GitHub Releases API
        logger.info("FirmwareManager: BaseUrl not configured, falling back to GitHub Releases")
        return self._fetch_from_github()

    def _get_base_url(self) -> str:
        url = str(CTX.cfg.firmwareBaseUrl.value or "").strip().rstrip("/")
        return url

    # --- FastAPI server path ---

    def _fetch_from_api(self, base_url: str) -> dict[str, FirmwareRelease]:
        """从 F4CP 更新服务读取 Power/Upper 的最新 manifest。"""
        latest: dict[str, FirmwareRelease] = {}
        errors: list[str] = []

        for kind in ("Power", "Upper"):
            kind_lower = kind.lower()
            try:
                latest_data = self._api_get_json(f"{base_url}/api/v1/firmware/{kind_lower}/latest")
                if not isinstance(latest_data, dict):
                    errors.append(f"{kind}: invalid /latest response")
                    continue
                version = str(latest_data.get("latest") or "").strip()
                if not version:
                    errors.append(f"{kind}: 'latest' field missing in /latest response")
                    continue
                manifest_data = self._api_get_json(
                    f"{base_url}/api/v1/firmware/{kind_lower}/versions/{version}"
                )
                if not isinstance(manifest_data, dict):
                    errors.append(f"{kind}: invalid manifest response for {version}")
                    continue
                release = self._release_from_manifest(kind, base_url, manifest_data)
                if release is not None:
                    latest[kind] = release
                else:
                    errors.append(f"{kind}: could not parse manifest for {version}")
            except Exception as exc:
                logger.error(f"{self.__class__.__name__}: FirmwareManager failed to fetch {kind} firmware info: {exc}")
                errors.append(f"{kind}: {exc}")

        if not latest and errors:
            message = f"Failed to fetch firmware info from update server: {'; '.join(errors)}"
            logger.error(f"{self.__class__.__name__}: {message}")
            raise RuntimeError(message)

        return latest

    def _release_from_manifest(
        self,
        kind: str,
        base_url: str,
        manifest_data: dict,
    ) -> FirmwareRelease | None:
        """把服务端 manifest 转成内部 FirmwareRelease，页面和下载逻辑只认这一种结构。"""
        version = str(manifest_data.get("version") or "").strip()
        if not version:
            return None

        files = manifest_data.get("files") or {}
        # Prefer .bin, fall back to .hex
        file_info = files.get("bin") or files.get("hex")
        if not file_info or not isinstance(file_info, dict):
            return None

        rel_url = str(file_info.get("download_url") or "").strip()
        if not rel_url:
            return None
        download_url = (base_url + rel_url) if rel_url.startswith("/") else rel_url

        sha256 = str(file_info.get("sha256") or "").strip()
        size = int(file_info.get("size") or 0)
        asset_name = str(file_info.get("name") or "").strip()

        rel_changelog = str(manifest_data.get("changelog_url") or "").strip()
        changelog_url = (base_url + rel_changelog) if rel_changelog.startswith("/") else rel_changelog

        return FirmwareRelease(
            kind=kind,
            tag=version,
            version=version,
            date=str(manifest_data.get("date") or ""),
            suffix=0,
            asset_name=asset_name,
            download_url=download_url,
            sha256=sha256,
            size=size,
            channel=str(manifest_data.get("channel") or "stable"),
            device=str(manifest_data.get("devices") or ""),
            hardware=str(manifest_data.get("hardware") or ""),
            changelog_url=changelog_url,
        )

    # --- Legacy GitHub Releases path ---

    def _fetch_from_github(self) -> dict[str, FirmwareRelease]:
        """兼容旧的 GitHub Releases 命名方式，并按每类固件挑出最新项。"""
        releases = self.fetch_releases()
        gh_latest: dict[str, FirmwareRelease] = {}
        for release in releases:
            current = gh_latest.get(release.kind)
            if current is None or (release.date, release.suffix) > (current.date, current.suffix):
                gh_latest[release.kind] = release
        return gh_latest

    @property
    def api_root(self) -> str:
        """Legacy GitHub API root — only used when BaseUrl is not configured."""
        if self._apiRoot:
            return self._apiRoot
        owner = str(CTX.cfg.firmwareGithubOwner.value or "").strip()
        repo = str(CTX.cfg.firmwareGithubRepo.value or "").strip()
        if not owner or not repo:
            message = "Firmware remote BaseUrl and GitHub owner/repo are both not configured."
            logger.error(f"{self.__class__.__name__}: {message}")
            raise RuntimeError(message)
        return f"https://api.github.com/repos/{owner}/{repo}"

    def fetch_releases(self) -> list[FirmwareRelease]:
        """Fetch firmware releases from the legacy GitHub Releases API."""
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

    # ------------------------------------------------------------------
    # Download with SHA-256 verification
    # ------------------------------------------------------------------

    def download_latest(self, kind: str) -> FirmwareRelease:
        """下载指定类型的远程最新固件。"""
        latest = self.get_latest_remote_releases().get(self._normalize_kind(kind))
        if latest is None:
            message = f"No remote {kind} firmware release was found."
            logger.error(f"{self.__class__.__name__}: {message}")
            raise RuntimeError(message)
        return self.download_release(latest)

    def download_release(self, release: FirmwareRelease) -> FirmwareRelease:
        """下载一个固件版本。

        文件先写入临时路径，校验 SHA-256 通过后再替换到正式目录，避免留下半截文件。
        """
        if not release.download_url:
            message = f"Release {release.tag} does not contain a downloadable firmware asset."
            logger.error(f"{self.__class__.__name__}: {message}")
            raise RuntimeError(message)

        target_dir = self._kind_dir(release.kind) / self._version_dir_name(release)
        target_dir.mkdir(parents=True, exist_ok=True)

        # Derive filename: prefer asset_name, fall back to URL basename
        asset_name = release.asset_name or Path(release.download_url.split("?")[0]).name
        if not asset_name:
            asset_name = f"F4CP-{release.kind}-{release.version}.bin"
        target_path = target_dir / asset_name

        request = self._build_request(release.download_url)
        tmp_path: Path | None = None
        try:
            with urlopen(request, timeout=60) as response:
                suffix = Path(asset_name).suffix or ".bin"
                with tempfile.NamedTemporaryFile(
                    delete=False, dir=str(target_dir), suffix=suffix
                ) as tmp_file:
                    shutil.copyfileobj(response, tmp_file)
                    tmp_path = Path(tmp_file.name)

            # SHA-256 integrity check
            if release.sha256:
                actual_digest = self._sha256_file(tmp_path)
                if actual_digest.lower() != release.sha256.lower().strip():
                    tmp_path.unlink(missing_ok=True)
                    tmp_path = None
                    message = (
                        f"SHA-256 mismatch for {asset_name}: "
                        f"expected {release.sha256}, got {actual_digest}"
                    )
                    logger.error(f"{self.__class__.__name__}: {message}")
                    raise RuntimeError(message)

            tmp_path.replace(target_path)
            tmp_path = None

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
            asset_name=asset_name,
            download_url=release.download_url,
            sha256=release.sha256,
            size=release.size,
            channel=release.channel,
            device=release.device,
            hardware=release.hardware,
            changelog_url=release.changelog_url,
            path=target_path,
        )

    # ------------------------------------------------------------------
    # config write-back
    # ------------------------------------------------------------------

    def write_local_version(self, release: FirmwareRelease) -> None:
        """把刚下载完成的版本写回配置，首页刷新时就能看到本地版本。"""
        if release.kind == "Upper":
            item = CTX.cfg.localUpperVersion
        else:
            item = CTX.cfg.localLowerVersion

        from qfluentwidgets import qconfig

        qconfig.set(item, release.version)

    def build_update_flags(self, latest: dict[str, FirmwareRelease]) -> dict[str, bool]:
        """对比远程和本地版本，生成页面上的“是否有更新”标记。"""
        flags: dict[str, bool] = {}
        for kind in ("Power", "Upper"):
            remote = latest.get(kind)
            local = self.get_latest_local_release(kind)
            flags[kind] = remote is not None and (
                local is None
                or self._release_sort_key(remote) > self._release_sort_key(local)
            )
        return flags

    # ------------------------------------------------------------------
    # Static normalisation / parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_kind(kind: str) -> str:
        text = str(kind or "").strip().lower()
        if text in {"power", "lower", "stm32g474"}:
            return "Power"
        if text in {"upper", "stm32h750"}:
            return "Upper"
        raise ValueError(f"Unsupported firmware kind: {kind!r}")

    @staticmethod
    def _parse_semver(version: str) -> tuple[int, int, int] | None:
        """Parse 'v0.1.3' or '0.1.3' -> (0, 1, 3), return None if not semver."""
        m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", str(version or "").strip())
        if m:
            return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return None

    @classmethod
    def _release_sort_key(cls, release: FirmwareRelease) -> tuple[int, int, int, int, int]:
        """Return a sortable key, where semver releases (era=1) always rank above old-style (era=0)."""
        semver = cls._parse_semver(release.version)
        if semver:
            return (1, semver[0], semver[1], semver[2], 0)
        # Old-style: encode date "MM_DD" or "YYYY-MM-DD" as numeric
        try:
            parts = str(release.date).replace("-", "_").split("_")
            mm = int(parts[-2]) if len(parts) >= 2 else 0
            dd = int(parts[-1]) if len(parts) >= 1 else 0
            date_int = mm * 100 + dd
        except (ValueError, IndexError):
            date_int = 0
        return (0, 0, date_int, release.suffix, 0)

    @staticmethod
    def _version_dir_name(release: FirmwareRelease) -> str:
        # New semver releases: use version string directly as directory name
        if re.match(r"^v\d+\.\d+\.\d+", release.version):
            return release.version
        # Old date-based format
        year = datetime.now().strftime("%Y")
        month, day = release.date.split("_", 1)
        return f"{year}-{month}{day}-{release.suffix:03d}"

    # ------------------------------------------------------------------
    # Local file parsing (supports both old and new naming conventions)
    # ------------------------------------------------------------------

    def _release_from_local_file(self, path: Path) -> FirmwareRelease | None:
        """从本地文件名反推出固件版本，同时兼容 semver 和旧日期命名。"""
        # New semver naming: F4CP-Power-v0.1.3.bin
        new_match = self._newAssetPattern.match(path.name)
        if new_match is not None:
            kind = self._normalize_kind(new_match.group(1))
            version = f"v{new_match.group(2)}.{new_match.group(3)}.{new_match.group(4)}"
            # Try to read date from sibling manifest.json
            date_str = self._read_manifest_date(path.parent)
            return FirmwareRelease(
                kind=kind,
                tag=version,
                version=version,
                date=date_str,
                suffix=0,
                asset_name=path.name,
                path=path,
            )

        # Legacy naming: UF4DP_Power_MM_DD.hex
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

    @staticmethod
    def _read_manifest_date(version_dir: Path) -> str:
        """Try to read 'date' field from a sibling manifest.json, return '' on failure."""
        manifest_path = version_dir / "manifest.json"
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                return str(data.get("date") or "")
            except Exception:
                pass
        return ""

    def _release_from_tag(self, tag: str) -> FirmwareRelease | None:
        match = self._tagPattern.match(tag)
        if match is None:
            return None
        kind = self._normalize_kind(match.group(1))
        date = f"{match.group(2)}_{match.group(3)}"
        suffix = int(match.group(4))
        return FirmwareRelease(kind=kind, tag=tag, version=tag, date=date, suffix=suffix)

    def _suffix_from_parent(self, parent: Path, date: str) -> int:
        release = self._release_from_tag(parent.name)
        if release is not None and release.date == date:
            return release.suffix
        dir_match = self._datedDirPattern.match(parent.name)
        if dir_match is not None and f"{dir_match.group(2)}_{dir_match.group(3)}" == date:
            suffix = dir_match.group(4)
            return int(suffix) if suffix else 0
        return 0

    def _find_release_asset(
        self, item: dict[str, object], kind: str, date: str
    ) -> dict[str, object] | None:
        """在旧 GitHub Release 的 assets 里找到匹配 kind/date 的固件文件。"""
        assets = item.get("../../Resources/Assets")
        if not isinstance(assets, list):
            return None
        expected_prefix = f"UF4DP_{kind}_{date}"
        matched_assets: list[dict[str, object]] = []
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "")
            if (
                name.lower().startswith(expected_prefix.lower())
                and Path(name).suffix.lower() in FIRMWARE_EXTENSIONS
            ):
                matched_assets.append(asset)
        if not matched_assets:
            return None
        extension_priority = {".hex": 0, ".bin": 1, ".elf": 2, ".axf": 3}
        return min(
            matched_assets,
            key=lambda a: extension_priority.get(
                Path(str(a.get("name") or "")).suffix.lower(), 99
            ),
        )

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _api_get_json(self, url: str) -> object:
        """Fetch JSON from the F4CP update server, raising RuntimeError on failure."""
        request = self._build_request(url)
        try:
            with urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            message = f"HTTP {exc.code} from update server ({url}): {exc.reason}"
            logger.error(f"{self.__class__.__name__}: {message}")
            raise RuntimeError(message) from exc
        except URLError as exc:
            message = f"Cannot connect to update server ({url}): {exc}"
            logger.error(f"{self.__class__.__name__}: {message}")
            raise RuntimeError(message) from exc
        except json.JSONDecodeError as exc:
            message = f"Update server returned invalid JSON ({url}): {exc}"
            logger.error(f"{self.__class__.__name__}: {message}")
            raise RuntimeError(message) from exc

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
        headers: dict[str, str] = {
            "User-Agent": "F4CP-FirmwareManager/1.0",
            "Accept": "application/json",
        }
        # Add GitHub-specific headers only for GitHub API URLs
        if "api.github.com" in url:
            headers["Accept"] = "application/vnd.github+json"
            headers["X-GitHub-Api-Version"] = "2022-11-28"
            token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
            if token:
                headers["Authorization"] = f"Bearer {token}"
        return Request(url, headers=headers)

    @staticmethod
    def _sha256_file(path: Path) -> str:
        """Compute the SHA-256 hex digest of *path*."""
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    # ------------------------------------------------------------------
    # Sort key for raw file paths (used by list_firmware_files)
    # ------------------------------------------------------------------

    @staticmethod
    def _local_sort_key(path: Path) -> tuple:
        # New semver naming takes priority
        new_match = FirmwareManager._newAssetPattern.match(path.name)
        if new_match is not None:
            v = (int(new_match.group(2)), int(new_match.group(3)), int(new_match.group(4)))
            return (1, v[0], v[1], v[2], 0.0)

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

        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        return (0, 0, 0, 0, mtime)


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
