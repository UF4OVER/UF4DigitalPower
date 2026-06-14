# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: session_power.py
#  @FileType: 电源协议会话文件，负责 F4CP 电源设备读写和轮询
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Callable, Iterable

from PyQt5.QtCore import QCoreApplication, QEventLoop, QObject, QTimer, pyqtSignal, pyqtSlot

from app.session import (
    ErrorEvent,
    RxEvent,
    SendEvent,
    SerialEventType,
    SerialSession,
    SerialState,
    StateEvent,
    TxEvent,
)

from app.core.const import (
    PowerCommand,
    PowerDataType,
    PowerClientProtocolError,
    STATUS_TYPES,
    CC_CV_NAMES,
    STATE_MACHINE_NAMES,
    STATE_FLAG_NAMES,
    PowerClientError,
    STATUS_READ_TYPES,
    STREAM_SLOW_TYPES,
    STREAM_FAST_TYPES,
    STREAM_FAST_PERIOD_MS,
    STREAM_SLOW_PERIOD_MS,
    DEFAULT_STATUS_VALUES,
    FAULT_NAMES,
    WRITE_IDLE_WAIT_TIMEOUT_MS,
    PowerClientTimeoutError,
    WRITE_IDLE_RETRY_MS,
    WRITE_FAILURE_DISCONNECT_THRESHOLD,
    COMMUNICATION_FAILURE_DISCONNECT_THRESHOLD,
    WRITE_POLL_RESUME_DELAY_MS,
    POWER_STATUS_FIELD_MAP,
    PowerClientDeviceError,
    PowerFrameFlag,
)
from app.protocol.tvlcom import (
    build_frame,
    decode_tlvs,
    encode_tlv,
    ensure_readable as _ensure_readable,
    ensure_writable as _ensure_writable,
    extract_frame_from_buffer,
    pack_stream_start_request,
)


from config import get_logger

logger = get_logger("PowerClient")

def _u32(value: int) -> bytes:
    return int(value).to_bytes(4, "little", signed=False)


def _u8(value: int) -> bytes:
    return int(value).to_bytes(1, "little", signed=False)


def _u16(value: int) -> bytes:
    return int(value).to_bytes(2, "little", signed=False)


def build_status(values: dict[PowerDataType, int]) -> PowerStatus:
    """把一组协议字段整理成 UI 更好使用的 PowerStatus 快照。"""
    normalized = _normalize_status_values(values)
    missing = [type_id.name for type_id in STATUS_TYPES if type_id not in normalized]
    if missing:
        raise PowerClientProtocolError(f"Missing status types: {', '.join(missing)}")
    return PowerStatus(
        vin_mv=normalized[PowerDataType.INPUT_VOLTAGE],
        iin_ma=normalized[PowerDataType.INPUT_CURRENT],
        vout_mv=normalized[PowerDataType.OUTPUT_VOLTAGE],
        iout_ma=normalized[PowerDataType.OUTPUT_CURRENT],
        core_temp_mc=normalized[PowerDataType.CORE_TEMPERATURE],
        board_temp_mc=normalized[PowerDataType.BOARD_TEMPERATURE],
        temp2_temp_mc=normalized[PowerDataType.TEMP2_TEMPERATURE],
        set_voltage_limit_mv=normalized[PowerDataType.SET_VOLTAGE_LIMIT],
        set_current_limit_ma=normalized[PowerDataType.SET_CURRENT_LIMIT],
        cc_cv_mode=normalized[PowerDataType.CC_CV_MODE],
        power_state=normalized[PowerDataType.POWER_STATE],
        fault_state=normalized[PowerDataType.FAULT_STATE],
        state_machine_flag_bits=normalized[PowerDataType.STATE_MACHINE_FLAG_BITS],
        state_machine_state=normalized[PowerDataType.STATE_MACHINE_STATE],
        otp_value_mc=normalized[PowerDataType.OTP_VALUE],
        otp_set_value_mc=normalized[PowerDataType.OTP_SET_VALUE],
        ovp_value_mv=normalized[PowerDataType.OVP_VALUE],
        ovp_set_value_mv=normalized[PowerDataType.OVP_SET_VALUE],
        ocp_value_ma=normalized[PowerDataType.OCP_VALUE],
        ocp_set_value_ma=normalized[PowerDataType.OCP_SET_VALUE],
        duty_cmd_permille=normalized[PowerDataType.DUTY_CMD],
        pwm_a_compare=normalized[PowerDataType.PWM_A_COMPARE],
        pwm_d_compare=normalized[PowerDataType.PWM_D_COMPARE],
        fan_speed=normalized[PowerDataType.FAN_SPEED],
        fan_set_value=normalized[PowerDataType.FAN_SET_VALUE],
    )


def _normalize_status_values(values: dict[PowerDataType, int]) -> dict[PowerDataType, int]:
    """兼容旧固件缺字段的情况，用相近实时值补齐状态模型需要的数据。"""
    normalized = dict(values)
    if PowerDataType.OTP_VALUE not in normalized and PowerDataType.BOARD_TEMPERATURE in normalized:
        normalized[PowerDataType.OTP_VALUE] = normalized[PowerDataType.BOARD_TEMPERATURE]
    if PowerDataType.OVP_VALUE not in normalized and PowerDataType.OUTPUT_VOLTAGE in normalized:
        normalized[PowerDataType.OVP_VALUE] = normalized[PowerDataType.OUTPUT_VOLTAGE]
    if PowerDataType.OCP_VALUE not in normalized and PowerDataType.OUTPUT_CURRENT in normalized:
        normalized[PowerDataType.OCP_VALUE] = normalized[PowerDataType.OUTPUT_CURRENT]
    if PowerDataType.FAN_SET_VALUE not in normalized and PowerDataType.FAN_SPEED in normalized:
        normalized[PowerDataType.FAN_SET_VALUE] = normalized[PowerDataType.FAN_SPEED]
    return normalized


