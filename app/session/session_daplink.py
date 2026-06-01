# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 04-25 13:15
#  @FileName: session_daplink.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : Powered By GPT-5.4
#  @Python  :
# -------------------------------

from __future__ import annotations

import os
import re
import sys
import zipfile
from dataclasses import dataclass, field
from enum import IntEnum
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from xml.etree import ElementTree as ET

from PyQt5.QtCore import QCoreApplication, QEvent, QObject, QProcess, QThread, QTimer, pyqtSignal

from config import CTX, logger

DAPLINK_FLASH_TIMEOUT_MS = 5 * 60 * 1000
PYOCD_PROGRESS_PHASE_RANGES = {
    "erase": (0.0, 20.0),
    "program": (20.0, 100.0),
}
PYOCD_DEFAULT_PROGRESS_STEPS = 40
SUPPORTED_TARGET_KEYWORDS = ("g474", "h743", "h750")
SUPPORTED_PACK_NAME_KEYWORDS = ("g474", "h743", "h750")
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
PYOCD_PROGRESS_FRAGMENT_RE = re.compile(r"^[\[\]\-=|\s]+$")


def _install_pyocd_probe_filter() -> None:
    import importlib_metadata

    if getattr(importlib_metadata, "_f4cp_pyocd_probe_filter_installed", False):
        return

    original_entry_points = importlib_metadata.entry_points
    allowed_probe_plugins = {"cmsisdap"}
    allowed_rtos_plugins: set[str] = set()

    def filtered_entry_points(*args, **kwargs):
        """
        屏蔽pyocd中的一些模块
        """
        group = kwargs.get("group")
        entry_points = original_entry_points(*args, **kwargs)
        if group == "pyocd.probe":
            return [entry_point for entry_point in entry_points if entry_point.name.lower() in allowed_probe_plugins]
        if group == "pyocd.rtos":
            return [entry_point for entry_point in entry_points if entry_point.name.lower() in allowed_rtos_plugins]
        return entry_points

    importlib_metadata.entry_points = filtered_entry_points
    importlib_metadata._f4cp_pyocd_probe_filter_installed = True


@lru_cache(maxsize=1)
def _pyocd_api() -> SimpleNamespace:
    _install_pyocd_probe_filter()

    from pyocd.core.helpers import ConnectHelper
    from pyocd.core.memory_map import FlashRegion, RamRegion
    from pyocd.flash.file_programmer import FileProgrammer
    from pyocd.target.pack.cmsis_pack import CmsisPack
    from pyocd.target.pack.pack_target import normalise_target_type_name

    return SimpleNamespace(
        ConnectHelper=ConnectHelper,
        FlashRegion=FlashRegion,
        RamRegion=RamRegion,
        FileProgrammer=FileProgrammer,
        CmsisPack=CmsisPack,
        normalise_target_type_name=normalise_target_type_name,
    )


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
    silent: bool = False


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


class DaplinkActionThread(QThread):
    resultReady = pyqtSignal(str, bool, int)

    def __init__(self, action: str, session: "DaplinkPyocdSession", worker, parent: QObject | None = None):
        super().__init__(parent)
        self.action = action
        self.session = session
        self.worker = worker

    def run(self) -> None:
        success = False
        exit_code = 1
        try:
            self.worker()
            success = True
            exit_code = 0
        except Exception as exc:  # NOQA broad-except
            logger.exception(exc)
            message = self.session._format_worker_error(exc)
            self.session._post_event(LogEvent(message, "error"))
            self.session._post_event(MessageEvent("执行失败", message, "error"))
        self.resultReady.emit(self.action, success, exit_code)


