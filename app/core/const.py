# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/6/6
#  @FileName: const.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 按文件来
#  @Python  : 
# -------------------------------
import re
from dataclasses import dataclass
from enum import IntEnum


# ========================= session_power.py start ===================================== #
class PowerClientError(RuntimeError):
    """Base error for power client failures."""

class PowerClientTimeoutError(PowerClientError):
    """Raised when the devices response times out."""

class PowerClientCrcError(PowerClientError):
    """Raised when an incoming frame fails CRC validation."""

class PowerClientProtocolError(PowerClientError):
    """Raised when the frame structure or response content is invalid."""

class PowerClientNackError(PowerClientError):
    """Raised when the devices returns NACK."""

class PowerClientAccessError(PowerClientProtocolError):
    """Raised when a requested operation violates the data metadata."""

class PowerCommand(IntEnum):
    ACK = 0x00
    READ = 0x01
    WRITE = 0x02
    REPORT = 0x03
    STREAM_START = 0x04
    STREAM_STOP = 0x05
    NACK = 0xFF

class PowerDataType(IntEnum):
    INPUT_VOLTAGE = 10
    INPUT_CURRENT = 11
    OUTPUT_VOLTAGE = 12
    OUTPUT_CURRENT = 13
    CORE_TEMPERATURE = 14
    BOARD_TEMPERATURE = 15
    SET_VOLTAGE_LIMIT = 17
    SET_CURRENT_LIMIT = 18
    CC_CV_MODE = 20
    POWER_STATE = 21
    FAULT_STATE = 22
    STATE_MACHINE_FLAG_BITS = 23
    STATE_MACHINE_STATE = 24
    INPUT_VOLTAGE_RAW = 25
    INPUT_CURRENT_RAW = 26
    OUTPUT_VOLTAGE_RAW = 27
    OUTPUT_CURRENT_RAW = 28
    OTP_VALUE = 29
    OTP_SET_VALUE = 30
    OVP_VALUE = 31
    OVP_SET_VALUE = 32
    OCP_VALUE = 33
    OCP_SET_VALUE = 34
    DUTY_CMD = 35
    PWM_A_COMPARE = 36
    PWM_D_COMPARE = 37
    FAN_SPEED = 38
    FAN_SET_VALUE = 39
    DEBUG_SNAPSHOT = 40
    APP_TVL_DEBUG_SNAPSHOT = 40  # Legacy alias; use DEBUG_SNAPSHOT in new code.
    LOOP_CURRENT_FEEDBACK = 41
    LOOP_CURRENT_REFERENCE = 42
    VOLTAGE_LOOP_CURRENT_REFERENCE = 43

class PowerValueType(IntEnum):
    U8 = 1
    U32 = 4
    I32 = 4

class PowerAccess(IntEnum):
    READ = 0x01
    WRITE = 0x02
    READ_WRITE = 0x03

@dataclass(frozen=True)
class PowerDataMeta:
    type_id: PowerDataType
    value_type: PowerValueType
    access: PowerAccess
    unit: str
    label: str
    signed: bool = False

    @property
    def length(self) -> int:
        return int(self.value_type)

class FaultFlag(IntEnum):
    INPUT_UNDER_VOLTAGE = 0x0001
    INPUT_OVER_VOLTAGE = 0x0002
    OUTPUT_UNDER_VOLTAGE = 0x0004
    OUTPUT_OVER_VOLTAGE = 0x0008
    OUTPUT_OVER_CURRENT = 0x0010
    OUTPUT_SHORT_CIRCUIT = 0x0020
    OVER_TEMPERATURE_PROTECTION = 0x0040


FAULT_NAMES = {
    FaultFlag.INPUT_UNDER_VOLTAGE: "输入欠压",
    FaultFlag.INPUT_OVER_VOLTAGE: "输入过压",
    FaultFlag.OUTPUT_UNDER_VOLTAGE: "输出欠压",
    FaultFlag.OUTPUT_OVER_VOLTAGE: "输出过压",
    FaultFlag.OUTPUT_OVER_CURRENT: "输出过流",
    FaultFlag.OUTPUT_SHORT_CIRCUIT: "输入短路",
    FaultFlag.OVER_TEMPERATURE_PROTECTION: "过温保护",
}

STATE_FLAG_NAMES = {
    0b0001: "INIT",
    0b0010: "WAIT",
    0b0100: "RISE",
    0b1000: "RUN",
    0b1111: "ERR",
}

STATE_MACHINE_NAMES = {
    0: "NA",
    1: "BUCK",
    2: "BOOST",
    3: "MIX",
}

CC_CV_NAMES = {
    0: "CC",
    1: "CV",
}

