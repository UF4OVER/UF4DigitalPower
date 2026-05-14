# F4CP 上位机

F4CP 是 `UF4DigitalPower` 数字电源的 PC 上位机，面向 Windows 桌面使用，基于 Python、PyQt5 与 qfluentwidgets 构建。它负责设备发现、串口连接、运行状态监控、输出参数设置、保护阈值配置、协议调试和 DAPLink/pyOCD 烧录辅助。

真实入口是 `start.py`，主窗口类 `Window(MSFluentWindow)` 也定义在这里，并负责组装各功能页面。

## 主要功能

- 电源仪表盘：显示输入/输出电压、电流、温度、CV/CC 状态、故障位、状态机、PWM 比较值、风扇值等运行数据。
- 输出控制：设置输出电压、电流限制，并控制电源输出开关。
- 保护参数：设置 OVP、OCP、OTP 与风扇设定值。
- 串口控制台：支持原始串口收发、日志记录，以及 TVLCOM V2 帧/TLV 解析查看。
- DAPLink 烧录：通过 pyOCD 调用本地 CMSIS Pack 完成目标芯片烧录流程。
- 设置页面：支持主题、字体和应用配置管理。
- 电池页面：提供电池相关信息展示与后续功能扩展入口。

## 快速开始

### 环境要求

- Python `3.10+`
- `uv`
- Windows 10/11 优先
- DAPLink 烧录功能需要可用的 CMSIS Pack，默认从 `Resources/Tools/Pack/` 读取

### 安装依赖

```powershell
uv sync
```

### 启动应用

```powershell
uv run python start.py
```

### 运行测试

```powershell
uv run python -m unittest discover -s tests
```

### 打包

```powershell
.\Script\package_exe.ps1
```

打包输出位于 `Build/exe/`。如需进一步裁剪体积，可在打包后运行：

```powershell
uv run python Script/upx_zip.py
```

## 项目结构

```text
F4CP/
├─ App/
│  ├─ Pages/                 # 主窗口和各页面
│  └─ Core/
│     ├─ Session/            # 串口、电源协议、DAPLink 会话
│     ├─ TVLCOMV2_FULL/      # 通用 TVLCOM V2 帧/TLV 工具
│     ├─ Manager/            # 样式、字体、固件、更新等管理器
│     └─ utility.py          # 通用 UI 辅助函数
├─ Config/                   # 运行路径、配置管理、日志初始化
├─ Resources/
│  ├─ Assets/                # 图标与静态资源
│  ├─ Config/                # config.ini / config.json
│  ├─ Firmware/              # 本地固件目录
│  ├─ Theme/qss/             # 页面 QSS
│  └─ Tools/Pack/            # CMSIS Pack
├─ Script/                   # 打包、演示、资源生成脚本
├─ tests/                    # unittest 测试
├─ start.py                  # 应用入口
└─ pyproject.toml            # 依赖与 cx_Freeze 配置
```

## 页面与核心模块

| 页面/模块 | 说明 | 主要文件 |
| --- | --- | --- |
| Home | 首页与概览 | `App/Pages/page_home.py` |
| Power | 电源控制、状态监控、保护参数设置 | `App/Pages/page_power.py` |
| Device | 串口控制台与 TVLCOM V2 调试 | `App/Pages/page_device.py` |
| Daplink | DAPLink/pyOCD 烧录 | `App/Pages/page_daplink.py` |
| Battery | 电池相关页面 | `App/Pages/page_battery.py` |
| Settings | 主题、字体等设置 | `App/Pages/page_settings.py` |
| Power Client | 专用电源协议客户端 | `App/Core/Session/session_power.py` |
| Serial Session | 通用串口会话与跨线程事件 | `App/Core/Session/session_serial.py` |
| DAPLink Session | pyOCD 后台烧录会话 | `App/Core/Session/session_daplink.py` |

## 电源连接与配置

Power 页面会从 `Resources/Config/config.ini` 读取目标设备 VID/PID：

```ini
[port]
vid=2001
pid=8738
```

自动发现成功后，页面会创建串口会话并挂接到 `F4CPPowerClient`。该客户端运行在独立 `QThread` 中，通过 Qt 信号与页面通信，避免后台串口回调直接操作 UI。

## 通信协议

Power 页面使用 `App/Core/Session/session_power.py` 中的专用电源协议客户端。协议摘要：

- 帧头：`0xAA 0x55`
- 长度：`CMD + SEQ + Payload` 的字节数，little-endian
- 校验：Modbus CRC16，little-endian
- 载荷：TLV 列表，格式为 `Type(1) + Length(2) + Value(N)`
- 命令：`ACK(0x00)`、`READ(0x01)`、`WRITE(0x02)`、`REPORT(0x03)`、`NACK(0xFF)`

常用数据类型在 `PowerDataType` 与 `POWER_DATA_META` 中维护。修改协议时需要同步：

- 上位机：`App/Core/Session/session_power.py`
- 下位机：`UF4DigitalPower/APP/Src/uf4_tvlcom.c`
- 协议文档：项目根目录 `COMMUNICATION_COMMANDS.md` 与固件目录 `UF4DigitalPower/COMMUNICATION_COMMANDS.md`
- 示例脚本：`UF4DigitalPower/Docs/tvl_host_example.py`

注意：`App/Core/TVLCOMV2_FULL/` 是串口调试页使用的通用 TVLCOM V2 工具；Power 页面使用的是 `session_power.py` 中的专用实现，两者不要混为一套状态机。

## 运行时数据

- `Resources/Config/config.ini`：端口 VID/PID、版本信息、固件远程仓库、更新 URL、字体等应用设置。
- `Resources/Config/config.json`：qfluentwidgets 主题配置。
- `Resources/Theme/qss/{dark,light}/`：页面样式表。新增页面样式时，需要同步 `StyleSheet` 枚举、页面 `objectName` 与 QSS 文件名。
- `Logs/`：运行日志。
- `Build/exe/`：打包产物。

`Build/exe/`、`Logs/`、`__pycache__/` 与 `.pytest_cache/` 都属于生成或运行时产物，不应当作为源码维护。

## 开发约定

- 顶部提示统一使用 `App/Core/utility.py` 中的 `showMessage(...)`。
- 新增持久化设置优先走 `SettingMangerInstance` / `QSettings`。
- 异步任务与页面通信应沿用自定义 Qt 事件或 Qt 信号，不要从 worker 线程直接操作控件。
- 修改 Power 协议前，先更新协议表，再同步上下位机枚举、元数据、读写处理和测试。
- DAPLink 相关逻辑默认依赖 `Resources/Tools/Pack/` 中的本地 `.pack` 文件。

## 常用定位入口

- 应用入口与主窗口导航：`start.py`
- 电源页面：`App/Pages/page_power.py`
- 电源协议：`App/Core/Session/session_power.py`
- 串口页：`App/Pages/page_device.py`
- 通用串口会话：`App/Core/Session/session_serial.py`
- DAPLink 页面：`App/Pages/page_daplink.py`
- DAPLink 会话：`App/Core/Session/session_daplink.py`
- 配置与路径：`Config/config.py`
- 样式管理：`App/Core/Manager/manager_stylesheet.py`
