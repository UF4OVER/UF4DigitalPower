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

import os
import re
import unittest
from pathlib import Path

from app.core.const import POWER_DATA_META, REPORT_STATUS_TYPES
from app.session.session_power import PowerCommand, PowerDataType


HOST_ROOT = Path(__file__).resolve().parents[1]
FIRMWARE_ROOT = Path(os.environ.get("UF4DIGITALPOWER_ROOT", r"E:\PROJECT_C\UF4DigitalPower"))


def _detect_uf4com_root() -> Path:
    env_root = os.environ.get("UF4COM_ROOT")
    if env_root:
        return Path(env_root)

    cmake_file = FIRMWARE_ROOT / "CMakeLists.txt"
    if cmake_file.exists():
        text = cmake_file.read_text(encoding="utf-8")
        match = re.search(r'set\(UF4COM_ROOT\s+"(?P<path>[^"]+)"\)', text)
        if match is not None:
            return Path(match.group("path"))

    return Path(r"E:\PROJECT_C\UF4COM")


UF4COM_ROOT = _detect_uf4com_root()
UF4COM_HEADER = UF4COM_ROOT / "uf4com" / "protocol" / "Inc" / "uf4com.h"
UF4_TRANSPORT_C = FIRMWARE_ROOT / "Core" / "Src" / "uf4_transport.c"
PROTOCOL_DOCUMENT = HOST_ROOT / "docs" / "README.md"

COMMAND_NAME_MAP = {
    "READ_REQ": "READ",
    "READ_RSP": "READ_RSP",
    "WRITE_REQ": "WRITE",
    "WRITE_RSP": "WRITE_RSP",
    "STREAM_START_REQ": "STREAM_START",
    "STREAM_START_RSP": "STREAM_START_RSP",
    "STREAM_STOP_REQ": "STREAM_STOP",
    "STREAM_STOP_RSP": "STREAM_STOP_RSP",
    "STREAM_DATA": "STREAM_DATA",
}

DATA_TYPE_ALIAS_MAP = {
    "BOARD_TEMPERATURE": "TEMP1_TEMPERATURE",
}


def _normalize_type_name(name: str) -> str:
    return DATA_TYPE_ALIAS_MAP.get(name, name)


def _parse_define_map(path: Path, prefix: str) -> dict[str, int]:
    if not path.exists():
        raise unittest.SkipTest(f"Protocol header not found: {path}")

    text = path.read_text(encoding="utf-8")
    result: dict[str, int] = {}
    pattern = rf"^\s*#define\s+({prefix}[A-Z0-9_]+)\s+(0x[0-9A-Fa-f]+|\d+)[uU]?\b"
    for name, value in re.findall(pattern, text, flags=re.M):
        result[name.removeprefix(prefix)] = int(value, 0)
    return result


def _parse_firmware_registered_ids() -> list[str]:
    if not UF4_TRANSPORT_C.exists():
        raise unittest.SkipTest(f"Firmware transport source not found: {UF4_TRANSPORT_C}")

    text = UF4_TRANSPORT_C.read_text(encoding="utf-8")
    match = re.search(
        r"static\s+uf4_id_t\s+s_uf4_id_table\[\]\s*=\s*\{(?P<body>.*?)\};",
        text,
        flags=re.S,
    )
    if match is None:
        raise AssertionError("Firmware UF4 ID table not found")

    return [
        name.removeprefix("UF4_ID_")
        for name in re.findall(r"UF4_ID_[A-Z0-9_]+", match.group("body"))
    ]


def _parse_documented_id_names() -> list[str]:
    if not PROTOCOL_DOCUMENT.exists():
        raise unittest.SkipTest(f"Protocol document not found: {PROTOCOL_DOCUMENT}")

    text = PROTOCOL_DOCUMENT.read_text(encoding="utf-8")
    match = re.search(
        r"# 14\. 数据ID定义(?P<section>.*?)# 15\.",
        text,
        flags=re.S,
    )
    if match is None:
        raise AssertionError("Protocol document ID section not found")

    return re.findall(
        r"^\|\s*0x[0-9A-Fa-f]+\s*\|\s*([A-Z0-9_]+)\s*\|",
        match.group("section"),
        flags=re.M,
    )