SOF = b"\xAA\x55"
STREAM_CHANNEL_SEPARATOR = b"\xFE\xED"

STREAM_FAST_PERIOD_MS = 20
STREAM_SLOW_PERIOD_MS = 1000

WRITE_IDLE_RETRY_MS = 25
WRITE_IDLE_WAIT_TIMEOUT_MS = 2500
WRITE_POLL_RESUME_DELAY_MS = 800
WRITE_FAILURE_DISCONNECT_THRESHOLD = 3
COMMUNICATION_FAILURE_DISCONNECT_THRESHOLD = 3

POWER_DATA_META: dict[PowerDataType, PowerDataMeta] = {
    PowerDataType.INPUT_VOLTAGE: PowerDataMeta(PowerDataType.INPUT_VOLTAGE, PowerValueType.U32, PowerAccess.READ, "mV", "Input Voltage"),
    PowerDataType.INPUT_CURRENT: PowerDataMeta(PowerDataType.INPUT_CURRENT, PowerValueType.I32, PowerAccess.READ, "mA", "Input Current", signed=True),
    PowerDataType.OUTPUT_VOLTAGE: PowerDataMeta(PowerDataType.OUTPUT_VOLTAGE, PowerValueType.U32, PowerAccess.READ, "mV", "Output Voltage"),
    PowerDataType.OUTPUT_CURRENT: PowerDataMeta(PowerDataType.OUTPUT_CURRENT, PowerValueType.I32, PowerAccess.READ, "mA", "Output Current", signed=True),
    PowerDataType.CORE_TEMPERATURE: PowerDataMeta(PowerDataType.CORE_TEMPERATURE, PowerValueType.U32, PowerAccess.READ, "mC", "core Temperature"),
    PowerDataType.BOARD_TEMPERATURE: PowerDataMeta(PowerDataType.BOARD_TEMPERATURE, PowerValueType.U32, PowerAccess.READ, "mC", "Board Temperature"),
    PowerDataType.SET_VOLTAGE_LIMIT: PowerDataMeta(PowerDataType.SET_VOLTAGE_LIMIT, PowerValueType.U32, PowerAccess.READ_WRITE, "mV", "Set Voltage Limit"),
    PowerDataType.SET_CURRENT_LIMIT: PowerDataMeta(PowerDataType.SET_CURRENT_LIMIT, PowerValueType.U32, PowerAccess.READ_WRITE, "mA", "Set Current Limit"),
    PowerDataType.CC_CV_MODE: PowerDataMeta(PowerDataType.CC_CV_MODE, PowerValueType.U8, PowerAccess.READ, "enum", "CC/CV Mode"),
    PowerDataType.POWER_STATE: PowerDataMeta(PowerDataType.POWER_STATE, PowerValueType.U8, PowerAccess.READ_WRITE, "bool", "Power State"),
    PowerDataType.FAULT_STATE: PowerDataMeta(PowerDataType.FAULT_STATE, PowerValueType.U32, PowerAccess.READ, "bitmask", "Fault State"),
    PowerDataType.STATE_MACHINE_FLAG_BITS: PowerDataMeta(PowerDataType.STATE_MACHINE_FLAG_BITS, PowerValueType.U8, PowerAccess.READ, "enum", "State Machine Flag Bits"),
    PowerDataType.STATE_MACHINE_STATE: PowerDataMeta(PowerDataType.STATE_MACHINE_STATE, PowerValueType.U8, PowerAccess.READ, "enum", "State Machine State"),
    PowerDataType.INPUT_VOLTAGE_RAW: PowerDataMeta(PowerDataType.INPUT_VOLTAGE_RAW, PowerValueType.U32, PowerAccess.READ, "adc", "Input Voltage Raw"),
    PowerDataType.INPUT_CURRENT_RAW: PowerDataMeta(PowerDataType.INPUT_CURRENT_RAW, PowerValueType.U32, PowerAccess.READ, "adc", "Input Current Raw"),
    PowerDataType.OUTPUT_VOLTAGE_RAW: PowerDataMeta(PowerDataType.OUTPUT_VOLTAGE_RAW, PowerValueType.U32, PowerAccess.READ, "adc", "Output Voltage Raw"),
    PowerDataType.OUTPUT_CURRENT_RAW: PowerDataMeta(PowerDataType.OUTPUT_CURRENT_RAW, PowerValueType.U32, PowerAccess.READ, "adc", "Output Current Raw"),
    PowerDataType.OTP_VALUE: PowerDataMeta(PowerDataType.OTP_VALUE, PowerValueType.U32, PowerAccess.READ, "mC", "OTP Value"),
    PowerDataType.OTP_SET_VALUE: PowerDataMeta(PowerDataType.OTP_SET_VALUE, PowerValueType.U32, PowerAccess.READ_WRITE, "mC", "OTP Set Value"),
    PowerDataType.OVP_VALUE: PowerDataMeta(PowerDataType.OVP_VALUE, PowerValueType.U32, PowerAccess.READ, "mV", "OVP Value"),
    PowerDataType.OVP_SET_VALUE: PowerDataMeta(PowerDataType.OVP_SET_VALUE, PowerValueType.U32, PowerAccess.READ_WRITE, "mV", "OVP Set Value"),
    PowerDataType.OCP_VALUE: PowerDataMeta(PowerDataType.OCP_VALUE, PowerValueType.U32, PowerAccess.READ, "mA", "OCP Value"),
    PowerDataType.OCP_SET_VALUE: PowerDataMeta(PowerDataType.OCP_SET_VALUE, PowerValueType.U32, PowerAccess.READ_WRITE, "mA", "OCP Set Value"),
    PowerDataType.DUTY_CMD: PowerDataMeta(PowerDataType.DUTY_CMD, PowerValueType.U32, PowerAccess.READ, "permille", "Duty Command"),
    PowerDataType.PWM_A_COMPARE: PowerDataMeta(PowerDataType.PWM_A_COMPARE, PowerValueType.U32, PowerAccess.READ, "ticks", "PWM A Compare"),
    PowerDataType.PWM_D_COMPARE: PowerDataMeta(PowerDataType.PWM_D_COMPARE, PowerValueType.U32, PowerAccess.READ, "ticks", "PWM D Compare"),
    PowerDataType.FAN_SPEED: PowerDataMeta(PowerDataType.FAN_SPEED, PowerValueType.U32, PowerAccess.READ, "permille", "Fan Speed"),
    PowerDataType.FAN_SET_VALUE: PowerDataMeta(PowerDataType.FAN_SET_VALUE, PowerValueType.U32, PowerAccess.READ_WRITE, "permille", "Fan Set Value"),
    PowerDataType.LOOP_CURRENT_FEEDBACK: PowerDataMeta(PowerDataType.LOOP_CURRENT_FEEDBACK, PowerValueType.U32, PowerAccess.READ, "mA", "Loop Current Feedback"),
    PowerDataType.LOOP_CURRENT_REFERENCE: PowerDataMeta(PowerDataType.LOOP_CURRENT_REFERENCE, PowerValueType.U32, PowerAccess.READ, "mA", "Loop Current Reference"),
    PowerDataType.VOLTAGE_LOOP_CURRENT_REFERENCE: PowerDataMeta(PowerDataType.VOLTAGE_LOOP_CURRENT_REFERENCE, PowerValueType.U32, PowerAccess.READ, "mV", "Voltage Loop Reference"),
}

