# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 02-12 19:45
#  @FileName: bluetooth_const.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------

class BluetoothConst:
    # Bluetooth service UUIDs
    F4CP_SERVICE_UUID = "0000xxxx-0000-1000-8000-00805f9b34fb"  # Replace with actual UUID
    F4CP_CHARACTERISTIC_UUID = "0000yyyy-0000-1000-8000-00805f9b34fb"  # Replace with actual UUID

    # Bluetooth device name prefix
    DEVICE_NAME_PREFIX = "F4CP"

    # Bluetooth connection states
    STATE_DISCONNECTED = 0
    STATE_CONNECTING = 1
    STATE_CONNECTED = 2
    STATE_DISCONNECTING = 3