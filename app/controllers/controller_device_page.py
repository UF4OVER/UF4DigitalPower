# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 06-03 15:30
#  @FileName: controller_device_page.py
#  @FileType: 串口调试页面控制器文件，负责连接、收发和 TLV 操作入口编排
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

from config import cfg

if TYPE_CHECKING:
    from app.widgets.pages.page_device import DevicePage


class DevicePageController(QObject):
    """把设备调试页的用户动作和页面事件集中绑定。"""

    def __init__(self, page: "DevicePage"):
        super().__init__(page)
        self.page = page

    def bind(self) -> None:
        page = self.page

        # 这些连接是页面与业务动作之间的边界，后续可继续向 service 层下沉。
        cfg.themeChanged.connect(page._onThemeChanged)
        page.refreshButton.clicked.connect(page.refreshCurrentConnectionTargets)
        page.connectButton.clicked.connect(page.toggleConnection)
        page.connectionTypeCombo.currentTextChanged.connect(page._onConnectionTypeChanged)
        page.sendButton.clicked.connect(page.onSend)
        page.clearButton.clicked.connect(self.clearLog)
        page.modeCombo.currentIndexChanged.connect(page._applyMode)
        page.addTlvBtn.clicked.connect(page._addDefaultTlvRow)
        page.delTlvBtn.clicked.connect(page._deleteSelectedTlvRows)
        page.exportTlvBtn.clicked.connect(page._exportTlvJsonToTx)
        page.importTlvBtn.clicked.connect(page._importTlvJsonFromTx)

        page.rxEventSignal.connect(page._appendLog)
        page.stateSignal.connect(page._onState)
        page.errSignal.connect(page._onError)

    def clearLog(self) -> None:
        self.page.logEdit.setPlainText("")
