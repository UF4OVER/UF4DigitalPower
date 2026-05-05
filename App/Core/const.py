# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 02-12 20:18
#  @FileName: const.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : related constant definitions
#  @Python  : 3.10
# -------------------------------

from enum import Enum, IntEnum


class BluetoothState(IntEnum):
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    DISCONNECTING = 3


class TVL_DataType(IntEnum):
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

    STATE_MACHINE_FLAG_BITS_STATE = 23
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

    FAN_SPEED = 38
    FAN_SET_VALUE = 39


class TVL_FaultCode(IntEnum):
    NO_ERROR = 0x0000
    INPUT_UNDER_VOLTAGE = 0x0001
    INPUT_OVER_VOLTAGE = 0x0002
    OUTPUT_UNDER_VOLTAGE = 0x0004
    OUTPUT_OVER_VOLTAGE = 0x0008
    OUTPUT_OVER_CURRENT = 0x0010
    OUTPUT_SHORT_CIRCUIT = 0x0020
    OVER_TEMPERATURE_PROTECTION = 0x0040


class TVL_StateMachineFlagBits(IntEnum):
    INIT = 0b0001
    WAIT = 0b0010
    RISE = 0b0100
    RUN = 0b1000
    ERR = 0b1111


class TVL_StateMachineFlag(IntEnum):
    NA = 0
    BUCK = 1
    BOOST = 2
    MIX = 3


class TVL_Command(IntEnum):
    pass


SESSION_PAGE_BAUD_RATES = ("9600", "19200", "38400", "57600", "115200")
SESSION_PAGE_SEND_MODES = ("Raw(HEX/ASCII)", "TVLCOM_V2")
SESSION_PAGE_RAW_FORMATS = ("HEX", "ASCII")
SESSION_PAGE_V2_DEFAULT_CMD = 0x01

SESSION_PAGE_V2_TYPE_ALIAS_TO_ID = {
    "u8": 0x01,
    "uint8": 0x01,
    "u16": 0x02,
    "uint16": 0x02,
    "u32": 0x03,
    "uint32": 0x03,
    "float": 0x10,
    "string": 0x20,
}
