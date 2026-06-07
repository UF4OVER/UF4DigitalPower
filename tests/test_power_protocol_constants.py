# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_power_protocol_constants.py
#  @FileType: 自动化测试文件，用来守住关键功能行为
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

import re
import unittest
import os
from pathlib import Path

from app.core.const import POWER_DATA_META, REPORT_STATUS_TYPES
from app.session.session_power import PowerCommand, PowerDataType


ROOT = Path(__file__).resolve().parents[2]
FIRMWARE_ROOT = Path(os.environ.get("UF4DIGITALPOWER_ROOT", r"E:\PROJECT_C\UF4DigitalPower"))
USER_TVLCOM_H = FIRMWARE_ROOT / "USER" / "APP" / "user_tvlcom_protocol.h"
USER_TVLCOM_C = FIRMWARE_ROOT / "USER" / "APP" / "user_tvlcom_protocol.c"
COMMUNICATION_COMMANDS = ROOT / "COMMUNICATION_COMMANDS.md"


def _parse_enum(prefix: str) -> dict[str, int]:
    if not USER_TVLCOM_H.exists():
        raise unittest.SkipTest(f"Firmware protocol header not found: {USER_TVLCOM_H}")
    text = USER_TVLCOM_H.read_text(encoding="utf-8")
    result: dict[str, int] = {}
    for name, value in re.findall(rf"\b({prefix}[A-Z0-9_]+)\s*=\s*([A-Z0-9_xa-f]+)U?", text):
        value = value.removesuffix("U")
        short_name = name.removeprefix(prefix)
        if re.fullmatch(r"0x[0-9A-Fa-f]+|\d+", value):
            result[short_name] = int(value, 0)
            continue

        ref_name = value.removeprefix(prefix)
        if ref_name == value and value.startswith("USER_TVLCOM_DATA_"):
            ref_name = value.removeprefix("USER_TVLCOM_DATA_")
        result[short_name] = result[ref_name]
    return result


def _parse_firmware_report_types() -> list[str]:
    if not USER_TVLCOM_C.exists():
        raise unittest.SkipTest(f"Firmware protocol source not found: {USER_TVLCOM_C}")

    text = USER_TVLCOM_C.read_text(encoding="utf-8")
    match = re.search(
        r"static\s+const\s+uint8_t\s+s_USER_tvlcomReportTypes\[\]\s*=\s*\{(?P<body>.*?)\};",
        text,
        flags=re.S,
    )
    if match is None:
        raise AssertionError("Firmware report type table not found")

    return [
        name.removeprefix("USER_TVLCOM_DATA_")
        for name in re.findall(r"USER_TVLCOM_DATA_[A-Z0-9_]+", match.group("body"))
    ]


class PowerProtocolConstantTests(unittest.TestCase):
    def test_command_values_match_firmware_header(self):
        firmware_commands = _parse_enum("USER_TVLCOM_CMD_")
        host_commands = {name: int(item) for name, item in PowerCommand.__members__.items()}

        for name, value in firmware_commands.items():
            self.assertIn(name, host_commands)
            self.assertEqual(host_commands[name], value)

    def test_data_type_values_match_firmware_header(self):
        firmware_types = _parse_enum("USER_TVLCOM_DATA_")
        host_types = {name: int(item) for name, item in PowerDataType.__members__.items()}
        host_types.pop("APP_TVL_DEBUG_SNAPSHOT", None)

        self.assertEqual(host_types, firmware_types)

    def test_report_status_types_match_firmware_source(self):
        firmware = _parse_firmware_report_types()
        host = [item.name for item in REPORT_STATUS_TYPES]

        self.assertEqual(host, firmware)

    def test_report_status_types_match_protocol_document(self):
        if not COMMUNICATION_COMMANDS.exists():
            raise unittest.SkipTest(f"Protocol document not found: {COMMUNICATION_COMMANDS}")

        text = COMMUNICATION_COMMANDS.read_text(encoding="utf-8")
        match = re.search(
            r"## 状态组上报(?P<section>.*?)## 连续原始数据流",
            text,
            flags=re.S,
        )
        self.assertIsNotNone(match)

        documented = re.findall(r"TLV\(([A-Z0-9_]+)\)", match.group("section"))
        host = [item.name for item in REPORT_STATUS_TYPES]

        self.assertEqual(host, documented)

    def test_current_values_are_unsigned_u32(self):
        for type_id in (PowerDataType.INPUT_CURRENT, PowerDataType.OUTPUT_CURRENT):
            meta = POWER_DATA_META[type_id]

            self.assertEqual(meta.length, 4)
            self.assertFalse(meta.signed)

    def test_temperature_values_are_signed_i32(self):
        for type_id in (
            PowerDataType.CORE_TEMPERATURE,
            PowerDataType.BOARD_TEMPERATURE,
            PowerDataType.TEMP2_TEMPERATURE,
        ):
            meta = POWER_DATA_META[type_id]

            self.assertEqual(meta.length, 4)
            self.assertTrue(meta.signed)


if __name__ == "__main__":
    unittest.main()