@dataclass(frozen=True)
class PowerStatus:
    vin_mv: int
    iin_ma: int
    vout_mv: int
    iout_ma: int
    core_temp_mc: int
    board_temp_mc: int
    temp2_temp_mc: int
    set_voltage_limit_mv: int
    set_current_limit_ma: int
    cc_cv_mode: int
    power_state: int
    fault_state: int
    state_machine_flag_bits: int
    state_machine_state: int
    otp_value_mc: int
    otp_set_value_mc: int
    ovp_value_mv: int
    ovp_set_value_mv: int
    ocp_value_ma: int
    ocp_set_value_ma: int
    duty_cmd_permille: int
    pwm_a_compare: int
    pwm_d_compare: int
    fan_speed: int
    fan_set_value: int

    @property
    def vin_v(self) -> float:
        return self.vin_mv / 1000.0

    @property
    def iin_a(self) -> float:
        return self.iin_ma / 1000.0

    @property
    def vout_v(self) -> float:
        return self.vout_mv / 1000.0

    @property
    def iout_a(self) -> float:
        return self.iout_ma / 1000.0

    @property
    def pout_w(self) -> float:
        return self.vout_v * self.iout_a

    @property
    def pin_w(self) -> float:
        return self.vin_v * self.iin_a

    @property
    def efficiency(self) -> float:
        return 0.0 if self.pin_w <= 0 else (self.pout_w / self.pin_w) * 100.0

    @property
    def core_temp_c(self) -> float:
        return self.core_temp_mc / 100.0

    @property
    def board_temp_c(self) -> float:
        return self.board_temp_mc / 100.0

    @property
    def temp2_temp_c(self) -> float:
        return self.temp2_temp_mc / 100.0

    @property
    def otp_value_c(self) -> float:
        return self.otp_value_mc / 100.0

    @property
    def otp_set_value_c(self) -> float:
        return self.otp_set_value_mc / 100.0

    @property
    def ovp_value_v(self) -> float:
        return self.ovp_value_mv / 1000.0

    @property
    def ovp_set_value_v(self) -> float | None:
        if self.ovp_set_value_mv is None:
            return None
        return self.ovp_set_value_mv / 1000.0

    @property
    def ocp_value_a(self) -> float:
        return self.ocp_value_ma / 1000.0

    @property
    def ocp_set_value_a(self) -> float:
        return self.ocp_set_value_ma / 1000.0

    @property
    def mode_name(self) -> str:
        return CC_CV_NAMES.get(self.cc_cv_mode, f"UNKNOWN({self.cc_cv_mode})")

    @property
    def topology_name(self) -> str:
        return STATE_MACHINE_NAMES.get(self.state_machine_state, f"UNKNOWN({self.state_machine_state})")

    @property
    def state_flag_name(self) -> str:
        return STATE_FLAG_NAMES.get(self.state_machine_flag_bits, f"0b{self.state_machine_flag_bits:04b}")

    @property
    def power_enabled(self) -> bool:
        return bool(self.power_state)


@dataclass(frozen=True)
class DebugSnapshot:
    output_voltage_raw: int
    output_voltage_mv: int
    ovp_set_value_mv: int | None = None
    input_current_raw: int | None = None
    output_current_raw: int | None = None
    input_current_ma: int | None = None
    output_current_ma: int | None = None
    loop_current_feedback_ma: int | None = None
    loop_current_reference_ma: int | None = None
    voltage_loop_reference_mv: int | None = None

    @property
    def output_voltage_v(self) -> float:
        return self.output_voltage_mv / 1000.0

    @property
    def ovp_set_value_v(self) -> float | None:
        if self.ovp_set_value_mv is None:
            return None
        return self.ovp_set_value_mv / 1000.0


@dataclass
class _PendingRequest:
    seq: int
    loop: QEventLoop
    expected_cmd: PowerCommand
    response: dict[PowerDataType, int] | None = None
    error: Exception | None = None


