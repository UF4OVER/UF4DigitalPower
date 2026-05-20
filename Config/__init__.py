# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-16 14:58
#  @FileName: __init__.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  :
# -------------------------------

from .config import *  # noqa: F403 — re-exports all legacy names + new API

# Explicit re-exports for discoverability (these ARE exported by the * above,
# but explicit imports help IDEs and linters):
from .config import (  # noqa: F401
    AppContext,
    DirPaths,
    F4CPConfig,
    SettingsManager,
    get_default_context,
    reset_app_context,
    set_app_context,
)
