import re
import unittest
from pathlib import Path

from App.Core.Session.session_power import PowerCommand, PowerDataType


ROOT = Path(__file__).resolve().parents[2]
USER_TVLCOM_H = ROOT / "UF4DigitalPower" / "USER" / "Inc" / "user_tvlcom.h"


def _parse_enum(prefix: str) -> dict[str, int]:
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
