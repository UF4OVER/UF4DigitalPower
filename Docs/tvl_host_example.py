from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from enum import IntEnum

import serial


class TVLCommand(IntEnum):
    ACK = 0x00
    READ = 0x01
    WRITE = 0x02
    REPORT = 0x03
    NACK = 0xFF


class TVLDataType(IntEnum):
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

    FAN_SPEED = 38
    FAN_SET_VALUE = 39
    DEBUG_SNAPSHOT = 40


SOF = b"\xAA\x55"


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def pack_tlv(data_type: int, value: bytes) -> bytes:
    return struct.pack("<BH", data_type, len(value)) + value


def pack_u8(data_type: int, value: int) -> bytes:
    return pack_tlv(data_type, struct.pack("<B", value))


def pack_u32(data_type: int, value: int) -> bytes:
    return pack_tlv(data_type, struct.pack("<I", value))


def build_frame(cmd: int, seq: int, payload: bytes = b"") -> bytes:
    body = struct.pack("<BB", cmd, seq) + payload
    frame_wo_crc = SOF + struct.pack("<H", len(body)) + body
    crc = crc16_modbus(frame_wo_crc)
    return frame_wo_crc + struct.pack("<H", crc)


def parse_tlvs(payload: bytes) -> dict[int, bytes]:
    result: dict[int, bytes] = {}
    offset = 0
    while offset < len(payload):
        if offset + 3 > len(payload):
            raise ValueError("bad TLV header")
        data_type, length = struct.unpack_from("<BH", payload, offset)
        offset += 3
        if offset + length > len(payload):
            raise ValueError("bad TLV payload")
        result[data_type] = payload[offset:offset + length]
        offset += length
    return result


def decode_u8(raw: bytes) -> int:
    return struct.unpack("<B", raw)[0]


def decode_u32(raw: bytes) -> int:
    return struct.unpack("<I", raw)[0]


def decode_status_values(result: dict[int, bytes]) -> PowerStatus:
    return PowerStatus(
        vin_v=decode_u32(result[TVLDataType.INPUT_VOLTAGE]) / 1000.0,
        iin_a=decode_u32(result[TVLDataType.INPUT_CURRENT]) / 1000.0,
        vout_v=decode_u32(result[TVLDataType.OUTPUT_VOLTAGE]) / 1000.0,
        iout_a=decode_u32(result[TVLDataType.OUTPUT_CURRENT]) / 1000.0,
        core_temp_c=decode_u32(result[TVLDataType.CORE_TEMPERATURE]) / 1000.0,
        board_temp_c=decode_u32(result[TVLDataType.BOARD_TEMPERATURE]) / 1000.0,
        cc_cv_mode=decode_u8(result[TVLDataType.CC_CV_MODE]),
        power_state=decode_u8(result[TVLDataType.POWER_STATE]),
        fault_state=decode_u32(result[TVLDataType.FAULT_STATE]),
        state_bits=decode_u8(result[TVLDataType.STATE_MACHINE_FLAG_BITS]),
        topology_state=decode_u8(result[TVLDataType.STATE_MACHINE_STATE]),
        fan_speed=decode_u32(result[TVLDataType.FAN_SPEED]),
        set_voltage_v=decode_u32(result[TVLDataType.SET_VOLTAGE_LIMIT]) / 1000.0
        if TVLDataType.SET_VOLTAGE_LIMIT in result
        else None,
        set_current_a=decode_u32(result[TVLDataType.SET_CURRENT_LIMIT]) / 1000.0
        if TVLDataType.SET_CURRENT_LIMIT in result
        else None,
    )


@dataclass
class PowerStatus:
    vin_v: float
    iin_a: float
    vout_v: float
    iout_a: float
    core_temp_c: float
    board_temp_c: float
    cc_cv_mode: int
    power_state: int
    fault_state: int
    state_bits: int
    topology_state: int
    fan_speed: int
    set_voltage_v: float | None = None
    set_current_a: float | None = None


