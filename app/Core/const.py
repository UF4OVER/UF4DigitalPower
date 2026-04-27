# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 02-12 20:18
#  @FileName: const.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 相关常量定义
#  @Python  : 3.10
# -------------------------------

from enum import IntEnum, Enum
from typing import Optional, Tuple, Type

from qfluentwidgets import FluentIcon


class WINDOWS:
    windows = {}

class NotificationType(Enum):
        Success = 0
        Error = 1
        Debugging = 2
        Information = 3
        Warning = 4


class NotificationColorMapBase(Enum):
    """Base enum for popup colors; subclass this to add/override mappings."""

    @property
    def notification_type(self) -> NotificationType:
        return self.value[0]

    @property
    def theme_color(self) -> str:
        return self.value[1]

    @property
    def background_color(self) -> str:
        return self.value[2]


class NotificationIconMapBase(Enum):
    """Base enum for popup icons; subclass this to add/override mappings."""

    @property
    def notification_type(self) -> NotificationType:
        return self.value[0]

    @property
    def icon(self) -> FluentIcon:
        return self.value[1]


class DefaultNotificationColors(NotificationColorMapBase):
    Success = (NotificationType.Success, "#1f7a3e", "#d8f3df")
    Error = (NotificationType.Error, "#b42318", "#fee4e2")
    Debugging = (NotificationType.Debugging, "#175cd3", "#d1e9ff")
    Information = (NotificationType.Information, "#6941c6", "#ebe9fe")
    Warning = (NotificationType.Warning, "#b54708", "#fef0c7")


class DefaultNotificationIcons(NotificationIconMapBase):
    Success = (NotificationType.Success, FluentIcon.COMPLETED)
    Error = (NotificationType.Error, FluentIcon.CLOSE)
    Debugging = (NotificationType.Debugging, FluentIcon.UPDATE)
    Information = (NotificationType.Information, FluentIcon.INFO)
    Warning = (NotificationType.Warning, FluentIcon.FEEDBACK)


def _resolve_color_from_enum(enum_cls: Type[NotificationColorMapBase], n_type: NotificationType) -> Optional[Tuple[str, str]]:
    for item in enum_cls:
        if item.notification_type == n_type:
            return item.theme_color, item.background_color
    return None


def _resolve_icon_from_enum(enum_cls: Type[NotificationIconMapBase], n_type: NotificationType) -> Optional[FluentIcon]:
    for item in enum_cls:
        if item.notification_type == n_type:
            return item.icon
    return None


def resolve_notification_colors(n_type: NotificationType, *color_enums: Type[NotificationColorMapBase]) -> Tuple[str, str]:
    """Resolve colors from custom enums first, then fallback to defaults."""
    enum_chain = color_enums or (DefaultNotificationColors,)
    if DefaultNotificationColors not in enum_chain:
        enum_chain = (*enum_chain, DefaultNotificationColors)

    for enum_cls in enum_chain:
        colors = _resolve_color_from_enum(enum_cls, n_type)
        if colors:
            return colors

    return DefaultNotificationColors.Information.theme_color, DefaultNotificationColors.Information.background_color


def resolve_notification_icon(n_type: NotificationType, *icon_enums: Type[NotificationIconMapBase]) -> FluentIcon:
    """Resolve icon from custom enums first, then fallback to defaults."""
    enum_chain = icon_enums or (DefaultNotificationIcons,)
    if DefaultNotificationIcons not in enum_chain:
        enum_chain = (*enum_chain, DefaultNotificationIcons)

    for enum_cls in enum_chain:
        icon = _resolve_icon_from_enum(enum_cls, n_type)
        if icon is not None:
            return icon

    return DefaultNotificationIcons.Information.icon


class DeviceData(IntEnum):
    VID = 2001  # 设备VID
    PID = 8738  # 设备PID

class BluetoothState(IntEnum):  # 蓝牙连接状态
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    DISCONNECTING = 3

"""
TLV 协议相关常量定义 发送示例: 

send(DataType.xxx, value)
send(DataType.FAULT_STATE, FaultCode.xxxx)
send(DataType.STATE_MACHINE_FLAG_BITS_STATE, StateMachineFlagBits.xxxx)
send(DataType.STATE_MACHINE_STATE, StateMachineFlag.xxxx)

"""


