# -*- coding: utf-8 -*-
"""Minimal manual demo to verify notification sidebar does not block mouse input."""

from __future__ import annotations

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from App.Core.Manager.manager_notification import bindNotificationWindow


class MinimalNotificationDemo(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Notification Sidebar Minimal Demo")
        self.resize(960, 620)

        self._click_count = 0
        self._manager = bindNotificationWindow(self)
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(10)

        tips = QLabel(
            "验证点: 通知出现时，继续点击中间文本区和左侧按钮，\n"
            "如果计数和文本都能更新，说明鼠标未被通知层整体拦截。"
        )
        tips.setWordWrap(True)

        row = QHBoxLayout()
        row.setSpacing(8)

        btn_notify = QPushButton("Show Notification")
        btn_notify.clicked.connect(self._show_notification)

        btn_many = QPushButton("Burst x3")
        btn_many.clicked.connect(self._burst_notifications)

        self._btn_click = QPushButton("Click Test")
        self._btn_click.clicked.connect(self._on_click_test)

        self._status = QLabel("Click Test count: 0")

        row.addWidget(btn_notify)
        row.addWidget(btn_many)
        row.addWidget(self._btn_click)
        row.addWidget(self._status, 1)

        self._editor = QTextEdit()
        self._editor.setPlaceholderText("在这里输入文本，确认通知显示时仍可编辑")

        root.addWidget(tips)
        root.addLayout(row)
        root.addWidget(self._editor, 1)

    def _show_notification(self):
        self._manager.showCard(
            title="Mouse Input Check",
            subtitle="Try typing and clicking controls while this toast is visible.",
            level="info",
            auto_recycle=True,
            duration=3500,
            confirm_text="OK",
        )

    def _burst_notifications(self):
        for level in ("info", "success", "warning"):
            self._manager.showCard(
                title=f"{level.upper()} demo",
                subtitle="Notifications should not freeze unrelated controls.",
                level=level,
                auto_recycle=True,
                duration=4500,
            )

    def _on_click_test(self):
        self._click_count += 1
        self._status.setText(f"Click Test count: {self._click_count}")


def main() -> int:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)

    window = MinimalNotificationDemo()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())