def _host_command_map() -> dict[str, int]:
    return {name: int(item) for name, item in PowerCommand.__members__.items()}


def _firmware_command_map() -> dict[str, int]:
    raw_commands = _parse_define_map(UF4COM_HEADER, "UF4_CMD_")
    return {COMMAND_NAME_MAP[name]: value for name, value in raw_commands.items() if name in COMMAND_NAME_MAP}


def _host_data_type_map() -> dict[str, int]:
    result: dict[str, int] = {}
    for name, item in PowerDataType.__members__.items():
        if name == "DEBUG_SNAPSHOT":
            continue
        result[_normalize_type_name(name)] = int(item)
    return result


def _firmware_data_type_map() -> dict[str, int]:
    return _parse_define_map(UF4COM_HEADER, "UF4_ID_")


def _host_report_status_names() -> list[str]:
    return [_normalize_type_name(item.name) for item in REPORT_STATUS_TYPES]


def _assert_is_subset(test_case: unittest.TestCase, expected_items: list[str], actual_items: set[str], source: str) -> None:
    missing = [name for name in expected_items if name not in actual_items]
    test_case.assertEqual([], missing, f"Missing in {source}: {', '.join(missing)}")


def _assert_u16_meta(test_case: unittest.TestCase, type_ids: tuple[PowerDataType, ...]) -> None:
    for type_id in type_ids:
        meta = POWER_DATA_META[type_id]
        test_case.assertEqual(meta.length, 2)
        test_case.assertFalse(meta.signed)


def _assert_registered_and_documented(test_case: unittest.TestCase, type_ids: tuple[PowerDataType, ...]) -> None:
    firmware_types = _firmware_data_type_map()
    documented_types = set(_parse_documented_id_names())
    for type_id in type_ids:
        normalized_name = _normalize_type_name(type_id.name)
        test_case.assertIn(normalized_name, firmware_types)
        test_case.assertIn(normalized_name, documented_types)


CURRENT_TYPES = (
    PowerDataType.INPUT_CURRENT,
    PowerDataType.OUTPUT_CURRENT,
)

TEMPERATURE_TYPES = (
    PowerDataType.CORE_TEMPERATURE,
    PowerDataType.BOARD_TEMPERATURE,
    PowerDataType.TEMP2_TEMPERATURE,
)


class PowerProtocolConstantTests(unittest.TestCase):
    def test_command_values_match_uf4com_header(self):
        self.assertEqual(_host_command_map(), _firmware_command_map())

    def test_data_type_values_match_uf4com_header(self):
        self.assertEqual(_host_data_type_map(), _firmware_data_type_map())

    def test_report_status_types_are_registered_in_firmware(self):
        host = _host_report_status_names()
        firmware = set(_parse_firmware_registered_ids())
        _assert_is_subset(self, host, firmware, "firmware UF4 ID table")

    def test_report_status_types_are_documented(self):
        host = _host_report_status_names()
        documented = set(_parse_documented_id_names())
        _assert_is_subset(self, host, documented, "protocol document")

    def test_current_values_use_fixed_u16_tv_payload(self):
        _assert_registered_and_documented(self, CURRENT_TYPES)
        _assert_u16_meta(self, CURRENT_TYPES)

    def test_temperature_values_use_fixed_u16_tv_payload(self):
        _assert_registered_and_documented(self, TEMPERATURE_TYPES)
        _assert_u16_meta(self, TEMPERATURE_TYPES)

    def test_protocol_document_declares_fixed_u16_values(self):
        if not PROTOCOL_DOCUMENT.exists():
            raise unittest.SkipTest(f"Protocol document not found: {PROTOCOL_DOCUMENT}")

        text = PROTOCOL_DOCUMENT.read_text(encoding="utf-8")
        self.assertIn("固定长度 TV 格式", text)
        self.assertRegex(text, r"\|\s*uint16_t\s*\|\s*2 Byte\s*\|")


if __name__ == "__main__":
    unittest.main()