class TVLHost:
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.5):
        self.ser = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
        self.seq = 0

    def close(self) -> None:
        self.ser.close()

    def _next_seq(self) -> int:
        self.seq = (self.seq + 1) & 0xFF
        return self.seq

    def _read_exact(self, size: int) -> bytes:
        data = self.ser.read(size)
        if len(data) != size:
            raise TimeoutError(f"serial read timeout, want={size}, got={len(data)}")
        return data

    def _read_frame(self) -> tuple[int, int, bytes]:
        while True:
            head = self._read_exact(2)
            if head == SOF:
                break

        body_len = struct.unpack("<H", self._read_exact(2))[0]
        body = self._read_exact(body_len)
        recv_crc = struct.unpack("<H", self._read_exact(2))[0]
        frame_wo_crc = SOF + struct.pack("<H", body_len) + body
        calc_crc = crc16_modbus(frame_wo_crc)
        if recv_crc != calc_crc:
            raise ValueError(f"crc mismatch: recv=0x{recv_crc:04X}, calc=0x{calc_crc:04X}")

        cmd, seq = struct.unpack_from("<BB", body, 0)
        payload = body[2:]
        return cmd, seq, payload

    def request(self, cmd: TVLCommand, payload: bytes = b"") -> dict[int, bytes]:
        seq = self._next_seq()
        frame = build_frame(cmd, seq, payload)
        self.ser.write(frame)

        while True:
            resp_cmd, resp_seq, resp_payload = self._read_frame()
            if resp_cmd == TVLCommand.REPORT:
                continue
            if resp_seq != seq:
                raise ValueError(f"seq mismatch: resp={resp_seq}, req={seq}")
            if resp_cmd == TVLCommand.NACK:
                raise RuntimeError("device returned NACK")
            if resp_cmd != TVLCommand.ACK:
                raise ValueError(f"unexpected response cmd=0x{resp_cmd:02X}")
            return parse_tlvs(resp_payload)

    def read_report(self) -> dict[int, bytes]:
        while True:
            cmd, _seq, payload = self._read_frame()
            if cmd == TVLCommand.REPORT:
                return parse_tlvs(payload)

    def read_report_status(self) -> PowerStatus:
        return decode_status_values(self.read_report())

    def read_values(self, *data_types: TVLDataType) -> dict[int, bytes]:
        payload = b"".join(pack_tlv(int(data_type), b"") for data_type in data_types)
        return self.request(TVLCommand.READ, payload)

    def write_u32(self, data_type: TVLDataType, value: int) -> None:
        self.request(TVLCommand.WRITE, pack_u32(int(data_type), value))

    def write_u8(self, data_type: TVLDataType, value: int) -> None:
        self.request(TVLCommand.WRITE, pack_u8(int(data_type), value))

    def set_voltage_limit_mv(self, value_mv: int) -> None:
        self.write_u32(TVLDataType.SET_VOLTAGE_LIMIT, value_mv)

    def set_current_limit_ma(self, value_ma: int) -> None:
        self.write_u32(TVLDataType.SET_CURRENT_LIMIT, value_ma)

    def set_output(self, voltage_v: float, current_a: float, enabled: bool = True) -> None:
        payload = b"".join(
            (
                pack_u32(TVLDataType.SET_VOLTAGE_LIMIT, int(voltage_v * 1000.0 + 0.5)),
                pack_u32(TVLDataType.SET_CURRENT_LIMIT, int(current_a * 1000.0 + 0.5)),
                pack_u8(TVLDataType.POWER_STATE, 1 if enabled else 0),
            )
        )
        self.request(TVLCommand.WRITE, payload)

    def set_power_state(self, enabled: bool) -> None:
        self.write_u8(TVLDataType.POWER_STATE, 1 if enabled else 0)

    def set_otp_mc(self, value_mc: int) -> None:
        self.write_u32(TVLDataType.OTP_SET_VALUE, value_mc)

    def set_ovp_mv(self, value_mv: int) -> None:
        self.write_u32(TVLDataType.OVP_SET_VALUE, value_mv)

    def set_ocp_ma(self, value_ma: int) -> None:
        self.write_u32(TVLDataType.OCP_SET_VALUE, value_ma)

    def set_fan_value(self, value: int) -> None:
        self.write_u32(TVLDataType.FAN_SET_VALUE, value)

    def read_debug_snapshot(self) -> dict[int, bytes]:
        return self.read_values(TVLDataType.DEBUG_SNAPSHOT)

    def read_status(self) -> PowerStatus:
        result = self.read_values(
            TVLDataType.INPUT_VOLTAGE,
            TVLDataType.INPUT_CURRENT,
            TVLDataType.OUTPUT_VOLTAGE,
            TVLDataType.OUTPUT_CURRENT,
            TVLDataType.CORE_TEMPERATURE,
            TVLDataType.BOARD_TEMPERATURE,
            TVLDataType.SET_VOLTAGE_LIMIT,
            TVLDataType.SET_CURRENT_LIMIT,
            TVLDataType.CC_CV_MODE,
            TVLDataType.POWER_STATE,
            TVLDataType.FAULT_STATE,
            TVLDataType.STATE_MACHINE_FLAG_BITS,
            TVLDataType.STATE_MACHINE_STATE,
            TVLDataType.OTP_VALUE,
            TVLDataType.OTP_SET_VALUE,
            TVLDataType.OVP_VALUE,
            TVLDataType.OVP_SET_VALUE,
            TVLDataType.OCP_VALUE,
            TVLDataType.OCP_SET_VALUE,
            TVLDataType.FAN_SPEED,
            TVLDataType.FAN_SET_VALUE,
        )
        return decode_status_values(result)


def demo() -> None:
    host = TVLHost("COM6", 115200, timeout=1.0)
    try:
        host.set_output(12.0, 3.0, enabled=True)
        host.set_ovp_mv(33000)
        host.set_ocp_ma(10000)
        host.set_otp_mc(80000)

        for _ in range(5):
            status = host.read_report_status()
            print(status)
    finally:
        host.close()


if __name__ == "__main__":
    demo()