class F4CPPowerClient(QObject):
    log = pyqtSignal(str)
    error = pyqtSignal(str)
    connectionChanged = pyqtSignal(bool)
    statusUpdated = pyqtSignal(object)
    debugSnapshotReady = pyqtSignal(object)
    outputLimitsWritten = pyqtSignal()
    protectionValuesWritten = pyqtSignal()
    powerStateWritten = pyqtSignal(bool)
    writeTransactionFinished = pyqtSignal()
    writeFailureLimitReached = pyqtSignal()
    communicationFailureLimitReached = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._session: SerialSession | None = None
        self._buffer = bytearray()
        self._seq = 0
        self._pending: _PendingRequest | None = None
        self._last_values: dict[PowerDataType, int] = {}
        self._last_status: PowerStatus | None = None
        self._shutting_down = False
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_once)
        self._poll_resume_timer = QTimer(self)
        self._poll_resume_timer.setSingleShot(True)
        self._poll_resume_timer.timeout.connect(self._resume_polling_if_ready)
        self._stream_slow_poll_timer = QTimer(self)
        self._stream_slow_poll_timer.setSingleShot(False)
        self._stream_slow_poll_timer.timeout.connect(self._poll_stream_slow_group_once)
        self._poll_requested_interval_ms: int | None = None
        self._poll_resume_interval_ms: int | None = None
        self._consecutive_write_failures = 0
        self._consecutive_communication_failures = 0
        self._stream_types: tuple[PowerDataType, ...] = ()
        self._stream_fast_types: tuple[PowerDataType, ...] = ()
        self._stream_slow_types: tuple[PowerDataType, ...] = ()
        self._stream_enabled = False
        self._stream_stop_pending = False
        self._stream_bad_frame_count = 0
        self._stream_slow_poll_started = False
        self._stream_slow_refresh_in_progress = False

    @property
    def is_connected(self) -> bool:
        return self._session is not None and self._session.is_open

    @property
    def is_busy(self) -> bool:
        return self._pending is not None

    @pyqtSlot(object)
    def attach_session(self, session: SerialSession) -> None:
        """接管一个已经打开的串口会话，并把后续串口事件转发到本客户端。"""
        self._shutting_down = False
        self._session = session
        self._buffer.clear()
        self._pending = None
        self._last_values.clear()
        self._last_status = None
        self._consecutive_write_failures = 0
        self._consecutive_communication_failures = 0
        self._stop_stream_state()
        session.set_event_receiver(self)
        self._clear_receive_backlog()
        self.connectionChanged.emit(session.is_open)
        self.log.emit(f"Attached to serial session on {session.cfg.port}")

    @pyqtSlot()
    def detach_session(self) -> None:
        """解除串口绑定，同时清理轮询、挂起请求和上一帧缓存。"""
        self.stop_polling()
        self._fail_pending(PowerClientError("Serial session detached"))
        if self._session is not None:
            try:
                self._session.set_event_receiver(None)
            except Exception:
                logger.error(f"Failed to detach serial session on {self._session.cfg.port}")
        self._session = None
        self._buffer.clear()
        self._pending = None
        self._last_values.clear()
        self._last_status = None
        self._consecutive_write_failures = 0
        self._consecutive_communication_failures = 0
        self._stop_stream_state()
        self.connectionChanged.emit(False)

    @pyqtSlot()
    def shutdown(self) -> None:
        self._shutting_down = True
        self.stop_polling()
        self.detach_session()

    @pyqtSlot(int)
    def start_polling(self, interval_ms: int = 800) -> None:
        """启动状态刷新。

        新固件优先走 UF4COM STREAM_DATA 帧，失败时再回落到普通 READ 轮询。
        """
        interval = max(200, int(interval_ms))
        if self.is_connected and not self.is_busy:
            try:
                self.read_status(timeout_ms=1000)
                self.start_streaming(interval)
                return
            except Exception as exc:
                self.error.emit(str(exc))

        self._poll_resume_timer.stop()
        self._poll_resume_interval_ms = None
        self._poll_requested_interval_ms = interval
        was_active = self._poll_timer.isActive()
        previous_interval = self._poll_timer.interval()
        self._poll_timer.start(interval)
        if (not was_active) or previous_interval != interval:
            self.log.emit(f"Host polling started ({interval} ms)")
        if self.is_connected and not self.is_busy:
            QTimer.singleShot(0, self._poll_once)

    @pyqtSlot()
    def stop_polling(self) -> None:
        """停止自动刷新，并取消等待恢复轮询的延迟任务。"""
        if self._stream_enabled:
            try:
                self.stop_streaming()
            except Exception as exc:
                self.error.emit(str(exc))
        self._poll_timer.stop()
        self._poll_resume_timer.stop()
        self._poll_requested_interval_ms = None
        self._poll_resume_interval_ms = None

    @pyqtSlot()
    def request_read_status(self) -> None:
        if not self.is_connected or self.is_busy:
            return
        try:
            self.read_status(timeout_ms=1000)
        except Exception as exc:
            self.error.emit(str(exc))

    @pyqtSlot()
    def request_debug_snapshot(self) -> None:
        if not self.is_connected or self.is_busy:
            return
        try:
            snapshot = self.read_debug_snapshot(timeout_ms=1000)
            self.debugSnapshotReady.emit(snapshot)
        except Exception as exc:
            self.error.emit(str(exc))

    @pyqtSlot(int, int, bool)
    def request_set_output_limits(self, voltage_mv: int, current_ma: int, enabled: bool) -> None:
        """写入输出电压/电流限制，并按界面开关同步输出状态。"""
        def _write() -> None:
            self.write_values(
                {
                    PowerDataType.SET_VOLTAGE_LIMIT: _u32(voltage_mv),
                    PowerDataType.SET_CURRENT_LIMIT: _u32(current_ma),
                    PowerDataType.POWER_STATE: _u8(1 if enabled else 0),
                },
                timeout_ms=2000,
            )
            self.outputLimitsWritten.emit()
            self._refresh_status_after_write(timeout_ms=2000)

        self._run_write_transaction("output write", _write)

    @pyqtSlot(int, int, int, int)
    def request_set_protection_values(self, ovp_mv: int, ocp_ma: int, otp_mc: int, fan_value: int) -> None:
        """写入 OVP/OCP/OTP 和风扇目标值，这些保护参数一起提交更不容易状态撕裂。"""
        def _write() -> None:
            self.write_values(
                {
                    PowerDataType.OVP_SET_VALUE: _u32(ovp_mv),
                    PowerDataType.OCP_SET_VALUE: _u32(ocp_ma),
                    PowerDataType.OTP_SET_VALUE: _u16(otp_mc),
                    PowerDataType.FAN_SET_VALUE: _u32(fan_value),
                },
                timeout_ms=2000,
            )
            self.protectionValuesWritten.emit()
            self._refresh_status_after_write(timeout_ms=2000)

        self._run_write_transaction("protection write", _write)

    @pyqtSlot(bool)
    def request_set_power_state(self, enabled: bool) -> None:
        def _write() -> None:
            self.set_power_state(enabled, timeout_ms=2000)
            self.powerStateWritten.emit(enabled)
            self._refresh_status_after_write(timeout_ms=2000)

        self._run_write_transaction("power state write", _write)

    def event(self, event):
        event_type = event.type()

        if event_type == int(SerialEventType.RX):
            self._handle_rx(event)
            return True

        if event_type == int(SerialEventType.TX):
            self._handle_tx(event)
            return True

        if event_type == int(SerialEventType.ERROR):
            self._handle_error(event)
            return True

        if event_type == int(SerialEventType.STATE):
            self._handle_state(event)
            return True

        return super().event(event)

    def read_values(self, *types: PowerDataType, timeout_ms: int = 1000) -> dict[PowerDataType, int]:
        """同步读取指定字段，适合按钮触发或测试代码的一次性请求。"""
        for type_id in types:
            _ensure_readable(type_id)
        payload = b"".join(encode_tlv(type_id) for type_id in types)
        response = self._request(
            PowerCommand.READ,
            payload,
            timeout_ms=timeout_ms,
            expected_cmd=PowerCommand.READ_RSP,
        )

        if types == (PowerDataType.DEBUG_SNAPSHOT,):
            return response

        missing = [type_id.name for type_id in types if type_id not in response]
        if missing:
            raise PowerClientProtocolError(f"Missing response types: {', '.join(missing)}")
        self._last_values.update(response)
        return response

    def read_report_values(self, timeout_ms: int = 1000) -> dict[PowerDataType, int]:
        response = self.read_values(*STATUS_READ_TYPES, timeout_ms=timeout_ms)
        missing = [type_id.name for type_id in STATUS_READ_TYPES if type_id not in response]
        if missing:
            raise PowerClientProtocolError(f"Missing report types: {', '.join(missing)}")
        self._last_values.update(response)
        return response

    def write_values(self, values: dict[PowerDataType, bytes], timeout_ms: int = 1000) -> None:
        """同步写入一组字段；调用前会根据元数据检查字段是否允许写入。"""
        for type_id, raw_value in values.items():
            _ensure_writable(type_id, raw_value)
        payload = b"".join(encode_tlv(type_id, raw_value) for type_id, raw_value in values.items())
        self._request(
            PowerCommand.WRITE,
            payload,
            timeout_ms=timeout_ms,
            expected_cmd=PowerCommand.WRITE_RSP,
        )
        self._last_values.update(
            {
                type_id: int.from_bytes(raw_value, "little", signed=False)
                for type_id, raw_value in values.items()
            }
        )

    def read_status(self, timeout_ms: int = 1000) -> PowerStatus:
        """读取一帧完整状态，并把结果广播给页面和图表。"""
        result = self.read_report_values(timeout_ms=timeout_ms)
        status = build_status(result)
        self._last_status = status
        self.statusUpdated.emit(status)
        return status

    def start_streaming(
        self,
        interval_ms: int = 800,
        types: Iterable[PowerDataType] = STREAM_FAST_TYPES,
        timeout_ms: int = 1000,
    ) -> None:
        fast_types = tuple(types)
        # 裸流阶段只跑快组；慢组等流稳定后再通过单独请求刷新。
        slow_types = STREAM_SLOW_TYPES
        for type_id in fast_types:
            _ensure_readable(type_id)
        for type_id in slow_types:
            _ensure_readable(type_id)
        payload = pack_stream_start_request(
            fast_types,
            STREAM_FAST_PERIOD_MS,
            (),
            0,
        )
        self._request(
            PowerCommand.STREAM_START,
            payload,
            timeout_ms=timeout_ms,
            expected_cmd=PowerCommand.STREAM_START_RSP,
        )
        # STREAM_START 响应后可能已经跟着首批 STREAM_DATA 帧，清一次输入避免旧包扰动。
        self._clear_receive_backlog()
        for type_id, value in DEFAULT_STATUS_VALUES.items():
            self._last_values.setdefault(type_id, value)
        self._stream_types = fast_types + slow_types
        self._stream_fast_types = fast_types
        self._stream_slow_types = slow_types
        self._stream_enabled = True
        self._stream_bad_frame_count = 0
        self._stream_slow_poll_started = False
        self._poll_requested_interval_ms = max(200, int(interval_ms))
        self._poll_timer.stop()
        self._poll_resume_timer.stop()
        self._stream_slow_poll_timer.stop()
        self.log.emit(
            "UF4COM stream started "
            f"(fast={STREAM_FAST_PERIOD_MS} ms "
            f"types={','.join(type_id.name for type_id in fast_types)}; "
            f"slow={STREAM_SLOW_PERIOD_MS} ms "
            f"types={','.join(type_id.name for type_id in slow_types)})"
        )

    def stop_streaming(self, timeout_ms: int = 1000) -> None:
        was_enabled = self._stream_enabled
        if was_enabled and self.is_connected and not self.is_busy:
            self._stream_stop_pending = True
            try:
                self._request(
                    PowerCommand.STREAM_STOP,
                    b"",
                    timeout_ms=timeout_ms,
                    expected_cmd=PowerCommand.STREAM_STOP_RSP,
                )
            finally:
                self._stream_stop_pending = False
                self._stop_stream_state()
                self._clear_receive_backlog()
        else:
            self._stop_stream_state()
            self._buffer.clear()
        if was_enabled:
            self.log.emit("UF4COM stream stopped")

    def read_debug_snapshot(self, timeout_ms: int = 1000) -> DebugSnapshot:
        result = self.read_values(
            PowerDataType.OUTPUT_VOLTAGE_RAW,
            PowerDataType.OUTPUT_VOLTAGE,
            PowerDataType.OVP_SET_VALUE,
            PowerDataType.INPUT_CURRENT_RAW,
            PowerDataType.OUTPUT_CURRENT_RAW,
            PowerDataType.INPUT_CURRENT,
            PowerDataType.OUTPUT_CURRENT,
            PowerDataType.LOOP_CURRENT_FEEDBACK,
            PowerDataType.LOOP_CURRENT_REFERENCE,
            PowerDataType.VOLTAGE_LOOP_CURRENT_REFERENCE,
            timeout_ms=timeout_ms,
        )

        missing = [
            type_id.name
            for type_id in (
                PowerDataType.OUTPUT_VOLTAGE_RAW,
                PowerDataType.OUTPUT_VOLTAGE,
            )
            if type_id not in result
        ]
        if missing:
            raise PowerClientProtocolError(f"Debug snapshot missing response types: {', '.join(missing)}")

        return DebugSnapshot(
            output_voltage_raw=result[PowerDataType.OUTPUT_VOLTAGE_RAW],
            output_voltage_mv=result[PowerDataType.OUTPUT_VOLTAGE],
            ovp_set_value_mv=result.get(PowerDataType.OVP_SET_VALUE),
            input_current_raw=result.get(PowerDataType.INPUT_CURRENT_RAW),
            output_current_raw=result.get(PowerDataType.OUTPUT_CURRENT_RAW),
            input_current_ma=result.get(PowerDataType.INPUT_CURRENT),
            output_current_ma=result.get(PowerDataType.OUTPUT_CURRENT),
            loop_current_feedback_ma=result.get(PowerDataType.LOOP_CURRENT_FEEDBACK),
            loop_current_reference_ma=result.get(PowerDataType.LOOP_CURRENT_REFERENCE),
            voltage_loop_reference_mv=result.get(PowerDataType.VOLTAGE_LOOP_CURRENT_REFERENCE),
        )

    def set_voltage_limit_mv(self, value_mv: int, timeout_ms: int = 1000) -> None:
        self.write_values({PowerDataType.SET_VOLTAGE_LIMIT: _u32(value_mv)}, timeout_ms=timeout_ms)

    def set_current_limit_ma(self, value_ma: int, timeout_ms: int = 1000) -> None:
        self.write_values({PowerDataType.SET_CURRENT_LIMIT: _u32(value_ma)}, timeout_ms=timeout_ms)

    def set_ovp_mv(self, value_mv: int, timeout_ms: int = 1000) -> None:
        self.write_values({PowerDataType.OVP_SET_VALUE: _u32(value_mv)}, timeout_ms=timeout_ms)

    def set_ocp_ma(self, value_ma: int, timeout_ms: int = 1000) -> None:
        self.write_values({PowerDataType.OCP_SET_VALUE: _u32(value_ma)}, timeout_ms=timeout_ms)

    def set_otp_mc(self, value_mc: int, timeout_ms: int = 1000) -> None:
        self.write_values({PowerDataType.OTP_SET_VALUE: _u16(value_mc)}, timeout_ms=timeout_ms)

    def set_fan_value(self, value: int, timeout_ms: int = 1000) -> None:
        self.write_values({PowerDataType.FAN_SET_VALUE: _u32(value)}, timeout_ms=timeout_ms)

    def set_power_state(self, enabled: bool, timeout_ms: int = 1000) -> None:
        self.write_values({PowerDataType.POWER_STATE: _u8(1 if enabled else 0)}, timeout_ms=timeout_ms)

    def set_output(
        self,
        voltage_v: float,
        current_a: float,
        enabled: bool = True,
        timeout_ms: int = 1000,
    ) -> None:
        self.write_values(
            {
                PowerDataType.SET_VOLTAGE_LIMIT: _u32(int(voltage_v * 1000 + 0.5)),
                PowerDataType.SET_CURRENT_LIMIT: _u32(int(current_a * 1000 + 0.5)),
                PowerDataType.POWER_STATE: _u8(1 if enabled else 0),
            },
            timeout_ms=timeout_ms,
        )

    def pretty_print_status(self, status: PowerStatus) -> str:
        faults = ", ".join(self.decode_fault_flags(status.fault_state)) or "None"
        return (
            f"VIN={status.vin_v:.3f} V, IIN={status.iin_a:.3f} A, "
            f"VOUT={status.vout_v:.3f} V, IOUT={status.iout_a:.3f} A, "
            f"Mode={status.mode_name}, Topology={status.topology_name}, "
            f"Power={'ON' if status.power_enabled else 'OFF'}, Faults={faults}"
        )

    @staticmethod
    def pretty_print_debug_snapshot(snapshot: DebugSnapshot) -> str:
        parts = [
            "DEBUG_SNAPSHOT "
            f"raw27={snapshot.output_voltage_raw}, "
            f"vout12={snapshot.output_voltage_mv} mV ({snapshot.output_voltage_v:.3f} V)"
        ]
        if snapshot.ovp_set_value_mv is not None and snapshot.ovp_set_value_v is not None:
            parts.append(f"ovp32={snapshot.ovp_set_value_mv} mV ({snapshot.ovp_set_value_v:.3f} V)")
        if snapshot.input_current_raw is not None:
            parts.append(f"iin_raw26={snapshot.input_current_raw}")
        if snapshot.output_current_raw is not None:
            parts.append(f"iout_raw28={snapshot.output_current_raw}")
        if snapshot.input_current_ma is not None:
            parts.append(f"iin11={snapshot.input_current_ma} mA")
        if snapshot.output_current_ma is not None:
            parts.append(f"iout13={snapshot.output_current_ma} mA")
        if snapshot.loop_current_feedback_ma is not None:
            parts.append(f"loop_i_fb41={snapshot.loop_current_feedback_ma} mA")
        if snapshot.loop_current_reference_ma is not None:
            parts.append(f"loop_i_ref42={snapshot.loop_current_reference_ma} mA")
        if snapshot.voltage_loop_reference_mv is not None:
            parts.append(f"loop_v_ref43={snapshot.voltage_loop_reference_mv} mV")
        return ", ".join(parts)

    @staticmethod
    def decode_fault_flags(mask: int) -> list[str]:
        if mask == 0:
            return []
        return [name for flag, name in FAULT_NAMES.items() if mask & int(flag)]

    @staticmethod
    def decode_state_flag(value: int) -> str:
        return STATE_FLAG_NAMES.get(value, f"0b{value:04b}")

    @staticmethod
    def decode_topology(value: int) -> str:
        return STATE_MACHINE_NAMES.get(value, f"UNKNOWN({value})")

    @staticmethod
    def decode_cc_cv(value: int) -> str:
        return CC_CV_NAMES.get(value, f"UNKNOWN({value})")

    def _run_write_transaction(self, description: str, write_action: Callable[[], None]) -> None:
        """把一次写操作包进安全流程：先让轮询停下来，再等待当前请求结束。"""
        if not self.is_connected:
            self.error.emit("Serial session is not connected")
            return

        try:
            self._pause_polling_for_write()
        except Exception as exc:
            self._record_write_failure(exc)
            self._schedule_polling_resume()
            self.writeTransactionFinished.emit()
            return
        self._run_write_when_idle(description, write_action, time.monotonic())

    def _run_write_when_idle(
        self,
        description: str,
        write_action: Callable[[], None],
        started_at: float,
    ) -> None:
        """等客户端空闲后再真正写入，避免写请求和自动轮询抢同一个响应。"""
        if self._shutting_down or not self.is_connected:
            self._schedule_polling_resume()
            return

        if self.is_busy:
            waited_ms = int((time.monotonic() - started_at) * 1000)
            if waited_ms >= WRITE_IDLE_WAIT_TIMEOUT_MS:
                self._record_write_failure(
                    PowerClientTimeoutError(
                        f"Timed out waiting for polling to finish; {description} was not sent"
                    )
                )
                self._schedule_polling_resume()
                return

            QTimer.singleShot(
                WRITE_IDLE_RETRY_MS,
                lambda: self._run_write_when_idle(description, write_action, started_at),
            )
            return

        try:
            write_action()
            self._consecutive_write_failures = 0
        except Exception as exc:
            self._record_write_failure(exc)
        finally:
            self._schedule_polling_resume()
            self.writeTransactionFinished.emit()

    def _record_write_failure(self, exc: Exception) -> None:
        self._consecutive_write_failures += 1
        self.error.emit(
            f"{exc} (写入失败 {self._consecutive_write_failures}/"
            f"{WRITE_FAILURE_DISCONNECT_THRESHOLD})"
        )
        if self._consecutive_write_failures >= WRITE_FAILURE_DISCONNECT_THRESHOLD:
            self.log.emit("连续写入失败 3 次，准备断开串口")
            self._consecutive_write_failures = 0
            self.writeFailureLimitReached.emit()

    def _reset_communication_failures(self) -> None:
        self._consecutive_communication_failures = 0

    def _record_communication_failure(self, exc: Exception | str) -> None:
        self._consecutive_communication_failures += 1
        message = str(exc)
        self.log.emit(
            f"通信失败 {self._consecutive_communication_failures}/"
            f"{COMMUNICATION_FAILURE_DISCONNECT_THRESHOLD}: {message}"
        )
        if self._consecutive_communication_failures >= COMMUNICATION_FAILURE_DISCONNECT_THRESHOLD:
            self.log.emit("连续通信失败 3 次，准备断开串口")
            self._consecutive_communication_failures = 0
            self.communicationFailureLimitReached.emit(message)

    def _pause_polling_for_write(self) -> None:
        """写参数前暂停自动刷新，给设备留出一段安静的命令窗口。"""
        self._poll_resume_timer.stop()
        if self._stream_enabled:
            interval = self._poll_requested_interval_ms
            self._poll_resume_interval_ms = interval if interval is not None else 800
            self.stop_streaming(timeout_ms=1000)
            self.log.emit("UF4COM stream paused for write")
            return
        if self._poll_requested_interval_ms is not None:
            self._poll_resume_interval_ms = self._poll_requested_interval_ms
            self._poll_timer.stop()
            self.log.emit("Host polling paused for write")

    def _schedule_polling_resume(self) -> None:
        if self._poll_resume_interval_ms is None or self._shutting_down:
            return
        self._poll_resume_timer.start(WRITE_POLL_RESUME_DELAY_MS)

    def _resume_polling_if_ready(self) -> None:
        """写入完成后恢复刷新；如果设备还忙，就稍等一小段时间再试。"""
        interval = self._poll_resume_interval_ms
        if interval is None:
            return
        if self._shutting_down or not self.is_connected:
            self._poll_resume_interval_ms = None
            return
        if self.is_busy:
            self._poll_resume_timer.start(WRITE_IDLE_RETRY_MS)
            return

        self._poll_resume_interval_ms = None
        self._poll_requested_interval_ms = interval
        if self.is_connected and not self._stream_enabled:
            try:
                self.start_streaming(interval)
                return
            except Exception as exc:
                self.error.emit(f"UF4COM stream resume failed: {exc}")
        self._poll_timer.start(interval)
        self.log.emit(f"Host polling resumed ({interval} ms)")
        QTimer.singleShot(0, self._poll_once)

    def _poll_once(self) -> None:
        if self._shutting_down or not self.is_connected or self.is_busy:
            return
        try:
            self.read_status(timeout_ms=800)
        except Exception as exc:
            self.error.emit(str(exc))

    def _refresh_status_after_write(self, timeout_ms: int = 1000) -> None:
        if self._shutting_down or not self.is_connected or self.is_busy:
            return
        try:
            self.read_status(timeout_ms=timeout_ms)
        except Exception as exc:
            self.error.emit(f"WRITE_RSP received, but status refresh failed: {exc}")

    def _request(
        self,
        cmd: PowerCommand,
        payload: bytes,
        expected_cmd: PowerCommand,
        timeout_ms: int = 1000,
    ) -> dict[PowerDataType, int]:
        """发送一条命令并等待对应响应。

        Qt 串口对象在线程内收发，所以这里用本地 QEventLoop 等待 RX 事件来唤醒。
        """
        if not self.is_connected or self._session is None:
            raise PowerClientError("Serial session is not connected")
        if self._pending is not None:
            raise PowerClientError("Another request is still pending")

        if not self._stream_enabled:
            self._clear_receive_backlog()

        self._seq = (self._seq + 1) & 0xFF
        seq = self._seq
        frame = build_frame(cmd, seq, payload)
        loop = QEventLoop(self)
        pending = _PendingRequest(seq=seq, loop=loop, expected_cmd=expected_cmd)
        self._pending = pending

        timer = QTimer(self)
        timer.setSingleShot(True)

        def _on_timeout():
            if self._pending is pending and pending.error is None and pending.response is None:
                pending.error = PowerClientTimeoutError(f"Request timed out for seq={seq}")
                pending.loop.quit()

        timer.timeout.connect(_on_timeout)
        timer.start(timeout_ms)

        QCoreApplication.postEvent(self._session, SendEvent(frame))
        self.log.emit(f"REQ cmd=0x{int(cmd):02X} seq={seq} len={len(payload)}")
        pending.loop.exec_()

        timer.stop()
        timer.deleteLater()
        self._pending = None

        if pending.error is not None:
            self._record_communication_failure(pending.error)
            raise pending.error
        self._reset_communication_failures()
        return pending.response or {}

    def _handle_rx(self, event: RxEvent) -> None:
        """消费串口收到的字节流，按当前模式解析为原始流样本或完整协议帧。"""
        data = event.payload.data
        if not data:
            return
        self.log.emit(f"RX {data.hex(' ')}")
        self._buffer.extend(data)

        while True:
            try:
                frame = self._extract_frame()
            except Exception as exc:
                self._fail_pending(exc)
                self.error.emit(str(exc))
                return

            if frame is None:
                break

            if int(frame["cmd"]) == int(PowerCommand.STREAM_DATA):
                self._handle_stream_data_frame(frame)
                continue

            try:
                response = self._parse_response(frame)
            except Exception as exc:
                self._fail_pending(exc)
                self.error.emit(str(exc))
                continue

            if self._pending is None:
                self.log.emit("Ignored unsolicited response frame")
                continue

            if frame["seq"] != self._pending.seq:
                if self._stream_stop_pending:
                    self.log.emit(f"Ignored stream-stop noise frame seq={frame['seq']}")
                    continue
                self.log.emit(
                    f"Ignored stale response seq={frame['seq']} while waiting for seq={self._pending.seq}"
                )
                continue

            self._pending.response = response
            self._pending.loop.quit()

    def _handle_stream_data_frame(self, frame: dict[str, int | bytes]) -> None:
        """处理 UF4COM 主动 STREAM_DATA 帧。"""
        try:
            values = decode_tlvs(bytes(frame["payload"]), strict=False)
        except Exception as exc:
            self._handle_stream_decode_error(exc)
            return
        self._handle_stream_values(values)

    def _status_from_values(self, values: dict[PowerDataType, int]) -> PowerStatus | None:
        values = _normalize_status_values(values)
        if self._last_status is None:
            try:
                return build_status(self._last_values)
            except PowerClientProtocolError:
                return None

        updates = {}
        for type_id, value in values.items():
            field_name = POWER_STATUS_FIELD_MAP.get(type_id)
            if field_name is not None:
                updates[field_name] = value

        return replace(self._last_status, **updates) if updates else self._last_status

    def _handle_tx(self, event: TxEvent) -> None:
        self.log.emit(f"TX {event.payload.data.hex(' ')}")

    def _handle_error(self, event: ErrorEvent) -> None:
        message = event.payload.message
        self._fail_pending(PowerClientError(message))
        self._record_communication_failure(message)
        self.error.emit(message)
        if event.payload.fatal and not self.is_connected:
            self._handle_serial_connection_lost(message)

    def _handle_state(self, event: StateEvent) -> None:
        state = event.payload.state
        is_open = state == SerialState.OPEN
        self.connectionChanged.emit(is_open)
        if state == SerialState.CLOSED:
            self.stop_polling()
            self._fail_pending(PowerClientError("Serial port closed"))
        elif state == SerialState.ERROR:
            self.error.emit(event.payload.info or "Serial port error")

    def _handle_serial_connection_lost(self, message: str) -> None:
        self.stop_polling()
        self._poll_resume_timer.stop()
        self._poll_requested_interval_ms = None
        self._poll_resume_interval_ms = None
        self._stop_stream_state()
        self._fail_pending(PowerClientError(message))
        self.connectionChanged.emit(False)

    def _stop_stream_state(self) -> None:
        self._stream_enabled = False
        self._stream_types = ()
        self._stream_fast_types = ()
        self._stream_slow_types = ()
        self._stream_stop_pending = False
        self._stream_bad_frame_count = 0
        self._stream_slow_poll_started = False
        self._stream_slow_refresh_in_progress = False
        self._stream_slow_poll_timer.stop()

    def _clear_receive_backlog(self) -> None:
        self._buffer.clear()
        if self._session is None:
            return
        clear_input_buffer = getattr(self._session, "clear_input_buffer", None)
        if clear_input_buffer is None:
            return
        try:
            clear_input_buffer()
        except Exception as exc:
            self.log.emit(f"Input buffer clear failed: {exc}")

    def _handle_stream_decode_error(self, exc: Exception) -> None:
        self._stream_bad_frame_count += 1
        bad_count = self._stream_bad_frame_count

        self.log.emit(
            f"UF4COM stream bad frame {bad_count}/3: {exc}"
            + "; discarded bad frame and waiting next frame"
        )

        if bad_count < 3:
            return

        message = f"UF4COM stream failed for 3 consecutive frames: {exc}"
        self._stop_stream_state()
        self._record_communication_failure(message)
        self.error.emit(message)
        self.communicationFailureLimitReached.emit(message)

    def _handle_stream_values(self, values: dict[PowerDataType, int]) -> None:
        self._stream_bad_frame_count = 0
        if (not self._stream_slow_poll_started) and self._stream_enabled:
            self._stream_slow_poll_started = True
            if self._stream_slow_types:
                self._stream_slow_poll_timer.start(STREAM_SLOW_PERIOD_MS)
        self._last_values.update(values)
        self._reset_communication_failures()
        status = self._status_from_values(values)
        if status is None:
            return
        self._last_status = status
        self.statusUpdated.emit(status)

    def _poll_stream_slow_group_once(self) -> None:
        if self._shutting_down or not self.is_connected or not self._stream_enabled:
            self._stream_slow_poll_timer.stop()
            return
        if (
            not self._stream_slow_types
            or self.is_busy
            or self._stream_stop_pending
            or self._stream_slow_refresh_in_progress
        ):
            return

        fast_types = self._stream_fast_types
        slow_types = self._stream_slow_types
        interval_ms = self._poll_requested_interval_ms or 800

        self._stream_slow_refresh_in_progress = True
        self._stream_slow_poll_timer.stop()
        try:
            self.stop_streaming(timeout_ms=1000)
            values = self.read_values(*slow_types, timeout_ms=1000)
        except Exception as exc:
            self.error.emit(f"Slow group refresh failed: {exc}")
            values = None
        finally:
            restart_error = None
            if self.is_connected and not self._shutting_down:
                restart_error = self._restart_stream_after_slow_refresh(interval_ms, fast_types)
            self._stream_slow_refresh_in_progress = False

        if restart_error is not None:
            self.error.emit(f"UF4COM stream restart failed after slow-group refresh: {restart_error}")

        if not values:
            return

        self._last_values.update(values)
        status = self._status_from_values(values)
        if status is None:
            return
        self._last_status = status
        self.statusUpdated.emit(status)

    def _restart_stream_after_slow_refresh(
        self,
        interval_ms: int,
        fast_types: tuple[PowerDataType, ...],
    ) -> Exception | None:
        last_error: Exception | None = None

        for attempt in range(2):
            if not self.is_connected or self._shutting_down:
                return None

            self._clear_receive_backlog()
            if attempt > 0:
                time.sleep(0.05)

            try:
                self.start_streaming(interval_ms=interval_ms, types=fast_types, timeout_ms=1000)
                return None
            except Exception as exc:
                last_error = exc
                self.log.emit(f"UF4COM stream restart retry {attempt + 1}/2 failed: {exc}")

        return last_error

    def _is_stream_frame_search_active(self) -> bool:
        return self._stream_stop_pending or (self._stream_enabled and self._pending is not None)

    def _extract_frame(self) -> dict[str, int | bytes] | None:
        """从接收缓存里提取一帧完整协议数据，顺手丢掉帧头前的噪声。"""
        return extract_frame_from_buffer(
            self._buffer,
            stream_frame_search=self._is_stream_frame_search_active(),
        )

    def _parse_response(self, frame: dict[str, int | bytes]) -> dict[PowerDataType, int]:
        cmd = int(frame["cmd"])
        flags = int(frame.get("flags", 0))
        payload = bytes(frame["payload"])

        if flags & int(PowerFrameFlag.ERROR):
            code = int.from_bytes(payload[1:3], "big", signed=False) if len(payload) >= 3 else 0
            raise PowerClientDeviceError(f"Device returned UF4COM error 0x{code:04X} for seq={frame['seq']}")
        if self._pending is not None and cmd != int(self._pending.expected_cmd):
            raise PowerClientProtocolError(
                f"Unexpected response cmd=0x{cmd:02X}, expected 0x{int(self._pending.expected_cmd):02X}"
            )
        return decode_tlvs(payload)

    def _fail_pending(self, exc: Exception) -> None:
        if self._pending is None:
            return
        self._pending.error = exc
        self._pending.loop.quit()


def pretty_faults(mask: int) -> str:
    return ", ".join(F4CPPowerClient.decode_fault_flags(mask)) or "None"


