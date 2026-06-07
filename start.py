# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: start.py
#  @FileType: 应用入口文件，负责创建主窗口并启动 Qt 事件循环
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.11
# -------------------------------

import sys
import time

from PyQt5.QtGui import QCloseEvent

time_ = time.time()

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication

from config import get_logger,cfg
from app.manager import loadSavedFont

logger = get_logger("Bootstrap")


from ui import Window
# # 解决 qfluentwidgets 对 QSS 中 path 带空格的情况无法识别的问题
# from PyQt5.QtWidgets import QStyleFactory
# QStyleFactory.setStyle("Fusion")

class Application(Window):
    def __init__(self):
        super().__init__()
        QTimer.singleShot(150, self._checkUpdateOnStartUp)
    def _checkUpdateOnStartUp(self):
        """按用户设置决定启动后是否自动检查应用更新。"""
        if getattr(cfg.checkUpdateAtStartUp, "value", False):
            self.homeInterface.requestUpdateCheck(manual=False)

    def close(self):
        logger.warning("Application closed")
        super().close()

    def closeEvent(self, event: QCloseEvent):
        """窗口关闭前先让电源页停掉串口和轮询，避免后台还在收发。"""
        self.powerInterface.shutdown()
        super().closeEvent(event)

if __name__ == "__main__":
    time_ = time.time()
    logger.info("main is running")
    if cfg.highDpiScaling.value:
        logger.info("highDpiScaling is running")
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    logger.info("Application started")
    try:
        app = QApplication(sys.argv)
        loadSavedFont(app)  # 加载字体
        w = Application()
        # w.show()
        logger.info(f"start time: {time.time() - time_}")

        sys.exit(app.exec_())
    except Exception as e:
        logger.error(e)
        sys.exit(-1)
