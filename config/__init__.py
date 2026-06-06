# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: __init__.py
#  @FileType: 配置包初始化文件，统一导出应用配置上下文
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from .config import (
    CTX,
    AppContext,
    DirPaths,
    F4CPConfig,
    # ---- 便捷快捷方式----
    cfg,
    AppIconPath,
    logger,
    get_logger,

    # ---- 应用常量 ----
    VERSION,
    YEAR,
    AUTHOR,
    HELP_URL,
    REPO_URL,
    EXAMPLE_URL,
    FEEDBACK_URL,
    RELEASE_URL,
    ZH_SUPPORT_URL,
    EN_SUPPORT_URL,
    VERSION_LOCAL_SECTION,
    VERSION_REMOTE_SECTION,
    UPDATE_SECTION,
    FIRMWARE_REMOTE_SECTION,
    LOCAL_APP_VERSION_OPTION,
    LOCAL_UPPER_VERSION_OPTION,
    LOCAL_LOWER_VERSION_OPTION,
    LATEST_APP_VERSION_OPTION,
    LATEST_UPPER_VERSION_OPTION,
    LATEST_LOWER_VERSION_OPTION,
    UPDATE_URL_OPTION,
    FIRMWARE_GITHUB_OWNER_OPTION,
    FIRMWARE_GITHUB_REPO_OPTION,
    FIRMWARE_BASE_URL_OPTION,
)
