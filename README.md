# F4CP

F4CP 是 `UF4DigitalPower` 项目的 Windows 上位机，面向数字电源调试、监控、参数配置和固件烧录。应用基于 Python、PyQt5、qfluentwidgets、pyqtgraph 和 pyOCD 构建，入口为 `start.py`。

当前主窗口类为 `Window(MSFluentWindow)`，默认导航包含：

- 引导 (`HomePage`)：软件概览、最新动态、多功能按钮导航与快捷通知展示。
- 串口 (`DevicePage`)：串口与蓝牙通信调试，支持 Raw 发送与 TVLCOM V2 (TLV 组包与解析)。
- 设备 (`PowerPage`)：数字电源看板、输出控制、参数设定与多通道图表采样。
- 烧录 (`DaplinkPage`)：基于 pyOCD 进程的 DAPLink 在线擦除、固件烧录、运行复位及本地包管理。
- 版本 (`VersionPage`)：查看当前软件/固件版本、配置 GitHub API 密钥、一键检索/下载最新固件与更新升级。
- 设置 (`SettingsPage`)：软件主题（浅色/深色/跟随系统）、字体大小及高 DPI 缩放。

仓库中还包含 `BatteryPage` 电池组面板实现，用于 4 串电池组状态展示和连接模式预留；当前 `start.py` 尚未把该页面正式加入主窗口导航。

## 快速开始

### 环境要求