TYPE_LENGTHS = {type_id: meta.length for type_id, meta in POWER_DATA_META.items()}

POWER_STATUS_FIELD_MAP = {
    PowerDataType.INPUT_VOLTAGE: "vin_mv",
    PowerDataType.INPUT_CURRENT: "iin_ma",
    PowerDataType.OUTPUT_VOLTAGE: "vout_mv",
    PowerDataType.OUTPUT_CURRENT: "iout_ma",
    PowerDataType.CORE_TEMPERATURE: "core_temp_mc",
    PowerDataType.BOARD_TEMPERATURE: "board_temp_mc",
    PowerDataType.SET_VOLTAGE_LIMIT: "set_voltage_limit_mv",
    PowerDataType.SET_CURRENT_LIMIT: "set_current_limit_ma",
    PowerDataType.CC_CV_MODE: "cc_cv_mode",
    PowerDataType.POWER_STATE: "power_state",
    PowerDataType.FAULT_STATE: "fault_state",
    PowerDataType.STATE_MACHINE_FLAG_BITS: "state_machine_flag_bits",
    PowerDataType.STATE_MACHINE_STATE: "state_machine_state",
    PowerDataType.OTP_VALUE: "otp_value_mc",
    PowerDataType.OTP_SET_VALUE: "otp_set_value_mc",
    PowerDataType.OVP_VALUE: "ovp_value_mv",
    PowerDataType.OVP_SET_VALUE: "ovp_set_value_mv",
    PowerDataType.OCP_VALUE: "ocp_value_ma",
    PowerDataType.OCP_SET_VALUE: "ocp_set_value_ma",
    PowerDataType.DUTY_CMD: "duty_cmd_permille",
    PowerDataType.PWM_A_COMPARE: "pwm_a_compare",
    PowerDataType.PWM_D_COMPARE: "pwm_d_compare",
    PowerDataType.FAN_SPEED: "fan_speed",
    PowerDataType.FAN_SET_VALUE: "fan_set_value",
}

