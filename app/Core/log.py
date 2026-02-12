# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-14 14:14
#  @FileName: log.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------
import logging
from datetime import datetime

from app.Config import SettingMangerInstance as SMI

# 日志文件夹路径
LOG_DIR = SMI.BaseDir / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 按年月日_时分生成文件名
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
LOG_PATH = LOG_DIR / f"{timestamp}.log"

# 创建日志器
logger = logging.getLogger("MCServerLauncher")
logger.setLevel(logging.DEBUG)

# 控制台输出
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# 文件输出
file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)

# 日志格式
formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

if not logger.hasHandlers():
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)