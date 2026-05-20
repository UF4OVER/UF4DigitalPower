# F4CP

F4CP 是 `UF4DigitalPower` 数字电源的 Windows 上位机。应用基于 Python、PyQt5 和 qfluentwidgets 构建，用于设备发现、串口连接、状态监控、输出控制、保护阈值配置、TVLCOM V2 调试，以及 DAPLink/pyOCD 固件烧录。

应用入口是 `start.py`。主窗口 `Window(MSFluentWindow)` 在这里创建，并组装 Home、Device、Power、Daplink 和 Settings 页面。

## 功能概览

- 首页：项目概览、版本信息和更新检查入口。
- 串口页：原始串口收发、串口日志、TVLCOM V2 帧和 TLV 解析。
- 设备页：电源状态采集、输出电压/限流设置、输出开关控制、保护参数配置。
- 烧录页：通过 pyOCD 和本地 CMSIS Pack 执行 DAPLink 烧录。
- 设置页：主题、字体和应用配置管理。
- 标题栏通知：主窗口 `titleBar` 中间提供灵动岛通知区域，页面仍通过统一 `showMessage(...)` 发送提示。

## 快速开始

### 环境要求

- Windows 10/11
- Python `3.10+`
- `uv`
- DAPLink 烧录功能需要 `Resources/Tools/Pack/` 下存在可用的 CMSIS Pack

### 安装依赖

```powershell
uv sync
```

### 启动

```powershell
uv run python start.py
```

### 测试

```powershell
uv run python -m unittest discover -s tests
```

### 打包

```powershell
.\Script\package_exe.ps1
```

打包产物输出到 `Build/exe/`。需要进一步压缩体积时，可以在打包后运行：

```powershell
uv run python Script/upx_zip.py
```

## 项目结构

```text
F4CP/
├─ App/
│  ├─ Pages/                 # 各业务页面
│  └─ Core/
│     ├─ Session/            # 串口、电源协议、DAPLink 会话
│     ├─ TVLCOMV2_FULL/      # 通用 TVLCOM V2 帧/TLV 工具
│     ├─ Manager/            # 样式、字体、固件、更新管理
│     ├─ icons.py            # 图标封装
│     └─ utility.py          # 通用 UI 辅助函数
├─ Config/                   # 路径、配置、日志初始化
├─ Resources/
│  ├─ Assets/                # 图标和应用图片
│  ├─ Config/                # config.ini / config.json
│  ├─ Firmware/              # 本地固件
│  ├─ Font/                  # 字体资源
│  ├─ Theme/qss/             # 页面样式
│  └─ Tools/Pack/            # CMSIS Pack
├─ Script/                   # 打包和资源脚本
├─ tests/                    # unittest 测试
├─ start.py                  # 应用入口和主窗口
└─ pyproject.toml            # 依赖与 cx_Freeze 配置
```

## 关键模块

| 模块 | 说明 |
| --- | --- |
| `start.py` | 应用入口、主窗口、导航和标题栏通知 |
| `App/Pages/page_home.py` | 首页、版本信息、更新检查 |
| `App/Pages/page_device.py` | 串口控制台、TVLCOM V2 调试 |
| `App/Pages/page_power.py` | 电源状态、输出控制、保护参数 |
| `App/Pages/page_daplink.py` | DAPLink/pyOCD 烧录页面 |
| `App/Pages/page_settings.py` | 主题、字体和应用设置 |
| `App/Core/Session/session_power.py` | 专用电源协议客户端 |
| `App/Core/Session/session_serial.py` | 通用串口会话和事件投递 |
| `App/Core/Session/session_daplink.py` | pyOCD 后台烧录会话 |
| `App/Core/utility.py` | 统一通知入口 `showMessage(...)` |

## 电源连接配置

Power 页面从 `Resources/Config/config.ini` 读取目标设备 VID/PID：

```ini
[port]
vid=2001
pid=8738
```

自动发现成功后，页面会创建串口会话并挂接到 `F4CPPowerClient`。该客户端运行在独立 `QThread` 中，通过 Qt 信号和页面通信，避免后台串口回调直接操作 UI。

## 通信协议

Power 页面使用 `App/Core/Session/session_power.py` 中的专用协议实现：

- 帧头：`0xAA 0x55`
- 长度：`CMD + SEQ + Payload` 的字节数，little-endian
- 校验：Modbus CRC16，little-endian
- 载荷：TLV 列表，格式为 `Type(1) + Length(2) + Value(N)`
- 命令：`ACK(0x00)`、`READ(0x01)`、`WRITE(0x02)`、`REPORT(0x03)`、`NACK(0xFF)`

常用数据类型在 `PowerDataType` 与 `POWER_DATA_META` 中维护。修改协议时，需要同步上位机、下位机枚举、协议文档和测试。

注意：`App/Core/TVLCOMV2_FULL/` 是串口调试页使用的通用 TVLCOM V2 工具；Power 页面使用的是 `session_power.py` 中的专用实现，两者不要混成一套状态机。

## 开发约定

- 页面提示统一调用 `App/Core/utility.py` 的 `showMessage(...)`。主窗口会同时显示右上角 InfoBar 和标题栏灵动岛提示。
- 新增持久化设置优先走 `SettingMangerInstance` / `QSettings`。
- 异步任务和页面通信应使用 Qt 信号或自定义 Qt 事件，不要从 worker 线程直接操作控件。
- 新增页面样式时，需要同步 `StyleSheet` 枚举、页面 `objectName` 和 QSS 文件名。
- 修改 Power 协议前，先更新协议表，再同步上下位机枚举、元数据、读写处理和测试。
- `Build/exe/`、`Logs/`、`__pycache__/` 和 `.pytest_cache/` 是生成或运行时产物，不作为源码维护。

## 常用入口

- 应用入口与主窗口导航：`start.py`
- 电源页面：`App/Pages/page_power.py`
- 电源协议：`App/Core/Session/session_power.py`
- 串口页：`App/Pages/page_device.py`
- 通用串口会话：`App/Core/Session/session_serial.py`
- DAPLink 页面：`App/Pages/page_daplink.py`
- DAPLink 会话：`App/Core/Session/session_daplink.py`
- 配置与路径：`Config/config.py`
- 样式管理：`App/Core/Manager/manager_stylesheet.py`