class DaplinkPyocdSession(QObject):
    _dirs: "DirPaths | None" = None

    @classmethod
    def set_dirs(cls, dirs: "DirPaths | None"):
        """Inject DirPaths for test isolation; None reverts to default singleton."""
        cls._dirs = dirs

    @classmethod
    def _resolve_dirs(cls) -> "DirPaths":
        return cls._dirs if cls._dirs is not None else CTX.dirs

    def __init__(self, _event_receiver: Optional[QObject] = None, parent: QObject | None = None):
        super().__init__(parent)
        self._event_receiver = _event_receiver
        self._busy = False
        self._worker: DaplinkActionThread | None = None
        self._process: QProcess | None = None
        self._process_action: str | None = None
        self._process_timeout_timer = QTimer(self)
        self._process_timeout_timer.setSingleShot(True)
        self._process_timeout_timer.timeout.connect(self._kill_process_on_timeout)
        self._process_start_timeout_timer = QTimer(self)
        self._process_start_timeout_timer.setSingleShot(True)
        self._process_start_timeout_timer.timeout.connect(
            self._handle_process_start_timeout
        )
        self._pack_paths: list[Path] = []
        self._target_items: list[DaplinkTargetInfo] = []
        self._last_progress_value = -1.0
        self._process_line_buffer = ""
        self._process_progress_phase: str | None = None
        self._process_progress_total_steps = PYOCD_DEFAULT_PROGRESS_STEPS
        self._process_started = False

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
            self._start_action(
                "load_targets",
                lambda: self._load_targets_worker(payload.silent),
                silent=payload.silent,
            )
            return

        if action == "connect":
            self._start_action("connect", lambda: self._connect_worker(payload.connect))
            return

        if action == "download":
            self._start_download_process(payload)
            return

        self._post_event(MessageEvent("不支持的操作", f"未知操作: {payload.action}", "error"))

    def _start_action(self, action: str, worker, silent: bool = False) -> None:
        if self._busy:
            self._post_event(MessageEvent("忙碌中", "当前已有操作在执行，请稍候。", "warning"))
            return

        self._busy = True
        self._last_progress_value = -1.0
        if not silent:
            self._post_event(StateEvent(busy=True, action=action))

        self._worker = DaplinkActionThread(action, self, worker)
        if silent:
            self._worker.resultReady.connect(self._finish_action_silent)
        else:
            self._worker.resultReady.connect(self._finish_action)
        self._worker.finished.connect(self._cleanup_worker)
        self._worker.start()

    def _finish_action_silent(self, _action: str, _success: bool, _exit_code: int) -> None:
        self._busy = False

    def _reset_process_output_state(self) -> None:
        self._process_line_buffer = ""
        self._process_progress_phase = None
        self._process_progress_total_steps = PYOCD_DEFAULT_PROGRESS_STEPS

    def _finish_action(self, action: str, success: bool, exit_code: int) -> None:
        self._busy = False
        self._post_event(StateEvent(busy=False, action=action))
        self._post_event(ActionFinishedEvent(action=action, success=success, exit_code=exit_code, exit_status=None))

    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def _start_download_process(self, payload: DaplinkRequestPayload) -> None:
        if self._busy:
            self._post_event(MessageEvent("忙碌中", "当前已有操作在执行，请稍候。", "warning"))
            return

        if not payload.file_path or not os.path.isfile(payload.file_path):
            self._post_event(MessageEvent("固件无效", "请先选择有效的固件文件。", "warning"))
            return

        self._busy = True
        self._last_progress_value = -1.0
        self._reset_process_output_state()
        self._process_action = "download"
        self._post_event(StateEvent(busy=True, action="download"))
        self._post_event(ProgressEvent("download", 0.0))

        try:
            target_info = self._target_by_name(payload.connect.target_name)
            args = self._build_pyocd_flash_args(payload, target_info)
            program, prefix_args = self._pyocd_command()
            process_args = [*prefix_args, *args]
        except Exception as exc:
            self._busy = False
            self._process_action = None
            self._post_event(StateEvent(busy=False, action="download"))
            self._post_event(MessageEvent("执行失败", str(exc), "error"))
            self._post_event(ActionFinishedEvent(action="download", success=False, exit_code=1, exit_status=None))
            return

        self._process = QProcess(self)
        self._process_started = False
        self._process.setProgram(program)
        self._process.setArguments(process_args)
        self._process.setWorkingDirectory(str(self._resolve_dirs().BaseDir))
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.started.connect(self._handle_process_started)
        self._process.readyReadStandardOutput.connect(self._read_process_output)
        self._process.finished.connect(self._handle_process_finished)
        self._process.errorOccurred.connect(self._handle_process_error)

        command_text = " ".join([self._process.program(), *process_args])
        self._post_event(LogEvent(f"pyOCD: {command_text}", "command"))
        self._process_start_timeout_timer.start(3000)
        self._process.start()

    def _handle_process_started(self) -> None:
        if self._process_action is None:
            return
        self._process_started = True
        self._process_start_timeout_timer.stop()
        self._process_timeout_timer.start(DAPLINK_FLASH_TIMEOUT_MS)

    def _handle_process_start_timeout(self) -> None:
        if self._process is None or self._process_action is None or self._process_started:
            return
        error_text = self._process.errorString() or "超时未启动"
        self._finish_process_action(False, 1, f"pyOCD 启动失败: {error_text}")

    def _build_pyocd_flash_args(self, payload: DaplinkRequestPayload, target_info: DaplinkTargetInfo) -> list[str]:
        file_path = str(Path(payload.file_path or "").resolve())
        file_ext = Path(file_path).suffix.lower().lstrip(".")
        base_address = self._resolve_download_address(payload.base_address, f".{file_ext}", target_info)
        connect_mode = (payload.connect.connect_mode or "under-reset").strip().lower()
        if connect_mode == "attach":
            connect_mode = "under-reset"
        frequency = str(self._parse_frequency(payload.connect.frequency))

        args = [
            "flash",
            "--no-config",
            "--pack",
            target_info.pack_path,
            "-t",
            target_info.target_name,
            "-f",
            frequency,
            "-M",
            connect_mode,
            "-e",
            payload.erase_mode or "sector",
            "--format",
            file_ext or "hex",
        ]
        if payload.connect.probe_uid:
            args.extend(["-u", payload.connect.probe_uid])
        if base_address is not None:
            args.extend(["-a", f"0x{base_address:08X}"])
        if payload.trust_crc:
            args.append("--trust-crc")
        if not payload.reset_after_download:
            args.append("--no-reset")
        args.append(file_path)
        return args

    def _read_process_output(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._consume_process_output_chunk(data)

    def _consume_process_output_chunk(self, data: str) -> None:
        if not data:
            return

        clean_data = self._strip_ansi(data)
        if not clean_data:
            return

        for char in clean_data:
            if char in "\r\n":
                self._flush_process_line_buffer()
                continue
            self._process_line_buffer += char

        self._consume_live_progress_fragment(self._process_line_buffer)

    def _flush_process_line_buffer(self) -> None:
        line = self._process_line_buffer.strip()
        self._process_line_buffer = ""
        if not line:
            return
        if self._consume_process_output_line(line):
            return
        self._post_event(LogEvent(line))

    def _consume_process_output_line(self, line: str) -> bool:
        text = self._strip_ansi(line).strip()
        if not text:
            return True

        lowered = text.lower()
        if "erasing..." in lowered:
            self._process_progress_phase = "erase"
            self._report_progress("download", PYOCD_PROGRESS_PHASE_RANGES["erase"][0])
            return False
        if "programming..." in lowered:
            self._process_progress_phase = "program"
            self._report_progress("download", PYOCD_PROGRESS_PHASE_RANGES["program"][0])
            return False

        if self._update_progress_template(text):
            return True
        if self._update_progress_from_fragment(text):
            return True
        return False

    def _consume_live_progress_fragment(self, line: str) -> None:
        text = self._strip_ansi(line).strip()
        if not text:
            return
        self._update_progress_template(text)
        self._update_progress_from_fragment(text)

    def _update_progress_template(self, text: str) -> bool:
        if not self._looks_like_progress_fragment(text):
            return False
        if "-" not in text:
            return False

        slots = self._count_progress_slots(text)
        if slots > 0:
            self._process_progress_total_steps = slots
        return True

    def _update_progress_from_fragment(self, text: str) -> bool:
        if not self._looks_like_progress_fragment(text):
            return False
        if self._process_progress_phase not in PYOCD_PROGRESS_PHASE_RANGES:
            return True

        filled_steps = text.count("=")
        total_steps = max(self._process_progress_total_steps, filled_steps, 1)
        if "]" in text:
            filled_steps = total_steps

        start, end = PYOCD_PROGRESS_PHASE_RANGES[self._process_progress_phase]
        ratio = min(1.0, filled_steps / total_steps)
        self._report_progress("download", start + (end - start) * ratio)
        return True

    @staticmethod
    def _count_progress_slots(text: str) -> int:
        return sum(1 for char in text if char in "-=")

    @staticmethod
    def _looks_like_progress_fragment(text: str) -> bool:
        return bool(PYOCD_PROGRESS_FRAGMENT_RE.fullmatch(text))

    @staticmethod
    def _strip_ansi(text: str) -> str:
        return ANSI_ESCAPE_RE.sub("", text)

    def _handle_process_finished(self, exit_code: int, exit_status) -> None:
        if self._process_action is None:
            return
        self._process_started = False
        self._process_start_timeout_timer.stop()
        self._process_timeout_timer.stop()
        self._flush_process_line_buffer()
        success = exit_code == 0
        message = "固件下载完成。" if success else f"pyOCD 下载失败，退出码: {exit_code}"
        self._finish_process_action(success, exit_code, message)

    def _handle_process_error(self, error) -> None:
        if self._process is None or self._process_action is None:
            return
        error_text = self._process.errorString()
        self._post_event(LogEvent(f"pyOCD process error: {error_text}", "error"))
        if not self._process_started:
            self._process_start_timeout_timer.stop()
            self._process_timeout_timer.stop()
            self._finish_process_action(False, 1, f"pyOCD 启动失败: {error_text}")

    def _kill_process_on_timeout(self) -> None:
        if self._process is None:
            return
        self._post_event(LogEvent("pyOCD 下载超时，正在终止进程。", "error"))
        self._process.kill()

    def _finish_process_action(self, success: bool, exit_code: int, message: str) -> None:
        action = self._process_action or "download"
        self._process_started = False
        self._process_start_timeout_timer.stop()
        self._process_timeout_timer.stop()
        if self._process is not None:
            self._process.deleteLater()
            self._process = None
        self._process_action = None
        self._busy = False
        self._post_event(LogEvent(message, None if success else "error"))
        if success:
            self._post_event(ProgressEvent(action, 100.0))
        else:
            self._post_event(MessageEvent("执行失败", message, "error"))
        self._post_event(StateEvent(busy=False, action=action))
        self._post_event(ActionFinishedEvent(action=action, success=success, exit_code=exit_code, exit_status=None))

    @staticmethod
    def _pyocd_command() -> tuple[str, list[str]]:
        python_executable = Path(sys.executable)
        if python_executable.name.lower() in {"python.exe", "pythonw.exe", "python"}:
            return str(python_executable), ["-m", "pyocd"]

        # frozen (cx_Freeze): use the bundled pyocd console launcher
        # so that F4CP GUI is not re-spawned as a side-effect.
        if getattr(sys, "frozen", False):
            launcher = python_executable.with_name("pyocd.exe")
            if launcher.exists():
                return str(launcher), []

        executable = Path(sys.executable).with_name("pyocd.exe")
        if executable.exists():
            return str(executable), []
        return "pyocd", []

    def _scan_probes_worker(self) -> None:
        probes = self.scan_daplink_probes()
        self._post_event(ProbesEvent(probes))
        if probes:
            self._post_event(LogEvent(f"扫描到 {len(probes)} 个 DAPLink/CMSIS-DAP 调试器。"))
        else:
            self._post_event(LogEvent("未扫描到 DAPLink/CMSIS-DAP 调试器。", "error"))

    def _load_targets_worker(self, silent: bool = False) -> None:
        pack_paths, targets = self.discover_pack_targets()
        self._pack_paths = pack_paths
        self._target_items = targets
        self._post_event(TargetsEvent(targets, [str(path) for path in pack_paths]))

        if silent:
            return

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
        pyocd_api = _pyocd_api()

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
            programmer = pyocd_api.FileProgrammer(
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
        pyocd_api = _pyocd_api()
        target_info = self._target_by_name(connect.target_name)
        options = {
            "pack": [str(path) for path in self._require_pack_paths()],
            "target_override": target_info.target_name,
            "frequency": self._parse_frequency(connect.frequency),
            "connect_mode": (connect.connect_mode or "halt").strip().lower(),
            "no_config": True,
            "rtos.enable": False,
            "hide_programming_progress": True,
        }

        session = pyocd_api.ConnectHelper.session_with_chosen_probe(
            blocking=False,
            return_first=True,
            unique_id=connect.probe_uid or None,
            options=options,
        )
        if session is None:
            message = "未找到可用的 DAPLink/CMSIS-DAP 调试器。"
            logger.error(f"{self.__class__.__name__}: {message}")
            raise RuntimeError(message)
        return session

    def _target_by_name(self, target_name: str) -> DaplinkTargetInfo:
        for item in self._require_targets():
            if item.target_name == (target_name or "").strip().lower():
                return item
        message = "请选择来自本地 Pack 的有效 target。"
        logger.error(f"{self.__class__.__name__}: {message}")
        raise RuntimeError(message)

    def _require_targets(self) -> list[DaplinkTargetInfo]:
        if not self._target_items:
            self._pack_paths, self._target_items = self.discover_pack_targets()
        if not self._target_items:
            message = f"在 {self.pack_dir()} 中未发现可用的 CMSIS-Pack target。"
            logger.error(f"{self.__class__.__name__}: {message}")
            raise RuntimeError(message)
        return self._target_items

    def _require_pack_paths(self) -> list[Path]:
        if not self._pack_paths:
            self._pack_paths, self._target_items = self.discover_pack_targets()
        if not self._pack_paths:
            message = f"在 {self.pack_dir()} 中未找到 .pack 文件。"
            logger.error(f"{self.__class__.__name__}: {message}")
            raise RuntimeError(message)
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

    @staticmethod
    def _format_worker_error(exc: Exception) -> str:
        text = str(exc) or exc.__class__.__name__
        lowered = text.lower()
        if "read error" in lowered or "i/o" in lowered or "hid" in lowered:
            return (
                "DAPLink I/O read error. Close the serial session for this devices, "
                "replug DAPLink, lower SWD frequency, then try again."
            )
        return text

    @classmethod
    def pack_dir(cls) -> Path:
        return Path(cls._resolve_dirs().McuPackDir)

    @classmethod
    def discover_pack_targets(cls) -> tuple[list[Path], list[DaplinkTargetInfo]]:
        pyocd_api = _pyocd_api()
        pack_dir = cls.pack_dir()
        pack_paths = cls._candidate_pack_paths(pack_dir)
        used_pack_paths: set[Path] = set()
        targets_by_name: dict[str, DaplinkTargetInfo] = {}

        for pack_path in pack_paths:
            metadata = cls._read_pack_metadata(pack_path)
            try:
                cmsis_pack = pyocd_api.CmsisPack(str(pack_path))
            except Exception as exc:  # NOQA broad-except
                logger.warning(f"Skip invalid CMSIS Pack {pack_path}: {exc}")
                continue

            for device in cmsis_pack.devices:
                target_name = pyocd_api.normalise_target_type_name(device.part_number)
                if target_name in targets_by_name:
                    continue
                if not cls._is_supported_target(device.part_number, target_name, device.families):
                    continue

                flash_region = next((region for region in device.memory_map if isinstance(region, pyocd_api.FlashRegion)), None)
                ram_region = next((region for region in device.memory_map if isinstance(region, pyocd_api.RamRegion)), None)
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
                used_pack_paths.add(pack_path)

        targets = sorted(targets_by_name.values(), key=lambda item: item.part_number.lower())
        return sorted(used_pack_paths), targets

    @staticmethod
    def scan_daplink_probes() -> list[DaplinkProbeInfo]:
        probes = _pyocd_api().ConnectHelper.get_all_connected_probes(blocking=False)
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

    @classmethod
    def _candidate_pack_paths(cls, pack_dir: Path) -> list[Path]:
        if not pack_dir.is_dir():
            return []

        all_pack_paths = sorted(pack_dir.glob("*.pack"))
        filtered = [
            path for path in all_pack_paths
            if any(keyword in path.name.lower() for keyword in SUPPORTED_PACK_NAME_KEYWORDS)
        ]
        return filtered or all_pack_paths

    @staticmethod
    def _is_supported_target(part_number: str, target_name: str, families) -> bool:
        text = " ".join(
            [
                part_number or "",
                target_name or "",
                " ".join(families or []),
            ]
        ).lower()
        return any(keyword in text for keyword in SUPPORTED_TARGET_KEYWORDS)

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