- Windows 10/11
- Python `>=3.11`
- `uv`
- DAPLink/pyOCD 烧录功能需要 `Resources/Tools/Pack/` 下存在可用 CMSIS Pack

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
.\script\package_exe.ps1
```

cx_Freeze 配置位于 `pyproject.toml`，打包产物输出到 `build/exe/`。需要进一步压缩体积时，可以在打包后运行：

```powershell
uv run python script\upx_zip.py
```

## 项目结构

```text
F4CP/
├─ app/
│  ├─ controllers/           # 页面控制器，集中注册复杂页面的信号和操作入口
│  ├─ core/                  # 数据中心、通道、设备基类、通用 UI 工具
│  ├─ devices/               # 电源/BMS/虚拟设备适配层
│  ├─ manager/               # 字体、样式、固件、更新管理
│  ├─ protocol/              # TVLCOM V2 通用帧、Payload、类型工具
│  ├─ session/               # 串口、电源协议、DAPLink、蓝牙会话
│  └─ widgets/
│     ├─ chart/              # DataHub 驱动的实时曲线组件
│     ├─ components/         # 启动画面、DynamicIsland 等复用组件
│     ├─ icon/               # UF4 图标资源与封装
│     └─ pages/              # Home/Device/Power/Daplink/Settings/Battery 页面
├─ config/                   # 路径、JSON 配置和日志初始化
├─ docs/                     # 项目协作说明
├─ Resources/
│  ├─ Assets/                # 应用图标、图片资源
│  ├─ Config/                # config.json，运行时配置
│  ├─ Firmware/              # 本地上下位机固件
│  ├─ Font/                  # 字体资源
│  ├─ Theme/qss/             # light/dark 页面样式
│  └─ Tools/Pack/            # 本地 CMSIS Pack
├─ script/                   # 打包、pyOCD 启动和资料生成脚本
├─ tests/                    # unittest 测试
├─ start.py                  # 应用入口、主窗口和导航
└─ pyproject.toml            # 依赖、版本和 cx_Freeze 配置
```

## 关键模块

| 模块 | 说明 |
| --- | --- |
| `start.py` | 应用入口、主窗口导航、启动画面和标题栏 DynamicIsland 通知 |
| `app/controllers/` | 复杂页面控制器，负责把控件事件、页面信号和后台 client/session 事件集中绑定 |
| `config/config.py` | `AppContext`、路径解析、日志和 JSON 配置 |
| `app/widgets/pages/page_home.py` | 首页、软件更新检查、固件版本检查与下载 |
| `app/widgets/pages/page_device.py` | 串口/蓝牙调试页，支持 Raw 和 TVLCOM V2 模式 |
| `app/widgets/pages/page_power.py` | 数字电源仪表盘、输出控制、保护参数、实时曲线 |
| `app/widgets/pages/page_daplink.py` | DAPLink/pyOCD 烧录页面 |
| `app/widgets/pages/page_settings.py` | 主题、字体和应用设置 |
| `app/widgets/pages/page_battery.py` | 电池组面板 UI 与快照数据模型 |
| `app/session/session_serial.py` | 通用串口会话、串口枚举和 Qt 事件投递 |
| `app/session/session_power.py` | 数字电源专用协议客户端、状态模型和流式采样 |
| `app/session/session_daplink.py` | pyOCD 后台烧录会话 |
| `app/protocol/` | TVLCOM V2 通用帧构建、解析、Payload 和类型注册 |
| `app/core/data_hub.py` | 多通道时序数据缓存，供曲线和仪表盘读取 |
| `app/widgets/chart/` | 实时曲线模型、控制面板、数值面板和 pyqtgraph 渲染 |
| `app/core/utility.py` | 统一通知入口 `showMessage(...)` |

## 通信与数据流

### 串口/TVLCOM V2 调试

串口页位于 `app/widgets/pages/page_device.py`，使用 `SerialSession` 管理串口收发，也提供蓝牙 RFCOMM 连接的 UI 与会话封装。页面有两种发送模式：

- Raw：按 HEX 或 ASCII 直接发送。
- TVLCOM V2：根据 TLV 表组包，由 `app/protocol/frameBuilder.py`、`frameParser.py`、`payLoad.py` 和 `dataType.py` 处理帧和类型。

### 数字电源协议

Power 页面使用 `app/session/session_power.py` 中的专用协议，不与 `app/protocol/` 的通用 TVLCOM V2 调试工具共享状态机。

- 帧头：`0xAA 0x55`
- 长度：`CMD + SEQ + Payload` 的字节数，little-endian
- 校验：Modbus CRC16，little-endian
- 载荷：TLV 列表，格式为 `Type(1) + Length(2) + Value(N)`
- 命令：`ACK(0x00)`、`READ(0x01)`、`WRITE(0x02)`、`REPORT(0x03)`、`STREAM_START(0x04)`、`STREAM_STOP(0x05)`、`NACK(0xFF)`
- 原始流分隔：流式采样通道使用 `0xFE 0xED` 作为通道分隔符

常用数据类型在 `PowerDataType` 与 `POWER_DATA_META` 中维护。修改协议时，需要同步上位机、下位机枚举、协议文档和测试。

### 图表数据流

电源页面将解析后的状态转换为通道数据，写入 `DataHub`。`ChartModel` 从 `DataHub` 读取窗口内数据，`RealtimeChartWidget` 使用 pyqtgraph 展示曲线，并提供通道显示、时间窗口和数值面板。

## 开发约定

- 分层文件命名采用“层名在前、对象在后”的形式，便于文件列表中按职责聚合：页面用 `page_power.py`，控制器用 `controller_power_page.py`，会话用 `session_power.py`，管理器用 `manager_firmware.py`。
- 类名使用 `PascalCase`，并保留清晰的分层后缀，例如 `PowerPage`、`PowerPageController`、`DaplinkPyocdSession`。
- 普通函数和局部工具函数优先使用 `snake_case`；已有 PyQt 页面方法可以继续沿用项目现有的 `camelCase` 风格，避免为了统一命名做无意义的大范围改动。
- 私有方法按用途分组命名：`_init_xxx` 创建界面，`_bind_xxx` 注册事件，`_apply_xxx` 应用配置或状态，`_update_xxx` 刷新显示，`_on_xxx` 响应控件或事件。
- 页面和业务之间的信号按事件语义命名：请求类用 `xxxRequested`，状态类用 `xxxChanged` / `xxxUpdated`，结果类用 `xxxReady` / `xxxFinished`，错误类用 `xxxFailed` / `errorOccurred`。
- 复杂页面优先加 Controller 层。Page 负责控件创建和状态展示，Controller 负责信号绑定和操作入口编排，Session/Client 负责通信细节。
- 页面提示统一调用 `app/core/utility.py` 的 `showMessage(...)`；主窗口会同时显示右上角 InfoBar 和标题栏 DynamicIsland。
- 跨线程通信使用 Qt 信号或自定义 Qt 事件，不要从 worker 线程直接操作控件。
- 新增持久化设置统一走 `config.CTX.cfg` / qfluentwidgets `QConfig`。
- 新增页面样式时，同步 `StyleSheet` 枚举、页面 `objectName` 和 `Resources/Theme/qss/{light,dark}/` 下的 QSS 文件名。
- 修改 Power 协议前，先更新协议表，再同步上下位机枚举、元数据、读写处理和测试。
- DAPLink 烧录默认依赖 `Resources/Tools/Pack/` 中的本地 `.pack` 文件。
- `build/`、`Logs/`、`.venv/`、`__pycache__/`、`.pytest_cache/` 和运行时配置目录不作为源码维护。

## 常用入口

- 应用入口与主窗口导航：`start.py`
- 电源页面：`app/widgets/pages/page_power.py`
- 电源协议：`app/session/session_power.py`
- 串口/蓝牙调试页：`app/widgets/pages/page_device.py`
- 通用串口会话：`app/session/session_serial.py`
- TVLCOM V2 工具：`app/protocol/`
- DAPLink 页面：`app/widgets/pages/page_daplink.py`
- DAPLink 会话：`app/session/session_daplink.py`
- 电池组页面：`app/widgets/pages/page_battery.py`
- 配置与路径：`config/config.py`
- 样式管理：`app/manager/manager_stylesheet.py`
- 实时曲线：`app/widgets/chart/`