class TVL_DataType(IntEnum):  # 数据类型
    """
    TLV 协议中定义的数据类型
    仅供参考，具体含义请参考设备文档
    仅读取数据时，使用 ONLY READ 标记
    读取或写入数据时，使用 READ or WRITE 标记
    """
    INPUT_VOLTAGE = 10  # 单位: mV  ONLY READ
    INPUT_CURRENT = 11  # 单位: mA  ONLY READ
    OUTPUT_VOLTAGE = 12  # 单位: mV  ONLY READ
    OUTPUT_CURRENT = 13  # 单位: mA  ONLY READ
    CORE_TEMPERATURE = 14  # 单位: ℃  ONLY READ
    BOARD_TEMPERATURE = 15  # 单位: ℃  ONLY READ

    SET_VOLTAGE_LIMIT = 17  # 单位: mV  READ or WRITE
    SET_CURRENT_LIMIT = 18  # 单位: mA  READ or WRITE

    CC_CV_MODE = 20  # 0: CC, 1: CV  READ or WRITE
    POWER_STATE = 21  # 0: Off, 1: On  ONLY READ

    FAULT_STATE = 22  # 故障状态代码  ONLY READ

    STATE_MACHINE_FLAG_BITS_STATE = 23  # 状态机标志位  ONLY READ
    STATE_MACHINE_STATE = 24  # 状态机状态  ONLY READ

    INPUT_VOLTAGE_RAW = 25  # 原始ADC值，数据类型为 UNIT32  ONLY READ
    INPUT_CURRENT_RAW = 26  # ONLY READ
    OUTPUT_VOLTAGE_RAW = 27  # ONLY READ
    OUTPUT_CURRENT_RAW = 28  # ONLY READ

    OTP_VALUE = 29  # 过温保护设定值  ONLY READ
    OTP_SET_VALUE = 30  # 设置过温保护值  READ or WRITE

    OVP_VALUE = 31  # 过压保护设定值  ONLY READ
    OVP_SET_VALUE = 32  # 设置过压保护值  READ or WRITE

    OCP_VALUE = 33  # 过流保护设定值  ONLY READ
    OCP_SET_VALUE = 34  # 设置过流保护值  READ or WRITE

    FAN_SPEED = 38  # 单位: RPM  ONLY READ
    FAN_SET_VALUE = 39  # 设置风扇转速值，单位: RPM  READ or WRITE


class TVL_FaultCode(IntEnum):  # 故障代码
    """
    DataType.FAULT_STATE 对应的故障代码定义

    NO_ERROR: 表示无故障
    INPUT_UNDER_VOLTAGE 表示输入欠压
    INPUT_OVER_VOLTAGE 表示输入过压
    OUTPUT_UNDER_VOLTAGE 表示输出欠压
    OUTPUT_OVER_VOLTAGE 表示输出过压
    OUTPUT_OVER_CURRENT 表示输出过流
    OUTPUT_SHORT_CIRCUIT 表示输出短路
    OVER_TEMPERATURE_PROTECTION 表示温度过高
    """

    NO_ERROR = 0x0000  # 无故障
    INPUT_UNDER_VOLTAGE = 0x0001  # 输入欠压
    INPUT_OVER_VOLTAGE = 0x0002  # 输入过压
    OUTPUT_UNDER_VOLTAGE = 0x0004  # 输出欠压
    OUTPUT_OVER_VOLTAGE = 0x0008  # 输出过压
    OUTPUT_OVER_CURRENT = 0x0010  # 输出过流
    OUTPUT_SHORT_CIRCUIT = 0x0020  # 输出短路
    OVER_TEMPERATURE_PROTECTION = 0x0040  # 温度过高


class TVL_StateMachineFlagBits(IntEnum):  # 状态机标志位
    """
    DataType.SMFB_STATE 对应的状态机标志位定义
    INIT: 初始化状态
    WAIT: 空闲等待状态
    RISE: 软启状态
    RUN: 正常运行状态
    ERR: 故障状态
    """
    INIT = 0b0001  # 初始化
    WAIT = 0b0010  # 空闲等待
    RISE = 0b0100  # 软启
    RUN = 0b1000  # 正常运行
    ERR = 0b1111  # 故障


class TVL_StateMachineFlag(IntEnum):  # 状态机状态
    """
    DataType.SMS_STATE 对应的状态机状态定义
    NA: 未定义
    BUCK: BUCK模式
    BOOST: BOOST模式
    MIX: MIX混合模式
    """
    NA = 0  # 未定义
    BUCK = 1  # BUCK模式
    BOOST = 2  # BOOST模式
    MIX = 3  # MIX混合模式


class TVL_Command(IntEnum):  # 命令代码
    """
    TLV协议中定义的命令代码
    仅供参考，具体含义请参考设备文档
    """
    pass

    # READ = 0x01  # 读取数据
    # WRITE = 0x02  # 写入数据
    # NOTIFY = 0x03  # 设备主动通知数据