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
from pathlib import Path

from app.session.session_power import PowerCommand, PowerDataType


ROOT = Path(__file__).resolve().parents[2]
USER_TVLCOM_H = ROOT / "UF4DigitalPower" / "USER" / "Inc" / "user_tvlcom.h"


def _parse_enum(prefix: str) -> dict[str, int]:
    if not USER_TVLCOM_H.exists():
        raise unittest.SkipTest(f"Firmware protocol header not found: {USER_TVLCOM_H}")
    text = USER_TVLCOM_H.read_text(encoding="utf-8")
    result: dict[str, int] = {}
    for name, value in re.findall(rf"\b({prefix}[A-Z0-9_]+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)U?", text):
        result[name.removeprefix(prefix)] = int(value, 0)
    return result


class PowerProtocolConstantTests(unittest.TestCase):
    def test_command_values_match_firmware_header(self):
        firmware_commands = _parse_enum("USER_TVL_CMD_")
        host_commands = {item.name: int(item) for item in PowerCommand}

        self.assertEqual(host_commands, firmware_commands)

    def test_data_type_values_match_firmware_header(self):
        firmware_types = _parse_enum("USER_TVL_")
        firmware_types.pop("CMD_ACK", None)
        firmware_types.pop("CMD_READ", None)
        firmware_types.pop("CMD_WRITE", None)
        firmware_types.pop("CMD_REPORT", None)
        firmware_types.pop("CMD_NACK", None)
        firmware_types.pop("VALUE_U8", None)
        firmware_types.pop("VALUE_U32", None)
        firmware_types.pop("ACCESS_READ", None)
        firmware_types.pop("ACCESS_WRITE", None)
        firmware_types.pop("ACCESS_READ_WRITE", None)

        host_types = {item.name: int(item) for item in PowerDataType}
        host_types.pop("APP_TVL_DEBUG_SNAPSHOT", None)

        self.assertEqual(host_types, firmware_types)


if __name__ == "__main__":
    unittest.main()
