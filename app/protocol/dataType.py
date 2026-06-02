# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: dataType.py
#  @FileType: 协议封装文件，负责帧、载荷和数据类型的编解码
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

import ctypes


class TypeBase:
    typeId = None

    def encode(self, value) -> bytes:
        raise NotImplementedError

    def decode(self, data: bytes):
        raise NotImplementedError


class DataInt(TypeBase):
    def __init__(self, typeId, size, signed=False, name=None):
        self.typeId = typeId
        self.size = size
        self.signed = signed
        self.name = name or f"int{size*8}"

    def encode(self, value):
        max_val = (1 << (8 * self.size)) - 1
        min_val = 0 if not self.signed else -(1 << (8 * self.size - 1))

        if not (min_val <= value <= max_val):
            raise ValueError(f"value {value} out of range for {self.size} bytes")

        return value.to_bytes(self.size, "little", signed=self.signed)

    def decode(self, data):
        return int.from_bytes(data, "little", signed=self.signed)


class DataFloat(TypeBase):
    def __init__(self, typeId):
        self.typeId = typeId

    def encode(self, value):
        f = ctypes.c_float(value)
        i = ctypes.cast(ctypes.pointer(f), ctypes.POINTER(ctypes.c_uint32)).contents.value
        return i.to_bytes(4, "little")

    def decode(self, data):
        if len(data) != 4:
            raise ValueError("float must be 4 bytes")

        i = int.from_bytes(data, "little")
        return ctypes.cast(
            ctypes.pointer(ctypes.c_uint32(i)),
            ctypes.POINTER(ctypes.c_float)
        ).contents.value


class DataString(TypeBase):
    def __init__(self, typeId):
        self.typeId = typeId

    def encode(self, value: str):
        return value.encode("utf-8")

    def decode(self, data):
        return data.decode("utf-8")


class DataBytes(TypeBase):
    def __init__(self, typeId):
        self.typeId = typeId

    def encode(self, value: bytes):
        return value

    def decode(self, data):
        return data


class Types:
    U8 = DataInt(0x01, 1, name="u8")
    U16 = DataInt(0x02, 2, name="u16")
    U32 = DataInt(0x03, 4, name="u32")

    FLOAT = DataFloat(0x10)
    STRING = DataString(0x20)


TYPE_REGISTRY = {
    Types.U8.typeId: Types.U8,
    Types.U16.typeId: Types.U16,
    Types.U32.typeId: Types.U32,
    Types.FLOAT.typeId: Types.FLOAT,
    Types.STRING.typeId: Types.STRING,
}


