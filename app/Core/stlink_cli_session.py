# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-14 14:13
#  @FileName: stlink_cli_session.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : Powered By GPT-5.4
#  @Python  :
# -------------------------------

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from PyQt5.QtCore import QCoreApplication, QEvent, QObject, QProcess

from Config import DirPathsInstance


def defaultStm32ProgrammerCliPath() -> str:
    return os.path.join(
        DirPathsInstance.ST_LINKDir, "ST-LINK_CLI.exe")

class Stm32ProgrammerEventType(IntEnum):
    REQUEST = QEvent.registerEventType()
    LOG = QEvent.registerEventType()
    MESSAGE = QEvent.registerEventType()
    STATE = QEvent.registerEventType()
    PROBES = QEvent.registerEventType()
    DEVICE_INFO = QEvent.registerEventType()
    CHECKSUM = QEvent.registerEventType()
    MEMORY = QEvent.registerEventType()
    ACTION_FINISHED = QEvent.registerEventType()


class Stm32ProgrammerEvent(QEvent):
    def __init__(self, etype: Stm32ProgrammerEventType):
        super().__init__(QEvent.Type(int(etype)))
        self.timestamp = time.monotonic()


@dataclass(frozen=True)
class Stm32ConnectConfig:
    probe_sn: str | None = None
    freq: str = ""
    mode: str = "NORMAL"
    reset: str = "SWrst"  # NOQA


@dataclass(frozen=True)
class Stm32RequestPayload:
    action: str
    connect: Stm32ConnectConfig = field(default_factory=Stm32ConnectConfig)
    file_path: str | None = None
    address: str = ""
    size: int | None = None
    count: int | None = None
    save_path: str | None = None
    verify: bool = False
    skip_erase: bool = False
    reset_after_download: bool = False


class Stm32RequestEvent(Stm32ProgrammerEvent):
    def __init__(self, payload: Stm32RequestPayload):
        super().__init__(Stm32ProgrammerEventType.REQUEST)
        self.payload = payload


@dataclass(frozen=True)
class LogPayload:
    text: str
    level: str = "info"


class LogEvent(Stm32ProgrammerEvent):
    def __init__(self, text: str, level: str = "info"):

        super().__init__(Stm32ProgrammerEventType.LOG)
        self.payload = LogPayload(text=text, level=level)


@dataclass(frozen=True)
class MessagePayload:
    title: str
    content: str
    level: str = "info"


class MessageEvent(Stm32ProgrammerEvent):
    def __init__(self, title: str, content: str, level: str = "info"):
        super().__init__(Stm32ProgrammerEventType.MESSAGE)
        self.payload = MessagePayload(title=title, content=content, level=level)


@dataclass(frozen=True)
class StatePayload:
    busy: bool
    action: str | None = None


class StateEvent(Stm32ProgrammerEvent):
    def __init__(self, busy: bool, action: str | None = None):
        super().__init__(Stm32ProgrammerEventType.STATE)
        self.payload = StatePayload(busy=busy, action=action)


@dataclass(frozen=True)
class Stm32ProbeInfo:
    index: str
    sn: str
    fw: str
    ap: str
    board: str


@dataclass(frozen=True)
class ProbesPayload:
    probes: list[Stm32ProbeInfo]


class ProbesEvent(Stm32ProgrammerEvent):
    def __init__(self, probes: list[Stm32ProbeInfo]):
        super().__init__(Stm32ProgrammerEventType.PROBES)
        self.payload = ProbesPayload(probes=probes)


@dataclass(frozen=True)
class Stm32DeviceInfo:
    probe_sn: str = "--"
    probe_fw: str = "--"
    board: str = "--"
    voltage: str = "--"
    swd_freq: str = "--"
    connect_mode: str = "--"
    reset_mode: str = "--"
    device_id: str = "--"
    revision: str = "--"
    device_name: str = "--"
    flash_size: str = "--"
    flash_size_bytes: int | None = None
    device_type: str = "--"
    cpu: str = "--"
    bl_version: str = "--"


@dataclass(frozen=True)
class DeviceInfoPayload:
    action: str
    info: Stm32DeviceInfo | None


class DeviceInfoEvent(Stm32ProgrammerEvent):
    def __init__(self, action: str, info: Stm32DeviceInfo | None):
        super().__init__(Stm32ProgrammerEventType.DEVICE_INFO)
        self.payload = DeviceInfoPayload(action=action, info=info)


