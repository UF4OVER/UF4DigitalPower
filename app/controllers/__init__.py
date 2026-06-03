# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 06-03 15:30
#  @FileName: __init__.py
#  @FileType: 控制器包入口文件，统一导出页面控制器
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from app.controllers.controller_daplink_page import DaplinkPageController
from app.controllers.controller_device_page import DevicePageController
from app.controllers.controller_power_page import PowerPageController

__all__ = [
    "DaplinkPageController",
    "DevicePageController",
    "PowerPageController",
]
