# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/4/25
#  @FileName: utility.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------
from PyQt5.QtCore import Qt
from qfluentwidgets import InfoBar, InfoBarPosition


def showMessage(parent, title: str, content: str, level: str = "info"):

    kwargs = dict(
        title=title,
        content=content,
        orient=Qt.Orientation.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP,
        duration=3000,
        parent=parent,
    )

    if level == "success":
        InfoBar.success(**kwargs)
    elif level == "warning":
        InfoBar.warning(**kwargs)
    elif level == "error":
        InfoBar.error(**kwargs)
    else:
        InfoBar.info(**kwargs)