@dataclass(frozen=True)
class ChecksumPayload:
    checksum: str | None


class ChecksumEvent(Stm32ProgrammerEvent):
    def __init__(self, checksum: str | None):
        super().__init__(Stm32ProgrammerEventType.CHECKSUM)
        self.payload = ChecksumPayload(checksum=checksum)


@dataclass(frozen=True)
class Stm32MemoryValue:
    address: str
    value: str


@dataclass(frozen=True)
class MemoryPayload:
    values: list[Stm32MemoryValue]


class MemoryEvent(Stm32ProgrammerEvent):
    def __init__(self, values: list[Stm32MemoryValue]):
        super().__init__(Stm32ProgrammerEventType.MEMORY)
        self.payload = MemoryPayload(values=values)


@dataclass(frozen=True)
class ActionFinishedPayload:
    action: str | None
    success: bool
    exit_code: int
    exit_status: int | None = None


class ActionFinishedEvent(Stm32ProgrammerEvent):
    def __init__(self, action: str | None, success: bool, exit_code: int, exit_status: int | None = None):
        super().__init__(Stm32ProgrammerEventType.ACTION_FINISHED)
        self.payload = ActionFinishedPayload(
            action=action,
            success=success,
            exit_code=exit_code,
            exit_status=exit_status,
        )


