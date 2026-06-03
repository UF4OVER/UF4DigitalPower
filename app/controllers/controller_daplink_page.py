# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 06-03 15:30
#  @FileName: controller_daplink_page.py
#  @FileType: 烧录页面控制器文件，负责 DAPLink 页面操作入口和启动任务编排
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt5.QtCore import QObject, QTimer

from config import cfg

if TYPE_CHECKING:
    from app.widgets.pages.page_daplink import DaplinkPage


class DaplinkPageController(QObject):
    """集中管理 DAPLink 页面按钮、选择器和启动时异步任务。"""

    def __init__(self, page: "DaplinkPage"):
        super().__init__(page)
        self.page = page

    def bind(self) -> None:
        page = self.page

        # 页面保留具体动作实现，Controller 只负责把控件事件路由过去。
        cfg.themeChanged.connect(page._onThemeChanged)
        page.scanProbeBtn.clicked.connect(page.scanProbe)
        page.connectBtn.clicked.connect(page.readInfo)
        page.targetCombo.currentIndexChanged.connect(page._onTargetChanged)
        page.reloadPackBtn.clicked.connect(page.reloadPackTargets)
        page.targetFilterInput.textChanged.connect(page._applyTargetFilter)

        page.firmwareSourceCombo.currentIndexChanged.connect(page._onFirmwareSourceChanged)
        page.internalFirmwareCombo.currentIndexChanged.connect(page._onInternalFirmwareChanged)
        page.refreshFirmwareButton.clicked.connect(page._reloadInternalFirmwareOptions)
        page.browseButton.clicked.connect(page.browseFile)
        page.downloadButton.clicked.connect(page.startDownload)

        page.clearLogButton.clicked.connect(page.clearLog)
        page.saveLogButton.clicked.connect(page.saveLog)

    def scheduleStartupTasks(self) -> None:
        """延迟到事件循环开始后加载 Pack 和扫描探针，避免阻塞页面构造。"""
        QTimer.singleShot(0, self.page.preloadPackTargets)
        QTimer.singleShot(0, self.page.scanProbe)
