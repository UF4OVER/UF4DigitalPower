# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 04-26 13:15
#  @FileName: daplink_pyocd_session.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : Powered By GPT-5.4
#  @Python  :
# -------------------------------

from __future__ import annotations

import os
import threading
import zipfile
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from PyQt5.QtCore import QCoreApplication, QEvent, QObject
from pyocd.core.helpers import ConnectHelper
from pyocd.core.memory_map import FlashRegion, RamRegion
from pyocd.flash.file_programmer import FileProgrammer
from pyocd.target.pack.cmsis_pack import CmsisPack
from pyocd.target.pack.pack_target import normalise_target_type_name

from Config import DirPathsInstance, logger


class DaplinkProgrammerEventType(IntEnum):
    REQUEST = QEvent.registerEventType()
    LOG = QEvent.registerEventType()
    MESSAGE = QEvent.registerEventType()
    STATE = QEvent.registerEventType()
    PROBES = QEvent.registerEventType()
    TARGETS = QEvent.registerEventType()
    DEVICE_INFO = QEvent.registerEventType()
    PROGRESS = QEvent.registerEventType()
    ACTION_FINISHED = QEvent.registerEventType()


class DaplinkProgrammerEvent(QEvent):
    def __init__(self, etype: DaplinkProgrammerEventType):
        super().__init__(QEvent.Type(int(etype)))


@dataclass(frozen=True)
class DaplinkConnectConfig:
    probe_uid: str | None = None
    target_name: str = ""
    frequency: str = "1000000"
    connect_mode: str = "halt"


@dataclass(frozen=True)
class DaplinkRequestPayload:
    action: str
    connect: DaplinkConnectConfig = field(default_factory=DaplinkConnectConfig)
    file_path: str | None = None
    base_address: str = ""
    erase_mode: str = "sector"
    smart_flash: bool = True
    trust_crc: bool = False
    reset_after_download: bool = True


class DaplinkRequestEvent(DaplinkProgrammerEvent):
    def __init__(self, payload: DaplinkRequestPayload):
        super().__init__(DaplinkProgrammerEventType.REQUEST)
        self.payload = payload


@dataclass(frozen=True)
class LogPayload:
    text: str
    level: str = "info"


class LogEvent(DaplinkProgrammerEvent):
    def __init__(self, text: str, level: str = "info"):
        super().__init__(DaplinkProgrammerEventType.LOG)
        self.payload = LogPayload(text=text, level=level)


@dataclass(frozen=True)
class MessagePayload:
    title: str
    content: str
    level: str = "info"


class MessageEvent(DaplinkProgrammerEvent):
    def __init__(self, title: str, content: str, level: str = "info"):
        super().__init__(DaplinkProgrammerEventType.MESSAGE)
        self.payload = MessagePayload(title=title, content=content, level=level)


@dataclass(frozen=True)
class StatePayload:
    busy: bool
    action: str | None = None


class StateEvent(DaplinkProgrammerEvent):
    def __init__(self, busy: bool, action: str | None = None):
        super().__init__(DaplinkProgrammerEventType.STATE)
        self.payload = StatePayload(busy=busy, action=action)


@dataclass(frozen=True)
class DaplinkProbeInfo:
    index: int
    uid: str
    description: str
    vendor: str
    product: str
    probe_class: str


@dataclass(frozen=True)
class ProbesPayload:
    probes: list[DaplinkProbeInfo]


class ProbesEvent(DaplinkProgrammerEvent):
    def __init__(self, probes: list[DaplinkProbeInfo]):
        super().__init__(DaplinkProgrammerEventType.PROBES)
        self.payload = ProbesPayload(probes=probes)


@dataclass(frozen=True)
class DaplinkTargetInfo:
    target_name: str
    part_number: str
    vendor: str
    family: str
    flash_start: str
    flash_size: str
    flash_size_bytes: int | None
    ram_size: str
    ram_size_bytes: int | None
    pack_name: str
    pack_version: str
    pack_path: str