class Stm32ProgrammerSession(QObject):
    FLASH_BASE_ADDRESS = "0x08000000"

    def __init__(self, exe_path: str | None = None, _event_receiver: Optional[QObject] = None, parent: QObject | None = None):
        super().__init__(parent)
        self.exe_path = exe_path or defaultStm32ProgrammerCliPath()
        self._event_receiver = _event_receiver
        self._current_action: str | None = None
        self._current_command: list[str] = []
        self._output_buffer = ""
        self._stderr_buffer = ""

        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)
        self.process.errorOccurred.connect(self.process_error)

    def set_event_receiver(self, receiver: Optional[QObject]) -> None:
        if receiver is not None and not isinstance(receiver, QObject):
            raise TypeError("event receiver must be a QObject or None")
        self._event_receiver = receiver

    @property
    def is_busy(self) -> bool:
        return self.process.state() != QProcess.ProcessState.NotRunning

    def shutdown(self) -> None:
        if self.process.state() == QProcess.ProcessState.NotRunning:
            return

        self.process.kill()
        self.process.waitForFinished(1000)
        self._current_action = None
        self._current_command = []
        self._output_buffer = ""
        self._stderr_buffer = ""

    def event(self, e: QEvent):
        if e.type() == int(Stm32ProgrammerEventType.REQUEST):
            payload = getattr(e, "payload", None)
            if payload is not None:
                self._handle_request(payload)
            return True
        return super().event(e)

    def _handle_request(self, payload: Stm32RequestPayload) -> None:
        action = (payload.action or "").strip().lower()

        try:
            if action == "scan":
                self._start_action("scan", self._build_common_arguments() + ["-List"])
                return

            if action == "connect":
                self._start_action("connect", self._build_connect_arguments(payload.connect))
                return

            if action == "download":
                if not payload.file_path or not os.path.isfile(payload.file_path):
                    self._post_event(MessageEvent("无效固件", "请先选择有效的固件文件。", "warning"))
                    return

                args = self._build_connect_arguments(payload.connect)
                args.extend(self._build_program_arguments(payload.file_path, payload.address, payload.skip_erase, payload.verify))
                if payload.reset_after_download:
                    args.append(self._reset_command(payload.connect.reset))

                self._start_action("download", args)
                return

            if action == "upload":
                if not payload.save_path:
                    self._post_event(MessageEvent("缺少保存路径", "请先选择固件读取后的保存路径。", "warning"))
                    return
                if payload.size is None or payload.size <= 0:
                    self._post_event(MessageEvent("读取大小无效", "请输入十进制或十六进制的读取大小。", "warning"))
                    return

                address = payload.address or self.FLASH_BASE_ADDRESS
                args = self._build_connect_arguments(payload.connect)
                args.extend(["-Dump", address, str(payload.size), payload.save_path])
                self._start_action("upload", args)
                return

            if action == "checksum":
                if payload.size is None or payload.size <= 0:
                    self._post_event(MessageEvent("校验范围无效", "请先连接 MCU 以读取 Flash 大小。", "warning"))
                    return

                address = payload.address or self.FLASH_BASE_ADDRESS
                args = self._build_connect_arguments(payload.connect)
                args.extend(["-Cksum", address, str(payload.size)])
                self._start_action("checksum", args)
                return

            if action == "read_memory":
                if payload.count is None or payload.count <= 0:
                    self._post_event(MessageEvent("读取数量无效", "32-bit 数量请输入正整数。", "warning"))
                    return

                address = payload.address or self.FLASH_BASE_ADDRESS
                args = self._build_connect_arguments(payload.connect)
                args.extend(["-r32", address, str(payload.count)])
                self._start_action("read_memory", args)
                return

            self._post_event(MessageEvent("不支持的操作", f"未知操作: {payload.action}", "error"))
        except Exception as exc:
            self._post_event(MessageEvent("执行失败", str(exc), "error"))

    def _build_connect_arguments(self, connect: Stm32ConnectConfig | None) -> list[str]:  # NOQA
        connect = connect or Stm32ConnectConfig()
        args = self._build_common_arguments() + ["-c"]

        if connect.probe_sn:
            args.append(f"SN={connect.probe_sn}")

        args.append("SWD")

        freq = (connect.freq or "").strip()
        if freq:
            args.append(f"Freq={freq}")

        mode = (connect.mode or "").strip().upper()
        if mode in {"UR", "HOTPLUG"}:
            args.append(mode)

        reset = self._connect_reset_token(connect.reset)
        if reset:
            args.append(reset)

        return args

    @staticmethod
    def _build_common_arguments() -> list[str]:
        return ["-Q", "-NoPrompt"]

    def _build_program_arguments(self, file_path: str, address: str, skip_erase: bool, verify: bool) -> list[str]:
        args = ["-P", file_path]

        if address and self._should_append_address(file_path):
            args.append(address)
        if skip_erase:
            args.append("ske")
        if not verify:
            args.append("skpv")
        return args

    @staticmethod
    def _should_append_address(file_path: str) -> bool:
        return os.path.splitext(file_path)[1].lower() == ".bin"

    @staticmethod
    def _connect_reset_token(reset: str | None) -> str | None:
        mapping = {
            "SWRST": "Srst",
            "HWRST": "Hrst",
            "CRST": "Crst",
        }
        return mapping.get((reset or "").strip().upper())

    @staticmethod
    def _reset_command(reset: str | None) -> str:
        return "-HardRst" if (reset or "").strip().upper() == "HWRST" else "-Rst"

    def _start_action(self, action: str, args: list[str]) -> None:
        if self.is_busy:
            self._post_event(MessageEvent("忙碌中", "当前已有操作在执行，请稍候。", "warning"))
            return

        if not os.path.exists(self.exe_path):
            self._post_event(MessageEvent("CLI 不存在", "未找到 ST-LINK_CLI.exe。", "error"))
            self._post_event(LogEvent(f"ST-LINK CLI not found: {self.exe_path}", "error"))
            return

        self._current_action = action
        self._current_command = [self.exe_path, *args]
        self._output_buffer = ""
        self._stderr_buffer = ""

        self._post_event(StateEvent(busy=True, action=action))
        self._post_event(LogEvent("=" * 72))
        self._post_event(LogEvent(f"[{action}] {' '.join(self._current_command)}", "command"))
        self.process.start(self.exe_path, args)

    def handle_stdout(self) -> None:
        data = self.process.readAllStandardOutput()
        text = data.data().decode("utf-8", errors="replace")
        if not text:
            return

        self._output_buffer += text
        self._post_event(LogEvent(text.rstrip()))

    def handle_stderr(self) -> None:
        data = self.process.readAllStandardError()
        text = data.data().decode("utf-8", errors="replace")
        if not text:
            return

        self._stderr_buffer += text
        self._post_event(LogEvent(text.rstrip(), "error"))

    def process_error(self, error) -> None:
        action = self._current_action
        if action is None:
            return

        message = self.process.errorString() or f"QProcess error: {error}"
        self._post_event(StateEvent(busy=False, action=action))
        self._post_event(MessageEvent("执行失败", message, "error"))
        self._post_event(ActionFinishedEvent(action=action, success=False, exit_code=int(error), exit_status=None))
        self._current_action = None
        self._current_command = []

    def process_finished(self, exitCode, exitStatus) -> None:
        action = self._current_action
        if action is None:
            return

        self._post_event(StateEvent(busy=False, action=action))
        success = exitCode == 0

        if success:
            if action == "scan":
                self._post_event(ProbesEvent(self._parse_scan_results(self._output_buffer)))
            elif action in {"connect", "download"}:
                self._post_event(DeviceInfoEvent(action, self._extract_device_info(self._output_buffer)))
            elif action == "checksum":
                self._post_event(ChecksumEvent(self._extract_checksum(self._output_buffer)))
            elif action == "read_memory":
                self._post_event(MemoryEvent(self._extract_memory_values(self._output_buffer)))

        self._post_event(
            ActionFinishedEvent(
                action=action,
                success=success,
                exit_code=int(exitCode),
                exit_status=int(exitStatus),
            )
        )
        self._current_action = None
        self._current_command = []

    def _post_event(self, evt: Stm32ProgrammerEvent) -> None:
        if self._event_receiver is not None:
            QCoreApplication.postEvent(self._event_receiver, evt)

    @staticmethod
    def _parse_scan_results(text: str) -> list[Stm32ProbeInfo]:
        pattern = re.compile(
            r"ST-LINK Probe\s+(?P<index>\d+)\s*:\s*"
            r".*?SN\s*:\s*(?P<sn>[^\r\n]+)"
            r".*?FW\s*:\s*(?P<fw>[^\r\n]*)",
            re.S,
        )

        probes: list[Stm32ProbeInfo] = []
        for match in pattern.finditer(text):
            probes.append(
                Stm32ProbeInfo(
                    index=match.group("index").strip(),
                    sn=match.group("sn").strip(),
                    fw=match.group("fw").strip(),
                    ap="--",
                    board="--",
                )
            )
        return probes

    @classmethod
    def _extract_device_info(cls, text: str) -> Stm32DeviceInfo | None:
        def _extract(pattern: str) -> str | None:
            match = re.search(pattern, text, re.MULTILINE)
            return match.group(1).strip() if match else None

        probe_sn = _extract(r"^ST-LINK SN\s*:\s*(.+)$")
        probe_fw = _extract(r"^ST-LINK Firmware version\s*:\s*(.+)$")
        voltage = _extract(r"^Target voltage\s*=\s*(.+)$")
        swd_freq = _extract(r"^SWD Frequency\s*=\s*(.+)$")
        connect_mode = _extract(r"^Connection mode\s*:\s*(.+)$")
        reset_mode = _extract(r"^Reset mode\s*:\s*(.+)$")
        device_id = _extract(r"^Device ID\s*:\s*(.+)$")
        flash_size = _extract(r"^Device flash Size\s*:\s*(.+)$")
        device_name = _extract(r"^Device family\s*:\s*(.+)$")

        if not any((probe_sn, probe_fw, voltage, swd_freq, connect_mode, reset_mode, device_id, flash_size, device_name)):
            return None

        flash_size = flash_size or "--"
        return Stm32DeviceInfo(
            probe_sn=probe_sn or "--",
            probe_fw=probe_fw or "--",
            board="--",
            voltage=voltage or "--",
            swd_freq=swd_freq or "--",
            connect_mode=connect_mode or "--",
            reset_mode=reset_mode or "--",
            device_id=device_id or "--",
            revision="--",
            device_name=device_name or "--",
            flash_size=flash_size,
            flash_size_bytes=cls._parse_flash_size_bytes(flash_size),
            device_type="--",
            cpu="--",
            bl_version="--",
        )

    @staticmethod
    def _extract_checksum(text: str) -> str | None:
        match = re.search(r"(?:Memory\s+)?Checksum\s*:\s*(0x[0-9A-Fa-f]+)", text, re.IGNORECASE)
        return match.group(1) if match else None

    @staticmethod
    def _extract_memory_values(text: str) -> list[Stm32MemoryValue]:
        return [
            Stm32MemoryValue(address=address, value=f"0x{value}")
            for address, value in re.findall(r"(0x[0-9A-Fa-f]+)\s*:\s*([0-9A-Fa-f]+)", text)
        ]

    @staticmethod
    def _parse_flash_size_bytes(flash_size_text: str) -> int | None:
        match = re.match(r"\s*(\d+)\s*([KMG]?)Bytes?\s*", flash_size_text, re.IGNORECASE)
        if not match:
            return None

        value = int(match.group(1))
        unit = match.group(2).upper()
        factor = {
            "": 1,
            "K": 1024,
            "M": 1024 * 1024,
            "G": 1024 * 1024 * 1024,
        }.get(unit, 1)
        return value * factor

