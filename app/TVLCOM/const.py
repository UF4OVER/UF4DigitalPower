# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : TVLCOM
#  @Time    : 2026 - 01-19 15:09
#  @FileName: const.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------

SOF = 0x7E
EOF = 0x7F

PROTO_VER = 0x01

FLAG_ACK_REQ = 0x01
FLAG_IS_ACK  = 0x02
FLAG_IS_NACK = 0x04

TLV_STRING  = 0x01
TLV_INT32   = 0x02
TLV_UINT32  = 0x03
TLV_FLOAT   = 0x04
TLV_BINARY  = 0x05

TLV_RPC_REQ  = 0x80
TLV_RPC_RESP = 0x81