@dataclass(frozen=True)
class TargetsPayload:
    targets: list[DaplinkTargetInfo]
    pack_paths: list[str]


class TargetsEvent(DaplinkProgrammerEvent):
    def __init__(self, targets: list[DaplinkTargetInfo], pack_paths: list[str]):
        super().__init__(DaplinkProgrammerEventType.TARGETS)
        self.payload = TargetsPayload(targets=targets, pack_paths=pack_paths)


@dataclass(frozen=True)
class DaplinkDeviceInfo:
    probe_uid: str = "--"
    probe_description: str = "--"
    vendor: str = "--"
    product: str = "--"
    target_name: str = "--"
    part_number: str = "--"
    family: str = "--"
    flash_start: str = "--"
    flash_size: str = "--"
    ram_size: str = "--"
    pack_name: str = "--"
    pack_version: str = "--"


@dataclass(frozen=True)
class DeviceInfoPayload:
    action: str
    info: DaplinkDeviceInfo | None


class DeviceInfoEvent(DaplinkProgrammerEvent):
    def __init__(self, action: str, info: DaplinkDeviceInfo | None):
        super().__init__(DaplinkProgrammerEventType.DEVICE_INFO)
        self.payload = DeviceInfoPayload(action=action, info=info)


@dataclass(frozen=True)
class ProgressPayload:
    action: str
    percent: float


class ProgressEvent(DaplinkProgrammerEvent):
    def __init__(self, action: str, percent: float):
        super().__init__(DaplinkProgrammerEventType.PROGRESS)
        self.payload = ProgressPayload(action=action, percent=percent)


@dataclass(frozen=True)
class ActionFinishedPayload:
    action: str | None
    success: bool
    exit_code: int
    exit_status: int | None = None


class ActionFinishedEvent(DaplinkProgrammerEvent):
    def __init__(self, action: str | None, success: bool, exit_code: int, exit_status: int | None = None):
        super().__init__(DaplinkProgrammerEventType.ACTION_FINISHED)
        self.payload = ActionFinishedPayload(
            action=action,
            success=success,
            exit_code=exit_code,
            exit_status=exit_status,
        )


