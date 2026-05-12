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
import logging
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMessageBox
from qfluentwidgets import InfoBar, InfoBarPosition

try:
    from siui.core import SiGlobal
except Exception:  # SIUI 未安装或当前环境不可用时，允许回退到 InfoBar/QMessageBox
    SiGlobal = None


_MSG_TYPE_ERROR = 0
_MSG_TYPE_INFO = 1
_MSG_TYPE_SUCCESS = 2
_MSG_TYPE_WARNING = 3


_LEVEL_TO_MSG_TYPE = {
    "error": _MSG_TYPE_ERROR,
    "info": _MSG_TYPE_INFO,
    "success": _MSG_TYPE_SUCCESS,
    "warning": _MSG_TYPE_WARNING,
}


_LEVEL_TO_ICON = {
    "error": "ic_fluent_error_circle_filled",
    "info": "ic_fluent_info_filled",
    "success": "ic_fluent_checkmark_circle_filled",
    "warning": "ic_fluent_warning_filled",
}


def _resolve_icon(icon: Optional[str], fallback: str = "ic_fluent_info_filled"):
    """SIUI 图标解析。

    这里保持简单：
    - 传入 icon 就优先用传入值
    - 未传入则使用 fallback
    - 如果项目后续接入 SiIconPack，可在这里集中扩展
    """
    if icon:
        return icon
    return fallback


def _fallback_dialog(msg_type: int, title: str, text: str):
    """侧边消息不可用时的同步兜底。"""
    app = QApplication.instance()
    if app is None:
        print(f"{title}: {text}")
        return

    if msg_type == _MSG_TYPE_ERROR:
        QMessageBox.critical(None, title, text)
    elif msg_type == _MSG_TYPE_WARNING:
        QMessageBox.warning(None, title, text)
    else:
        QMessageBox.information(None, title, text)


def _fallback_infobar(parent, title: str, content: str, level: str = "info"):
    """保留 qfluentwidgets InfoBar 作为页面内轻提示兜底。"""
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
        return InfoBar.success(**kwargs)
    if level == "warning":
        return InfoBar.warning(**kwargs)
    if level == "error":
        return InfoBar.error(**kwargs)
    return InfoBar.info(**kwargs)


def show_message(_type: int, title: str, text: str, icon: str = None):
    """验证过的 SIUI 侧边栏全局调用方式。

    调用链：
    业务代码 -> show_message(...) -> MAIN_WINDOW.LayerRightMessageSidebar().send(...)
                               \-> 异常时 _fallback_dialog(...)
    """
    try:
        if SiGlobal is None:
            raise RuntimeError("SIUI 不可用")

        main_window = SiGlobal.siui.windows.get("MAIN_WINDOW")
        if main_window is None:
            raise RuntimeError("MAIN_WINDOW 尚未初始化")

        resolved_icon = _resolve_icon(icon, "ic_fluent_error_circle_filled")
        if resolved_icon is None:
            raise RuntimeError(f"无可用图标: {icon}")

        main_window.LayerRightMessageSidebar().send(
            title=title,
            text=text,
            msg_type=_type,
            icon=resolved_icon,
            fold_after=5000,
        )
    except Exception:
        logging.getLogger(__name__).exception("侧边消息发送失败，已回退到对话框提示")
        _fallback_dialog(_type, title, text)


def showMessage(parent, title: str, content: str, level: str = "info", useSide: bool = True, autoCloseMs: int = 5000):
    """项目统一提示出口。

    默认走已验证的 SIUI 右侧消息栏。若业务代码显式传 useSide=False，则使用 qfluentwidgets InfoBar。
    autoCloseMs 参数保留给调用端兼容，SIUI 当前固定 fold_after=5000。
    """
    if useSide:
        msg_type = _LEVEL_TO_MSG_TYPE.get(level, _MSG_TYPE_INFO)
        icon = _LEVEL_TO_ICON.get(level, _LEVEL_TO_ICON["info"])
        show_message(msg_type, title, content, icon)
        return None

    return _fallback_infobar(parent, title, content, level)


def showSideMessage(parent, title: str, content: str, level: str = "info", icon: str = None, autoCloseMs: int = 5000):
    """侧边通知显式调用入口，参数风格兼容前一次实现。"""
    msg_type = _LEVEL_TO_MSG_TYPE.get(level, _MSG_TYPE_INFO)
    resolved_icon = icon or _LEVEL_TO_ICON.get(level, _LEVEL_TO_ICON["info"])
    show_message(msg_type, title, content, resolved_icon)
    return None


def bindNotificationWindow(parentWindow):
    """兼容 start.py 中的绑定调用。

    SIUI 的消息栏由 MAIN_WINDOW.LayerRightMessageSidebar() 管理，这里只返回主窗口本身，
    避免额外创建第二套通知系统。
    """
    return parentWindow
