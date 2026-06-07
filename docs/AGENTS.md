# AGENTS.md

## 项目概览

- `F4CP` 是 Windows 优先的 PyQt5 桌面应用，基于 `qfluentwidgets` 构建。
- 真实入口是 `start.py`，它会实例化 `Application(Window)`。主窗口类 `Window(MSFluentWindow)` 位于 `app/window/main_window.py`，并通过 `ui.py` 进行兼容性导出。
- 采用模块化三层设计：视图层（`app/widgets/pages/*`）、控制层（`app/controllers/*`）和会话/工作线程层（`app/session/*`）。
- 运行时路径的事实来源是 `config/config.py` 中的 `DirPaths`，它会根据 `sys.frozen` 自动在源码目录和冻结后的 exe 目录之间切换。提供全局上下文 `CTX.dirs` 和全局配置 `CTX.cfg` (对应于底层的 `Resources/Config/config.json` 存储)。

## 主要子系统与三层架构

应用拆分为以下核心子系统，并遵循 **页面(View) - 控制器(Controller) - 会话/设备驱动(Session/Device)** 的清晰边界设计：

### 1. 引导、设置与版本管理器 (Home, Settings, Version)
- **页面**：`app/widgets/pages/page_home.py`、`page_settings.py`、`page_version.py`。
- **管理器**：`app/manager/*`（配合 `config/config.py` 加载保存配置，`manager_font.py` 加载/存取字体，`manager_stylesheet.py` 动态换肤，`manager_update.py` 负责从 GitHub API 检查程序更新）

### 2. 串口与 TVLCOM V2 调试控制台 (Serial Console)
- **页面**：`app/widgets/pages/page_device.py` 呈现原始串口收发、HEX/ASCII 格式 and TLV 动态列表。
- **控制器**：`app/controllers/controller_device_page.py` 绑定 UI 交互信号至底层后台槽。
- **会话层**：`app/session/session_serial.py` 精确管理串口事件流、缓冲区及后台轮询。
- **协议层**：`app/protocol/*` (`dataType.py`, `frameBuilder.py`, `frameParser.py`, `payLoad.py`, `unitls.py`) 处理标准的 TVLCOM V2 (SOF = `0x5AA5`) 编码与 CRC16 校验。

### 3. 数字电源与电池仪表盘 (Power & Battery Dashboard)
- **页面**：`app/widgets/pages/page_power.py` 绘制状态面板和参数编辑，`app/widgets/pages/page_battery.py` 负责电池单体监测。
- **控制器**：`app/controllers/controller_power_page.py` 彻底解耦 UI，将页面的参数编辑请求映射至 `F4CPPowerClient` 的读写请求，将 client 回调通过 Qt 连接到对应的页面展示函数中。
- **会话/驱动**：`app/session/session_power.py` 的 `F4CPPowerClient` 放在独立的多线程上下文中工作。
- **设备抽象**：`app/devices/*` (`device_power.py`, `device_bms.py`, `device_other.py` 继承自 `device_base.py`) 提供数据解析模型。
- **实时数据流**：`app/core/data_hub.py` 的数据通道协调环形缓冲区 `app/core/ring_buffer.py`，供 `app/widgets/chart/*` 中的实时 PyQtGraph 仪表盘持续平滑绘图。

### 4. DAPLink 专业烧录 (DAPLink Flash / Programmer)
- **页面**：`app/widgets/pages/page_daplink.py`。
- **控制器**：`app/controllers/controller_daplink_page.py`。
- **工作会话**：`app/session/session_daplink.py` 通过多线程/异步任务运行 pyOCD 进行固件擦除、编程和复位。
- **CMSIS 本地支持**：从 `Resources/Tools/Pack` 目录加载 MCU 本地 `.pack` 设备描述程序包。

### 5. 统一消息与动态标题栏
- **标题栏通知**：主窗口 `main_window.py` 挂载 `DynamicIsland` 挂件到自定义 `titleBar` 部分。
- **高兼容通知 API**：调用 `app/core/utility.py` 中的 `showMessage(...)` 将优先选择 `DynamicIsland` 渲染精美悬浮动画，若不可用自动降级为 qfluentwidgets 的 `InfoBar` 右上角弹窗。

## 必须保持的通信模式

- **禁止从 Worker 直接修改 UI**：工作线程、后台多线程（如 `F4CPPowerClient`、DAPLink 的 PyOCD 运行线程）绝对不允许直接对 Qt UI 组件属性进行修改。
- **多线程与自定义事件**：多线程组件必须使用 Qt 信号或派发自定义事件（例如 `DaplinkProgrammerEvent` 或串口自定义 Event 流）完成 UI 状态、日志、数据的异步推送。
- **槽与控制器解耦**：当增加新功能、按钮时，请把事件信号注册/绑定写在 `app/controllers/` 对应的控制器类内。

## 关键协议细节

- **数字电源协议 (Power Protocol)**：使用专用轻量级电源协议，其开始符 `SOF = b"\xAA\x55"` 并非通用串口的 `0x5AA5`，附带 Modbus CRC16 与专有的极简 TLV 指令集。
- **通用 TVLCOM V2 协议**：使用 `SOF = b"\x5A\xA5"`，其类型映射可通过 `app/protocol/dataType.py` 的 `TYPE_REGISTRY` 与 `app/core/const.py` 自定义或重命名。
- **数据缓冲机制**：数字电源与串口数据采用 `RingBuffer` 进行接收分流处理，防止在高速数据倾泻时阻塞 Qt Event Loop。

## 配置、资源与生成文件

- **QSS 与主题**：QSS 配置文件存放在 `Resources/Theme/qss/{dark,light}/` 路径中。页面类的 `objectName()` 字符需与 QSS 文件名称保持绝对匹配。
- **资源路径统一**：禁止使用绝对硬编码路径。必须始终通过 `config.CTX.dirs.ResourcesDir`（或其子属性 `ThemeDir`、`FontDir`、`ConfigDir`）获取运行时绝对路径。

## 常用命令

```powershell
# 同步环境依赖
uv sync

# 源码模式启动 (Windows PowerShell)
uv run python start.py

# 启动简易电源硬件模拟器协助开发
uv run python script/sim_power_device.py

# 发现并执行项目单元测试
uv run python -m unittest discover -s tests

# 一键打包可执行 exe (会在 Build/exe/ 输出)
.\script\package_exe.ps1

# 使用 UPX 压缩并打包分发 Zip
uv run python script/upx_zip.py
```

## 修改行为前优先查看

- 应用外壳及入口绑定：`start.py` 与 `ui.py`
- 主窗口与导航体系：`app/window/main_window.py` & `app/window/navigation.py`
- 控制器层定义：`app/controllers/`
- 各独立页面渲染：`app/widgets/pages/`
- 各底层会话线程：`app/session/`
