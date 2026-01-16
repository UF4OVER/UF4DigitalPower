# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-14 14:25
#  @FileName: build.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------


from cx_Freeze import Executable, setup

# 设置 GUI 基础
base = "Win32GUI"


def build_exe_cx_freeze():
    build_exe_options = {  # 构建选项
        "includes":[
            "PyQt5.QtCore",
            "PyQt5.QtGui",
            "PyQt5.QtWidgets",
            "qfluentwidgets",
            "qframelesswindow",
        ],
        "packages": [
            "Pages",   # 包含自定义界面文件
            "Config",  # 包含配置文件
            "Core",    # 包含核心功能文件
        ],
        "include_files": [
            "Assets",
        ],
        "excludes": [
            "scipy",
            "matplotlib",
            "backports",
            "PIL",
            "lib2to3",
            "setuptools",
            "tkinter",
            "unittest",
            "email",
            "cryptography",
            "pydoc",
        ],
        "optimize": 2,
        # Windows 运行时更稳（避免目标机器缺 VC++ runtime）
        "include_msvcr": True,
        "build_exe": "build/exe",
    }

    # MSI 安装包选项（bdist_msi）
    bdist_msi_options = {
        # add/remove programs 图标
        "install_icon": "Assets/F4CP_ICO_256.ico",
        # 默认安装目录（可选）
        "initial_target_dir": r"[ProgramFilesFolder]\\F4CP",
        # 生成的 msi 文件名（可选）
        "target_name": "F4CP-Setup.msi",
        # 安装完可勾选启动（可选）
        "launch_on_finish": True,
        # "add_to_path": False,
        # "all_users": True,
    }

    setup(
        options={
            "build_exe": build_exe_options,
        },
        executables=[
            Executable(
                script="start.py",
                target_name="F4CP",
                base=base,
                icon="Assets/F4CP_ICO_256.ico",
            )
        ],
    )


if __name__ == "__main__":
    build_exe_cx_freeze()
