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


# F4CP / UF4DigitalPower 通信命令表

本文档是上位机 `F4CP` 与功率固件 `UF4DigitalPower` 之间 TVLCOM 通信命令的统一契约。修改通信命令、数据类型、单位或访问权限时，先改这份表，再同步：

- 上位机：`F4CP/App/Core/Session/session_powert.py`
- 固件：`UF4DigitalPower/USER/Inc/user_tvlcom.h`
- 固件处理：`UF4DigitalPower/USER/Src/user_tvlcom.c`
- 示例：`UF4DigitalPower/Docs/tvl_host_example.py`

## 帧格式

```text
SOF(2) + Length(2, little-endian) + CMD(1) + SEQ(1) + Payload(N) + CRC16(2, little-endian)
```

- `SOF`: `0xAA 0x55`
- `Length`: `CMD + SEQ + Payload` 的字节数
- `SEQ`: 请求方递增序号；固件响应必须回同一个 `SEQ`
- `CRC16`: Modbus CRC16，初值 `0xFFFF`，多项式 `0xA001`，little-endian
- `Payload`: TLV 列表，格式为 `Type(1) + Length(2, little-endian) + Value(N)`

## 命令码

| 名称 | 值 | 方向 | Payload | 说明 |
| --- | ---: | --- | --- | --- |
| `ACK` | `0x00` | 固件 -> 上位机 | TLV 列表或空 | 请求成功响应。`READ` 成功时返回请求的数据；`WRITE` 成功时为空。 |
| `READ` | `0x01` | 上位机 -> 固件 | TLV 查询列表 | 每个 TLV 只填 `Type`，`Length=0`。 |
| `WRITE` | `0x02` | 上位机 -> 固件 | TLV 写入列表 | 每个 TLV 填 `Type`、长度和 little-endian 值。 |
| `REPORT` | `0x03` | 双向 | 请求空载荷；响应 TLV 列表 | 上位机发送空 payload 请求状态组，固件返回一帧 `REPORT`。 |
| `NACK` | `0xFF` | 固件 -> 上位机 | 空 | 命令、类型、长度、权限或载荷错误。 |

## 访问权限

| 名称 | 值 | 说明 |
| --- | ---: | --- |
| `READ` | `0x01` | 可读 |
| `WRITE` | `0x02` | 可写 |
| `READ_WRITE` | `0x03` | 可读可写 |

## 数据类型

| 名称 | Type | 长度 | 权限 | 单位 | 说明 |
| --- | ---: | ---: | --- | --- | --- |
| `INPUT_VOLTAGE` | `10` | 4 | READ | mV | 输入电压 |
| `INPUT_CURRENT` | `11` | 4 | READ | mA | 输入电流 |
| `OUTPUT_VOLTAGE` | `12` | 4 | READ | mV | 输出电压 |
| `OUTPUT_CURRENT` | `13` | 4 | READ | mA | 输出电流 |
| `CORE_TEMPERATURE` | `14` | 4 | READ | mC | 核心温度，摄氏度 x1000 |
| `BOARD_TEMPERATURE` | `15` | 4 | READ | mC | 板载温度，摄氏度 x1000 |
| `SET_VOLTAGE_LIMIT` | `17` | 4 | READ_WRITE | mV | 输出电压设定 |
| `SET_CURRENT_LIMIT` | `18` | 4 | READ_WRITE | mA | 输出电流设定 |
| `CC_CV_MODE` | `20` | 1 | READ | enum | `0=CC`, `1=CV` |
| `POWER_STATE` | `21` | 1 | READ_WRITE | bool | `0=OFF`, `1=ON` |
| `FAULT_STATE` | `22` | 4 | READ | bitmask | 故障位图 |
| `STATE_MACHINE_FLAG_BITS` | `23` | 1 | READ | bitmask | `0x01=INIT`, `0x02=WAIT`, `0x04=RISE`, `0x08=RUN`, `0x0F=ERR` |
| `STATE_MACHINE_STATE` | `24` | 1 | READ | enum | 当前功率拓扑：`0=NA`, `1=BUCK`, `2=BOOST`, `3=MIX` |
| `INPUT_VOLTAGE_RAW` | `25` | 4 | READ | adc | 输入电压 ADC 原始值 |
| `INPUT_CURRENT_RAW` | `26` | 4 | READ | adc | 输入电流 ADC 原始值 |
| `OUTPUT_VOLTAGE_RAW` | `27` | 4 | READ | adc | 输出电压 ADC 原始值 |
| `OUTPUT_CURRENT_RAW` | `28` | 4 | READ | adc | 输出电流 ADC 原始值 |
| `OTP_VALUE` | `29` | 4 | READ | mC | 当前过温保护参考值 |
| `OTP_SET_VALUE` | `30` | 4 | READ_WRITE | mC | 过温保护设定 |
| `OVP_VALUE` | `31` | 4 | READ | mV | 当前过压保护参考值 |
| `OVP_SET_VALUE` | `32` | 4 | READ_WRITE | mV | 过压保护设定 |
| `OCP_VALUE` | `33` | 4 | READ | mA | 当前过流保护参考值 |
| `OCP_SET_VALUE` | `34` | 4 | READ_WRITE | mA | 过流保护设定 |
| `FAN_SPEED` | `38` | 4 | READ | permille | 风扇当前值，0 到 1000 |
| `FAN_SET_VALUE` | `39` | 4 | READ_WRITE | permille | 风扇设定值，0 到 1000 |
| `DEBUG_SNAPSHOT` | `40` | 0 | READ | virtual | 虚拟读取项。请求 `Type=40, Length=0`；响应返回 `OUTPUT_VOLTAGE_RAW`、`OUTPUT_VOLTAGE`、`OVP_SET_VALUE` 三个 TLV。 |

