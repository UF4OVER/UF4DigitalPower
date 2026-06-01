# AGENTS.md

## 项目概览

- `F4CP` 是 Windows 优先的 PyQt5 桌面应用，基于 `qfluentwidgets` 构建。
- 真实入口是 `start.py`，主窗口类是 `Window(MSFluentWindow)`。
- 页面位于 `App/Pages/`，核心会话、协议和管理器位于 `App/Core/`。
- 运行时路径的事实来源是 `Config/config.py`，它会根据 `sys.frozen` 在源码目录和冻结后的 exe 目录之间切换。

## 主要子系统

- Home / Settings：`App/Pages/page_home.py`、`App/Pages/page_settings.py` 和 `App/Core/Manager/*`。
- 串口控制台：`App/Pages/page_device.py` 使用 `App/Core/Session/session_serial.py`，并结合 `App/Core/TVLCOMV2_FULL/*` 处理原始串口流量与 TVLCOM V2 解析。
- 电源仪表盘：`app/widgets/pages/page_power.py` 通过 `app/session/session_power.py` 中的 `F4CPPowerClient` 管理数字电源会话。
- DAPLink 烧录：`App/Pages/page_daplink.py` 通过自定义事件投递请求，`App/Core/Session/session_daplink.py` 在线程中执行 pyOCD 工作，并从 `Resources/Tools/Pack` 加载 CMSIS Pack。
- 标题栏通知：`start.py` 中的 `DynamicIsland` 挂在 `titleBar` 中间，页面仍通过 `App/Core/utility.py` 的 `showMessage(...)` 发送通知。

## 必须保持的通信模式

- 仓库使用自定义 Qt 事件或 Qt 信号跨线程通信，不要从 worker 线程直接操作 UI。
- 参考 `session_serial.py` 的 `SerialEventType`、`session_daplink.py` 的 `DaplinkProgrammerEventType` 和各页面 `event()` 实现。
- `PowerPage` 将 `F4CPPowerClient` 放在独立 `QThread` 中，并通过 `attachSessionRequested`、`readStatusRequested`、`outputLimitsRequested` 等信号通信。
- `DevicePage` 会缓冲 RX 字节、记录原始流量日志，并可选叠加 TVLCOM V2 解析；修改 V2 解析时不要破坏原始模式行为。

## 关键协议细节

- `session_power.py` 中的电源设备协议不是 `App/Core/TVLCOMV2_FULL` 的同一套实现。
- 电源协议使用 `SOF = b"\xAA\x55"`、Modbus CRC16、请求/ACK/NACK 流程，以及专用 TLV 类型。
- 电源仪表盘依赖固定 type ID，参见 `PowerDataType`、`POWER_DATA_META` 和页面诊断逻辑。
- 串口页显示的 TVLCOM V2 类型名来自 `TYPE_REGISTRY`，并辅以 `App/Core/const.py` 中的别名映射。

## 配置、资源与生成文件

- `Resources/Config/config.json` 保存应用配置，包括主题、字体、版本和更新地址。
- 主题 QSS 位于 `Resources/Theme/qss/{dark,light}/`；`StyleSheet` 枚举、页面 `objectName` 和 QSS 文件名需要一致。
- `Build/exe/`、`Logs/`、`__pycache__/` 和 `.pytest_cache/` 是生成或运行时产物，不作为源码维护。

## 常用命令

```powershell
uv sync
uv run python start.py
uv run python -m unittest discover -s tests
.\Script\package_exe.ps1
uv run python Script/upx_zip.py
```

## 仓库约定

- 顶部提示统一复用 `App/Core/utility.py` 中的 `showMessage(...)`。
- 新增设置项统一走 `config.CTX.cfg` / qfluentwidgets `QConfig`。
- 新增页面样式时，在 `StyleSheet` 中注册，并保持控件 `objectName` 与 QSS 文件名一致。
- DAPLink 相关逻辑默认依赖 `Resources/Tools/Pack` 中的本地 `.pack` 文件。

## 修改行为前优先查看

- 应用外壳和导航：`start.py`
- 串口页和 TVLCOM V2：`App/Pages/page_device.py`、`App/Core/TVLCOMV2_FULL/*`
- 电源协议和仪表盘：`App/Pages/page_power.py`、`App/Core/Session/session_power.py`
- DAPLink 烧录：`App/Pages/page_daplink.py`、`App/Core/Session/session_daplink.py`
- 设置、主题和字体：`App/Pages/page_settings.py`、`Config/config.py`、`App/Core/Manager/*`
