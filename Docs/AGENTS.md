# AGENTS.md
## 项目概览
- `F4CP` 是一个以 Windows 为优先平台的 PyQt5 桌面应用，基于 `qfluentwidgets` 构建；真实入口在 `start.py`，它会把五个页面组装进 `Window(UMainWindow)`。
- UI 外壳位于 `app/Pages/main_window.py`；`app/Pages/` 下的各页面模块同时负责界面组件和大部分页面级行为。
- 运行时路径的唯一事实来源是 `Config/config.py:DirPaths`；它通过 `getattr(sys, 'frozen', False)` 在源码目录与冻结后的 exe 目录之间切换。
## 主要子系统
- **Home / Settings UI**：以展示层为主，外加主题、语言、字体管理（`app/Pages/page_home.py`、`app/Pages/page_settings.py`、`app/Core/Manager/*`）。
- **串口控制台页面**：`app/Pages/page_device.py` 使用 `app/Core/Session/session_serial.py`，并结合 `app/TVLCOMV2_FULL/*` 处理原始串口流量与 TVLCOM V2 的帧/TLV 解析。
- **电源仪表盘**：`app/Pages/page_power.py` 会从 `Resources/Config/config.ini` 中读取 VID/PID 自动发现目标串口设备，然后把该会话挂接到 `app/Core/Session/session_powert.py` 中的 `F4CPPowerClient`。
- **DAPLink 烧录**：`app/Pages/page_daplink.py` 通过自定义事件把请求投递给 `DaplinkPyocdSession`（`app/Core/Session/session_daplink.py`）；后者在后台 Python 线程中执行 pyOCD 工作，并从 `Resources/Tools/Pack` 加载 CMSIS Pack。
## 必须保持的通信模式
- 这个仓库把 **自定义 Qt 事件作为跨组件边界**，而不是在工作线程里直接操作 UI。例子见 `session_serial.py` 里的 `SerialEventType`、`session_daplink.py` 里的 `DaplinkProgrammerEventType`。
- 页面通常通过重写 `event()` 来消费这些事件（如 `DevicePage.event`、`DaplinkFlashPage.event`、`F4CPPowerClient.event`）。如果你新增异步能力，沿用这一模式，不要从 worker 线程直接触碰控件。
- `PowerPage` 将 `F4CPPowerClient` 放在独立 `QThread` 中，并且只通过 `attachSessionRequested`、`readStatusRequested`、`outputLimitsRequested` 这类信号进行通信。
- `DevicePage` 会缓冲 RX 字节、记录原始流量日志，并可选地在其上叠加 TVLCOM V2 解析；修改 V2 解析时不要破坏原始模式行为。
## 关键协议细节
- `session_powert.py` 中的电源设备协议 **不是** `app/TVLCOMV2_FULL` 的同一套实现；它拥有自己的 `SOF = b"\xAA\x55"`、Modbus CRC16、请求/ACK/NACK 流程，以及专用 TLV 类型。
- 电源仪表盘依赖若干固定 type ID，例如输出电压 `12`、输出原始电压 `27`、OVP 设定值 `32`；参见 `PowerDataType` 与 `_diagnose_debug_snapshot()`。
- 串口页显示的 TVLCOM V2 类型名来自 `TYPE_REGISTRY`，并辅以 `app/Core/const.py` 中的别名映射（`SESSION_PAGE_V2_TYPE_ALIAS_TO_ID`）。
## 配置、资源与生成文件
- 持久化设置分散在 `Resources/Config/config.ini`（自定义 `QSettings` 值，例如端口 VID/PID、语言、字体）和 `Resources/Config/config.json`（`qfluentwidgets` 主题配置）中。
- 主题 QSS 位于 `Resources/Theme/qss/{dark,light}/`；`StyleSheet` 枚举名必须与页面 `objectName` / QSS 文件名对应（`HomePage`、`PowerPage`、`DaplinkFlashPage`、`SettingsPage`）。
- 翻译文件是 `Resources/Language/` 下的 JSON 字典；`language_manager` 只会为 `zh_CN` 加载 JSON，英文则回退到源码原文。
- 将 `build/exe/`、`Logs/` 与 `__pycache__/` 视为生成/运行时产物，而不是源码。
## 常用命令
- `uv sync`
- `uv run python start.py`
- `./Script/package_exe.ps1`
- `uv run python Script/upx_zip.py`（可选的打包后体积裁剪）
## 仓库特有编码约定
- 所有面向用户的 UI 文案都应包在 `self.tr(...)` 中；页面依赖 `LanguageChange` 事件重新执行 `_retranslate_ui()`。
- 顶部提示条统一复用 `app/Core/utility.py` 中的 `showMessage(...)`，不要随意改成自定义弹窗。
- 新增设置项应走 `SettingMangerInstance` / `QSettings`，不要写成硬编码模块全局变量。
- 如果新增页面样式，记得在 `StyleSheet` 中注册，并保持控件 `objectName` 与 QSS 文件名一致。
- 处理 DAPLink 支持时，要默认 `Resources/Tools/Pack` 里的本地 `.pack` 文件是必需输入；目标芯片选择与过滤都依赖它们。
## 修改行为前应优先查看
- 应用外壳/导航：`start.py`、`app/Pages/main_window.py`
- 串口页与 TVLCOM V2：`app/Pages/page_device.py`、`app/TVLCOMV2_FULL/*`
- 电源协议与仪表盘：`app/Pages/page_power.py`、`app/Core/scan_connect_device.py`、`app/Core/Session/session_powert.py`
- DAPLink 烧录：`app/Pages/page_daplink.py`、`app/Core/Session/session_daplink.py`
- 设置/主题/语言/字体：`app/Pages/page_settings.py`、`Config/config.py`、`app/Core/Manager/*`