## 状态组上报

上位机发送：

```text
CMD=REPORT, Payload = empty
```

固件返回：

```text
CMD=REPORT, Payload =
  TLV(INPUT_VOLTAGE)
  TLV(INPUT_CURRENT)
  TLV(OUTPUT_VOLTAGE)
  TLV(OUTPUT_CURRENT)
  TLV(CORE_TEMPERATURE)
  TLV(BOARD_TEMPERATURE)
  TLV(SET_VOLTAGE_LIMIT)
  TLV(SET_CURRENT_LIMIT)
  TLV(CC_CV_MODE)
  TLV(POWER_STATE)
  TLV(FAULT_STATE)
  TLV(STATE_MACHINE_FLAG_BITS)
  TLV(STATE_MACHINE_STATE)
  TLV(OTP_VALUE)
  TLV(OTP_SET_VALUE)
  TLV(OVP_VALUE)
  TLV(OVP_SET_VALUE)
  TLV(OCP_VALUE)
  TLV(OCP_SET_VALUE)
  TLV(DUTY_CMD)
  TLV(PWM_A_COMPARE)
  TLV(PWM_D_COMPARE)
  TLV(FAN_SPEED)
  TLV(FAN_SET_VALUE)
```

## 常用请求

读取状态：

```text
CMD=READ, Payload = TLV(Type=10, Len=0) + TLV(Type=11, Len=0) + ...
```

写输出设定并开机：

```text
CMD=WRITE
Payload =
  TLV(Type=17, Len=4, Value=set_voltage_mv)
  TLV(Type=18, Len=4, Value=set_current_ma)
  TLV(Type=21, Len=1, Value=1)
```

读取调试快照：

```text
CMD=READ
Payload = TLV(Type=40, Len=0)
Response ACK Payload =
  TLV(Type=27, Len=4, Value=output_voltage_raw)
  TLV(Type=12, Len=4, Value=output_voltage_mv)
  TLV(Type=32, Len=4, Value=ovp_set_value_mv)
```

## 同步检查清单

1. 新增 `CMD` 时，同时更新上位机 `PowerCommand`、固件 `user_tvl_cmd_t` 和本文档。
2. 新增数据 `Type` 时，同时更新上位机 `PowerDataType`、固件 `user_tvl_data_type_t`、元数据表和读写处理。
3. 改单位或长度时，同时更新 `POWER_DATA_META`、`g_user_tvl_data_descriptors` 和本文档。
4. 改写权限时，同时更新上位机 `_ensure_writable` 依赖的元数据和固件 `user_tvlcom_handle_write` 分支。
5. `REPORT` 状态组字段变更时，需同步上位机 `REPORT_STATUS_TYPES` 与固件 `report_types`。