class DaplinkPyocdSession(QObject):
    def __init__(self, _event_receiver: Optional[QObject] = None, parent: QObject | None = None):
        super().__init__(parent)
        self._event_receiver = _event_receiver
        self._busy = False
        self._worker: threading.Thread | None = None
        self._pack_paths: list[Path] = []
        self._target_items: list[DaplinkTargetInfo] = []
        self._last_progress_value = -1.0

    def set_event_receiver(self, receiver: Optional[QObject]) -> None:
        if receiver is not None and not isinstance(receiver, QObject):
            raise TypeError("event receiver must be a QObject or None")
        self._event_receiver = receiver

    @property
    def is_busy(self) -> bool:
        return self._busy

    def shutdown(self) -> None:
        self._event_receiver = None

    def event(self, e: QEvent):
        if e.type() == int(DaplinkProgrammerEventType.REQUEST):
            payload = getattr(e, "payload", None)
            if payload is not None:
                self._handle_request(payload)
            return True
        return super().event(e)

    def _handle_request(self, payload: DaplinkRequestPayload) -> None:
        action = (payload.action or "").strip().lower()

        if action == "scan_probes":
            self._start_action("scan_probes", self._scan_probes_worker)
            return

        if action == "load_targets":
            self._start_action("load_targets", self._load_targets_worker)
            return

        if action == "connect":
            self._start_action("connect", lambda: self._connect_worker(payload.connect))
            return

        if action == "download":
            self._start_action("download", lambda: self._download_worker(payload))
            return

        self._post_event(MessageEvent("不支持的操作", f"未知操作: {payload.action}", "error"))

    def _start_action(self, action: str, worker) -> None:
        if self._busy:
            self._post_event(MessageEvent("忙碌中", "当前已有操作在执行，请稍候。", "warning"))
            return

        self._busy = True
        self._last_progress_value = -1.0
        self._post_event(StateEvent(busy=True, action=action))

        def _runner():
            success = False
            exit_code = 1
            try:
                worker()
                success = True
                exit_code = 0
            except Exception as exc:  # NOQA broad-except
                logger.exception(exc)
                self._post_event(LogEvent(str(exc), "error"))
                self._post_event(MessageEvent("执行失败", str(exc), "error"))
            finally:
                self._busy = False
                self._post_event(StateEvent(busy=False, action=action))
                self._post_event(ActionFinishedEvent(action=action, success=success, exit_code=exit_code, exit_status=None))

        self._worker = threading.Thread(target=_runner, name=f"daplink-pyocd-{action}", daemon=True)
        self._worker.start()

    def _scan_probes_worker(self) -> None:
        probes = self.scan_daplink_probes()
        self._post_event(ProbesEvent(probes))
        if probes:
            self._post_event(LogEvent(f"扫描到 {len(probes)} 个 DAPLink/CMSIS-DAP 调试器。"))
        else:
            self._post_event(LogEvent("未扫描到 DAPLink/CMSIS-DAP 调试器。", "error"))

    def _load_targets_worker(self) -> None:
        pack_paths, targets = self.discover_pack_targets()
        self._pack_paths = pack_paths
        self._target_items = targets
        self._post_event(TargetsEvent(targets, [str(path) for path in pack_paths]))

        if not pack_paths:
            self._post_event(LogEvent(f"Pack 目录为空: {self.pack_dir()}", "error"))
            return

        self._post_event(LogEvent(f"已从 {len(pack_paths)} 个 Pack 中加载 {len(targets)} 个可用 target。"))

    def _connect_worker(self, connect: DaplinkConnectConfig) -> None:
        target_info = self._target_by_name(connect.target_name)
        self._post_event(LogEvent(f"连接调试器: uid={connect.probe_uid or 'auto'} target={connect.target_name} freq={connect.frequency or '--'} mode={connect.connect_mode}"))

        with self._open_session(connect) as session:
            info = self._build_device_info(session, target_info)
            self._post_event(DeviceInfoEvent("connect", info))
            self._post_event(LogEvent(f"已连接 {info.part_number}，Pack={info.pack_name} {info.pack_version}"))

    def _download_worker(self, payload: DaplinkRequestPayload) -> None:
        if not payload.file_path or not os.path.isfile(payload.file_path):
            raise FileNotFoundError("请先选择有效的固件文件。")

        target_info = self._target_by_name(payload.connect.target_name)
        file_path = payload.file_path
        file_ext = Path(file_path).suffix.lower()
        base_address = self._resolve_download_address(payload.base_address, file_ext, target_info)

        self._post_event(LogEvent(f"开始下载: {file_path}"))
        self._post_event(LogEvent(
            f"下载参数: target={target_info.target_name} erase={payload.erase_mode} smart_flash={payload.smart_flash} trust_crc={payload.trust_crc} reset_after={payload.reset_after_download}"
        ))
        if base_address is not None:
            self._post_event(LogEvent(f"二进制基地址: 0x{base_address:08X}"))

        with self._open_session(payload.connect) as session:
            programmer = FileProgrammer(
                session,
                progress=lambda percent: self._report_progress("download", percent),
                chip_erase=payload.erase_mode or "sector",
                smart_flash=payload.smart_flash,
                trust_crc=payload.trust_crc,
                no_reset=not payload.reset_after_download,
            )

            kwargs = {}
            if base_address is not None:
                kwargs["base_address"] = base_address

            programmer.program(file_path, **kwargs)
            self._post_event(ProgressEvent("download", 100.0))

            info = self._build_device_info(session, target_info)
            self._post_event(DeviceInfoEvent("download", info))
            self._post_event(LogEvent("固件下载完成。"))

    def _open_session(self, connect: DaplinkConnectConfig):
        target_info = self._target_by_name(connect.target_name)
        options = {
            "pack": [str(path) for path in self._require_pack_paths()],
            "target_override": target_info.target_name,
            "frequency": self._parse_frequency(connect.frequency),
            "connect_mode": (connect.connect_mode or "halt").strip().lower(),
            "no_config": True,
            "hide_programming_progress": True,
        }

        session = ConnectHelper.session_with_chosen_probe(
            blocking=False,
            return_first=True,
            unique_id=connect.probe_uid or None,
            options=options,
        )
        if session is None:
            raise RuntimeError("未找到可用的 DAPLink/CMSIS-DAP 调试器。")
        return session

    def _target_by_name(self, target_name: str) -> DaplinkTargetInfo:
        for item in self._require_targets():
            if item.target_name == (target_name or "").strip().lower():
                return item
        raise RuntimeError("请选择来自本地 Pack 的有效 target。")

    def _require_targets(self) -> list[DaplinkTargetInfo]:
        if not self._target_items:
            self._pack_paths, self._target_items = self.discover_pack_targets()
        if not self._target_items:
            raise RuntimeError(f"在 {self.pack_dir()} 中未发现可用的 CMSIS-Pack target。")
        return self._target_items

    def _require_pack_paths(self) -> list[Path]:
        if not self._pack_paths:
            self._pack_paths, self._target_items = self.discover_pack_targets()
        if not self._pack_paths:
            raise RuntimeError(f"在 {self.pack_dir()} 中未找到 .pack 文件。")
        return self._pack_paths

    def _build_device_info(self, session, target_info: DaplinkTargetInfo) -> DaplinkDeviceInfo:
        probe = session.probe
        return DaplinkDeviceInfo(
            probe_uid=getattr(probe, "unique_id", "--") or "--",
            probe_description=getattr(probe, "description", "--") or "--",
            vendor=getattr(probe, "vendor_name", "--") or "--",
            product=getattr(probe, "product_name", "--") or "--",
            target_name=target_info.target_name,
            part_number=getattr(session.target, "part_number", None) or target_info.part_number,
            family=target_info.family,
            flash_start=target_info.flash_start,
            flash_size=target_info.flash_size,
            ram_size=target_info.ram_size,
            pack_name=target_info.pack_name,
            pack_version=target_info.pack_version,
        )

    def _resolve_download_address(self, base_address_text: str, file_ext: str, target_info: DaplinkTargetInfo) -> int | None:
        if file_ext != ".bin":
            return None

        text = (base_address_text or "").strip()
        if text:
            return int(text, 0)

        if target_info.flash_start and target_info.flash_start != "--":
            return int(target_info.flash_start, 16)
        return None

    def _report_progress(self, action: str, percent) -> None:
        value = float(percent)
        if value <= 1.0:
            value *= 100.0
        value = max(0.0, min(100.0, value))
        if abs(value - self._last_progress_value) < 1.0 and value not in {0.0, 100.0}:
            return
        self._last_progress_value = value
        self._post_event(ProgressEvent(action, value))

    def _post_event(self, evt: DaplinkProgrammerEvent) -> None:
        if self._event_receiver is not None:
            QCoreApplication.postEvent(self._event_receiver, evt)

    @classmethod
    def pack_dir(cls) -> Path:
        return Path(DirPathsInstance.McuPack)

    @classmethod
    def discover_pack_targets(cls) -> tuple[list[Path], list[DaplinkTargetInfo]]:
        pack_dir = cls.pack_dir()
        pack_paths = sorted(pack_dir.glob("*.pack"))
        targets_by_name: dict[str, DaplinkTargetInfo] = {}

        for pack_path in pack_paths:
            metadata = cls._read_pack_metadata(pack_path)
            cmsis_pack = CmsisPack(str(pack_path))
            for device in cmsis_pack.devices:
                target_name = normalise_target_type_name(device.part_number)
                if target_name in targets_by_name:
                    continue

                flash_region = next((region for region in device.memory_map if isinstance(region, FlashRegion)), None)
                ram_region = next((region for region in device.memory_map if isinstance(region, RamRegion)), None)
                family = " / ".join(device.families or []) or "--"
                targets_by_name[target_name] = DaplinkTargetInfo(
                    target_name=target_name,
                    part_number=device.part_number,
                    vendor=device.vendor or metadata["vendor"],
                    family=family,
                    flash_start=cls._format_address(getattr(flash_region, "start", None)),
                    flash_size=cls._format_size(getattr(flash_region, "length", None)),
                    flash_size_bytes=getattr(flash_region, "length", None),
                    ram_size=cls._format_size(getattr(ram_region, "length", None)),
                    ram_size_bytes=getattr(ram_region, "length", None),
                    pack_name=metadata["name"],
                    pack_version=metadata["version"],
                    pack_path=str(pack_path),
                )

        targets = sorted(targets_by_name.values(), key=lambda item: item.part_number.lower())
        return pack_paths, targets

    @staticmethod
    def scan_daplink_probes() -> list[DaplinkProbeInfo]:
        probes = ConnectHelper.get_all_connected_probes(blocking=False)
        items: list[DaplinkProbeInfo] = []

        for index, probe in enumerate(probes, start=1):
            if not DaplinkPyocdSession._is_supported_probe(probe):
                continue

            items.append(
                DaplinkProbeInfo(
                    index=index,
                    uid=getattr(probe, "unique_id", "") or "--",
                    description=getattr(probe, "description", "") or "--",
                    vendor=getattr(probe, "vendor_name", "") or "--",
                    product=getattr(probe, "product_name", "") or "--",
                    probe_class=probe.__class__.__name__,
                )
            )

        return items

    @staticmethod
    def _is_supported_probe(probe) -> bool:
        text = " ".join(
            str(value or "")
            for value in (
                probe.__class__.__name__,
                getattr(probe, "description", ""),
                getattr(probe, "vendor_name", ""),
                getattr(probe, "product_name", ""),
            )
        ).lower()
        return "cmsis" in text or "daplink" in text

    @staticmethod
    def _read_pack_metadata(pack_path: Path) -> dict[str, str]:
        default_name = pack_path.stem
        default_version = "--"
        default_vendor = "--"

        try:
            with zipfile.ZipFile(pack_path) as zf:
                pdsc_name = next(name for name in zf.namelist() if name.lower().endswith(".pdsc"))
                with zf.open(pdsc_name) as pdsc_file:
                    root = ET.parse(pdsc_file).getroot()
        except Exception:  # NOQA broad-except
            return {
                "name": default_name,
                "version": default_version,
                "vendor": default_vendor,
            }

        return {
            "name": (root.findtext("name") or default_name).strip(),
            "version": (root.findtext("release") or default_version).strip(),
            "vendor": (root.findtext("vendor") or default_vendor).strip(),
        }

    @staticmethod
    def _parse_frequency(text: str) -> int:
        value = (text or "").strip().lower().replace("hz", "")
        if not value:
            return 1000000

        scale = 1
        if value.endswith("k"):
            scale = 1000
            value = value[:-1]
        elif value.endswith("m"):
            scale = 1000 * 1000
            value = value[:-1]

        return int(float(value) * scale)

    @staticmethod
    def _format_size(size_bytes: int | None) -> str:
        if not size_bytes:
            return "--"
        if size_bytes % (1024 * 1024) == 0:
            return f"{size_bytes // (1024 * 1024)} MB"
        if size_bytes % 1024 == 0:
            return f"{size_bytes // 1024} KB"
        return f"{size_bytes} B"

    @staticmethod
    def _format_address(address: int | None) -> str:
        if address is None:
            return "--"
        return f"0x{address:08X}"