STATUS_TYPES = (
    PowerDataType.INPUT_VOLTAGE,
    PowerDataType.INPUT_CURRENT,
    PowerDataType.OUTPUT_VOLTAGE,
    PowerDataType.OUTPUT_CURRENT,
    PowerDataType.CORE_TEMPERATURE,
    PowerDataType.BOARD_TEMPERATURE,
    PowerDataType.SET_VOLTAGE_LIMIT,
    PowerDataType.SET_CURRENT_LIMIT,
    PowerDataType.CC_CV_MODE,
    PowerDataType.POWER_STATE,
    PowerDataType.FAULT_STATE,
    PowerDataType.STATE_MACHINE_FLAG_BITS,
    PowerDataType.STATE_MACHINE_STATE,
    PowerDataType.OTP_VALUE,
    PowerDataType.OTP_SET_VALUE,
    PowerDataType.OVP_VALUE,
    PowerDataType.OVP_SET_VALUE,
    PowerDataType.OCP_VALUE,
    PowerDataType.OCP_SET_VALUE,
    PowerDataType.DUTY_CMD,
    PowerDataType.PWM_A_COMPARE,
    PowerDataType.PWM_D_COMPARE,
    PowerDataType.FAN_SPEED,
    PowerDataType.FAN_SET_VALUE,
)

REPORT_STATUS_TYPES = STATUS_TYPES

STREAM_FAST_TYPES = (
    PowerDataType.INPUT_VOLTAGE,
    PowerDataType.INPUT_CURRENT,
    PowerDataType.OUTPUT_VOLTAGE,
    PowerDataType.OUTPUT_CURRENT,
)

STREAM_SLOW_TYPES = (
    PowerDataType.CORE_TEMPERATURE,
    PowerDataType.BOARD_TEMPERATURE,
    PowerDataType.FAN_SPEED,
    PowerDataType.FAN_SET_VALUE,
)

STREAM_VALUE_LENGTHS: dict[PowerDataType, int] = {
    type_id: 2 for type_id in STREAM_FAST_TYPES + STREAM_SLOW_TYPES
}

DEFAULT_STATUS_VALUES: dict[PowerDataType, int] = {
    PowerDataType.INPUT_VOLTAGE: 0,
    PowerDataType.INPUT_CURRENT: 0,
    PowerDataType.OUTPUT_VOLTAGE: 0,
    PowerDataType.OUTPUT_CURRENT: 0,
    PowerDataType.CORE_TEMPERATURE: 0,
    PowerDataType.BOARD_TEMPERATURE: 0,
    PowerDataType.SET_VOLTAGE_LIMIT: 0,
    PowerDataType.SET_CURRENT_LIMIT: 0,
    PowerDataType.CC_CV_MODE: 0,
    PowerDataType.POWER_STATE: 0,
    PowerDataType.FAULT_STATE: 0,
    PowerDataType.STATE_MACHINE_FLAG_BITS: 0,
    PowerDataType.STATE_MACHINE_STATE: 0,
    PowerDataType.OTP_VALUE: 0,
    PowerDataType.OTP_SET_VALUE: 0,
    PowerDataType.OVP_VALUE: 0,
    PowerDataType.OVP_SET_VALUE: 0,
    PowerDataType.OCP_VALUE: 0,
    PowerDataType.OCP_SET_VALUE: 0,
    PowerDataType.DUTY_CMD: 0,
    PowerDataType.PWM_A_COMPARE: 0,
    PowerDataType.PWM_D_COMPARE: 0,
    PowerDataType.FAN_SPEED: 0,
    PowerDataType.FAN_SET_VALUE: 0,
}

# ========================= session_power.py stop ===================================== #


# ========================= session_daplink.py start ===================================== #
DAPLINK_FLASH_TIMEOUT_MS = 5 * 60 * 1000
PYOCD_PROGRESS_PHASE_RANGES = {"erase": (0.0, 20.0),
                               "program": (20.0, 100.0)}
PYOCD_DEFAULT_PROGRESS_STEPS = 40
SUPPORTED_TARGET_KEYWORDS = ("g474", "h743", "h750")
SUPPORTED_PACK_NAME_KEYWORDS = ("g474", "h743", "h750")
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
PYOCD_PROGRESS_FRAGMENT_RE = re.compile(r"^[\[\]\-=|\s]+$")

# ========================= session_daplink.py stop ===================================== #



