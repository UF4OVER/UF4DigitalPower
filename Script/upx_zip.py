# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 02-02 17:22
#  @FileName: upx_zip.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------

import os
import subprocess
import shutil


def compress_with_upx(directory):
    for root, dirs, files in os.walk(directory):
        if 'lib' in dirs and 'PyQt5' in dirs and 'Qt5' in dirs and 'translations' in dirs:
            translations_path = os.path.join(root, 'translations')
            shutil.rmtree(translations_path)
            print(f"Deleted translations folder at {translations_path}")
            dirs.remove('translations')  # 删除翻译插件

        # 排除指定目录，防止发生PyQt5平台错误
        if 'lib' in root and 'PyQt5' in root and 'Qt5' in root and 'plugins' in root:
            continue

        for file in files:
            if file.lower().endswith(('.exe', '.dll', '.pyd')):  # 规范大小写
                file_path = os.path.join(root, file)
                try:
                    subprocess.run(['upx.exe', '--best', file_path], check=True)
                    print(f"Compressed: {file_path}")
                except subprocess.CalledProcessError as e:
                    print(f"Failed to compress {file_path}: {e}")


if __name__ == "__main__":
    if os.path.exists("build\\exe"):
        print("build\\exe exists")
        target_directory = "build\\exe"
        compress_with_upx(target_directory)
    else:
        print("build\\exe does not exist")