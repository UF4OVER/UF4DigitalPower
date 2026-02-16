# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 02-15 16:40
#  @FileName: solt_bus.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------
from PyQt5.QtCore import pyqtSignal, QObject


class SignalBus(QObject):
    """ Signal bus """

    enableAcrylicBackground = pyqtSignal(bool)


Bus = SignalBus()