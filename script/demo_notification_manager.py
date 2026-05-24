# -*- coding: utf-8 -*-
"""Minimal GUI demo for NotificationManager slide in/out behavior."""

from __future__ import annotations

import random
import sys

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import Theme, setTheme

from manager import (
    bindNotificationWindow,
    notificationManager,
)


class NotificationDemoWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NotificationManager Demo")
        self.resize(980, 640)
        self._cards = []

        setTheme(Theme.LIGHT)
        self.manager = bindNotificationWindow(self)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("NotificationManager 动画演示")
        title.setStyleSheet("font-size: 22px; font-weight: 600;")

        tips = QLabel(
            "点击按钮观察：新通知从右侧滑入，旧通知向下移动；"
            "关闭后会淡出并向右滑出，下方卡片自动补位。"
        )
        tips.setWordWrap(True)

        self.logOutput = QTextEdit()
        self.logOutput.setReadOnly(True)
        self.logOutput.setPlaceholderText("运行日志")

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        btn_info = QPushButton("Info")
        btn_success = QPushButton("Success")
        btn_warning = QPushButton("Warning")
        btn_error = QPushButton("Error")

        btn_info.clicked.connect(lambda: self._push(level="info"))
        btn_success.clicked.connect(lambda: self._push(level="success"))
        btn_warning.clicked.connect(lambda: self._push(level="warning"))
        btn_error.clicked.connect(lambda: self._push(level="error"))

        row1.addWidget(btn_info)
        row1.addWidget(btn_success)
        row1.addWidget(btn_warning)
        row1.addWidget(btn_error)
        row1.addStretch(1)

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        btn_burst = QPushButton("Burst x5")
        btn_manual = QPushButton("Manual (no auto close)")
        btn_close_latest = QPushButton("Close latest")
        btn_close_all = QPushButton("Close all")

        btn_burst.clicked.connect(self._burst)
        btn_manual.clicked.connect(lambda: self._push(level="info", auto=False))
        btn_close_latest.clicked.connect(self._close_latest)
        btn_close_all.clicked.connect(self._close_all)

        row2.addWidget(btn_burst)
        row2.addWidget(btn_manual)
        row2.addWidget(btn_close_latest)
        row2.addWidget(btn_close_all)
        row2.addStretch(1)

        layout.addWidget(title)
        layout.addWidget(tips)
        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addWidget(self.logOutput, 1)

    def _push(self, level: str = "info", auto: bool = True):
        subtitle_samples = {
            "info": "串口已连接，准备读取状态。",
            "success": "烧录完成，设备已重启。",
            "warning": "检测到电压接近保护阈值。",
            "error": "通信超时，请检查设备连接。",
        }

        manager = notificationManager() or self.manager
        card = manager.showCard(
            title=f"{level.upper()} 通知",
            subtitle=subtitle_samples.get(level, "通知内容"),
            level=level,
            auto_recycle=auto,
            duration=3000,
            confirm_text="确认",
        )
        card.confirmed.connect(lambda _: self._log(f"[{level}] 点击确认"))
        card.closed.connect(lambda _: self._log(f"[{level}] 已关闭"))
        self._cards.append(card)

        mode = "auto" if auto else "manual"
        self._log(f"创建 {level} 通知 ({mode})")

    def _burst(self):
        levels = ["info", "success", "warning", "error"]
        for i in range(5):
            QTimer.singleShot(i * 220, lambda lv=random.choice(levels): self._push(level=lv, auto=True))

    def _close_latest(self):
        manager = notificationManager() or self.manager
        while self._cards:
            card = self._cards.pop()
            if card in manager.cards:
                manager.closeCard(card)
                self._log("手动关闭最近一条通知")
                return
        self._log("没有可关闭的通知")

    def _close_all(self):
        manager = notificationManager() or self.manager
        manager.clear()
        self._log("请求关闭所有通知")

    def _log(self, text: str):
        self.logOutput.append(text)


def main() -> int:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    w = NotificationDemoWindow()
    w.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())

