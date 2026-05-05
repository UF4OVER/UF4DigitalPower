# UF4DigitalPower

当前版本：`1.4.0502`

设计一个基于 STM32 的数字电源控制系统（C语言，HAL库），用于同步 Buck/Boost 功率拓扑，要求高实时性与模块化结构。

系统参数：

PWM频率：200kHz
输出范围：0.5–33V，0–10A
控制结构：电压环 + 电流环（双闭环 PID）

采样与量化：

电压采样（输入/输出相同方式）：
电压经 1/13.5135 分压进入 ADC
实际电压 = ADC 电压 × 13.5135
需要软件还原真实电压值
电流采样：
分流电阻：8mΩ
运放增益：20
中点偏置：1.65V
电流范围：±10A → ADC范围约 1.65V ±1.6V（≈0.05V–3.25V）
需进行零点校准与双向电流换算

控制逻辑：

外环（电压环）：
输入：Vref 与 Vout
输出：Iref
内环（电流环）：
输入：Iref 与 Iout
输出：PWM占空比
控制周期：
使用定时器中断（200kHz同步或其整数分频）执行控制算法

## 定时器任务分配

当前版本：`1.4.0502`

| 定时器 | 周期/用途 | 任务归属 | 说明 |
| --- | --- | --- | --- |
| `HRTIM1 Timer A` | 200kHz PWM 同步 | `PowerApp_FastLoop()` | 只跑电压/电流闭环和 PWM 更新，最高实时性 |
| `TIM2` | 1ms | `PowerApp_1msTask()` | 看门狗、LED 节拍、TVLCOM 1s 上报计时，只做轻任务 |
| `TIM3` | 5ms | `PowerApp_5msTask()` | 板温/芯片温度、状态机、保护判断、风扇命令更新 |
| `TIM4` | 10ms | `PowerApp_CommTask()` | TVLCOM 主动 `REPORT` 非阻塞发送/重试 |
| `TIM8 CH3` | PWM 输出 | 风扇 PWM | 仅用于风扇占空比输出，不挂调度任务 |
| `TIM6` | 保留 | 未启动 | 预留给后续 DAC/触发类任务 |
| `TIM7` | 保留 | 未启动 | 预留给后续独立慢周期任务 |
| `TIM16` | 保留 | 未启动 | 预留给捕获/单通道计时 |
| `TIM17` | 保留 | 未启动 | 预留给捕获/单通道计时 |

调度原则：

- 控制环只放在 `HRTIM1`，不要把通信、Flash、温度计算放进去。
- `TIM2` 只做 1ms 轻量节拍，不直接做耗时发送。
- `TIM3` 负责电源慢速状态维护，不再混通信任务。
- `TIM4` 专门处理通信主动上报，避免 `REPORT` 和电源控制任务混在一起。
- Flash 保存仍放在 main foreground/background，不放进任何定时器中断。

## BSP / USER_Code 分层

当前新增分层参考 `example/Buck-Boost-Digital-Power` 的 HAL 模板风格：

```text
BSP/
  Inc/bsp_power_board.h
  Src/bsp_power_board.c

USER_Code/
  Inc/user_power_control.h
  Src/user_power_control.c
```

### BSP 层职责

`BSP` 只做板级外设封装，不写业务状态机：

- ADC DMA 启动与 raw 读取
- HRTIM PWM 启停
- Buck / Boost compare 更新
- ADC 触发点 compare 更新
- 风扇 PWM 输出
- 板温和 CPU 温度读取
- 示例工程一致的 ADC/功率级常量

关键参数与 `example/Buck-Boost-Digital-Power` 对齐：

- `BSP_POWER_HRTIM_PERIOD = 30000`
- `BSP_POWER_ADC_MAX_VALUE = 8190.0`
- `BSP_POWER_VREF = 3.2806`
- 电压分压换算：`75.0 / 4.7`
- 电流采样：双向采样，`0A = 1.65V`，换算为 `(ADC电压 - 1.65V) / (0.005R * 62)`
- Buck/Boost 占空比限幅沿用示例值

### USER_Code 层职责

`USER_Code` 放用户控制逻辑，不直接散落 HAL 操作：

- `UserPower_Init()`
- `UserPower_FastLoop()`
- `UserPower_5msTask()`
- `UserPower_SetOutput()`
- `UserPower_GetSample()`
- `UserPower_GetSetpoint()`

`USER_Code/Src/user_power_control.c` 参考示例工程的 `function.c` 和 `PID.c`，实现：

- ADC raw 采样缓存
- 8 点滑动平均
- 电压/电流实际值换算
- Buck / Boost / Mix 模式判定
- 电压环 + 电流环控制
- OVP / OCP / OTP 基础保护

当前固件运行入口仍是原有 `APP` 层，新增 `USER_Code` 已纳入编译但尚未替换主控制入口。切换时建议按以下顺序：

1. `PowerApp_Init()` 中改为调用 `UserPower_Init()`
2. HRTIM 回调中改为调用 `UserPower_FastLoop()`
3. 5ms 慢任务中改为调用 `UserPower_5msTask()`
4. TVLCOM 读写接口改为读写 `UserPower` 的 sample/setpoint
5. 确认只保留一套 ADC DMA buffer，避免 `APP` 和 `BSP` 同时启动 ADC DMA

PWM与拓扑映射：

使用定时器A输出4路PWM控制同步开关：
A1 → L1（低边1）
A2 → H1（高边1）
D1 → L2（低边2）
D2 → H2（高边2）
支持互补输出与死区控制（Dead Time）

软件设计要求：

ADC + DMA 连续采样（电压、电流）
提供滤波（如一阶低通或滑动平均）
PID控制器支持：
限幅
Anti-windup
控制函数独立：Control_Loop_Run()
分层结构：
BSP/驱动层（ADC、PWM）
控制层（PID、采样处理）
应用层

保护机制：

过压（>33V）
过流（>10A）
欠压
故障时关闭PWM

使用spi对flash进行数据存储，保存PID参数和系统状态，以便在重启后恢复。
使用TVLCOM_V2_FULL进行串口通信，提供实时数据监控和参数调整接口。上位机使用python，python端定义了与TVLCOM协议对应的常量和数据结构，确保通信的一致性和可靠性。
## TVLCOM 常量（与 Python 一一对应）

### 1) 命令字

```python
class TVL_Command(IntEnum):
    ACK = 0x00      # 设备应答
    READ = 0x01     # 读取
    WRITE = 0x02    # 写入
    REPORT = 0x03   # 设备周期主动上报，默认 1s 一次
    NACK = 0xFF     # 错误应答
```

### 2) TLV 类型与数据ID（本项目约定：Type 直接使用 DataType 值）

```python
class TVL_DataType(IntEnum):
    INPUT_VOLTAGE = 10          # mV,  只读
    INPUT_CURRENT = 11          # mA,  只读
    OUTPUT_VOLTAGE = 12         # mV,  只读
    OUTPUT_CURRENT = 13         # mA,  只读
    CORE_TEMPERATURE = 14       # mC,  只读
    BOARD_TEMPERATURE = 15      # mC,  只读

    SET_VOLTAGE_LIMIT = 17      # mV,  读写
    SET_CURRENT_LIMIT = 18      # mA,  读写

    CC_CV_MODE = 20             # 0:CC,1:CV, 只读
    POWER_STATE = 21            # 0:OFF,1:ON, 读写
    FAULT_STATE = 22            # bitmask, 只读

    STATE_MACHINE_FLAG_BITS = 23  # INIT/WAIT/RISE/RUN/ERR, 只读
    STATE_MACHINE_STATE = 24      # NA/BUCK/BOOST/MIX, 只读

    INPUT_VOLTAGE_RAW = 25      # uint32, 只读
    INPUT_CURRENT_RAW = 26      # uint32, 只读
    OUTPUT_VOLTAGE_RAW = 27     # uint32, 只读
    OUTPUT_CURRENT_RAW = 28     # uint32, 只读

    OTP_VALUE = 29              # mC, 只读
    OTP_SET_VALUE = 30          # mC, 读写
    OVP_VALUE = 31              # mV, 只读
    OVP_SET_VALUE = 32          # mV, 读写
    OCP_VALUE = 33              # mA, 只读
    OCP_SET_VALUE = 34          # mA, 读写

    FAN_SPEED = 38              # 风扇PWM命令值，0-1000,只读
    FAN_SET_VALUE = 39          # 风扇PWM命令值，0-1000,读写预留
```

设备会每 1000 ms 主动发送一帧 `REPORT(0x03)`，payload 使用同样的 TLV 编码，包含常用电压、电流、温度、状态、故障、设定电压/电流、保护阈值和风扇命令值。上位机在等待请求 ACK 时应忽略或缓存 `REPORT` 帧，再继续等待相同 `seq` 的 `ACK/NACK`。

### 3) 故障码与状态机枚举

```python
class TVL_FaultCode(IntEnum):
    NO_ERROR = 0x0000
    INPUT_UNDER_VOLTAGE = 0x0001
    INPUT_OVER_VOLTAGE = 0x0002
    OUTPUT_UNDER_VOLTAGE = 0x0004
    OUTPUT_OVER_VOLTAGE = 0x0008
    OUTPUT_OVER_CURRENT = 0x0010
    OUTPUT_SHORT_CIRCUIT = 0x0020
    OVER_TEMPERATURE_PROTECTION = 0x0040

class TVL_StateMachineFlagBits(IntEnum):
    INIT = 0b0001
    WAIT = 0b0010
    RISE = 0b0100
    RUN = 0b1000
    ERR = 0b1111

class TVL_StateMachineFlag(IntEnum):
    NA = 0
    BUCK = 1
    BOOST = 2
    MIX = 3
```

## 1.4.0502 上位机修改建议

### 1) 必须新增 `REPORT` 命令

上位机命令枚举需要加入：

```python
REPORT = 0x03
```

`REPORT` 是设备主动上报帧，不是请求响应。设备默认每 `1000 ms` 主动发送一次，`seq = 0`。

### 2) 接收逻辑必须区分请求响应和主动上报

上位机发送 `READ/WRITE` 后等待 `ACK/NACK` 时，可能先收到 `REPORT`。建议处理逻辑：

```python
while True:
    cmd, seq, payload = read_frame()

    if cmd == TVLCommand.REPORT:
        handle_report(parse_tlvs(payload))
        continue

    if seq != request_seq:
        raise ValueError("seq mismatch")

    if cmd == TVLCommand.NACK:
        raise RuntimeError("device returned NACK")

    if cmd != TVLCommand.ACK:
        raise ValueError(f"unexpected cmd=0x{cmd:02X}")

    return parse_tlvs(payload)
```

### 3) 上位机应直接解析 `REPORT` 刷新实时状态

`REPORT` 至少包含以下 TLV：

```text
INPUT_VOLTAGE
INPUT_CURRENT
OUTPUT_VOLTAGE
OUTPUT_CURRENT
CORE_TEMPERATURE
BOARD_TEMPERATURE
SET_VOLTAGE_LIMIT
SET_CURRENT_LIMIT
CC_CV_MODE
POWER_STATE
FAULT_STATE
STATE_MACHINE_FLAG_BITS
STATE_MACHINE_STATE
OTP_SET_VALUE
OVP_SET_VALUE
OCP_SET_VALUE
FAN_SPEED
```

建议 GUI 主界面优先使用 `REPORT` 更新实时显示；手动查询或补漏时再发送 `READ`。

### 4) 输出电压/电流控制使用 `WRITE` 多 TLV

设置输出电压、电流并开启输出时，建议一次发送三个 TLV：

```python
payload = (
    pack_u32(TVLDataType.SET_VOLTAGE_LIMIT, 12000) +  # 12.000 V
    pack_u32(TVLDataType.SET_CURRENT_LIMIT, 3000) +   # 3.000 A
    pack_u8(TVLDataType.POWER_STATE, 1)               # 1=ON, 0=OFF
)
request(TVLCommand.WRITE, payload)
```

建议封装成上位机接口：

```python
def set_output(voltage_v: float, current_a: float, enabled: bool = True) -> None:
    payload = (
        pack_u32(TVLDataType.SET_VOLTAGE_LIMIT, int(voltage_v * 1000 + 0.5)) +
        pack_u32(TVLDataType.SET_CURRENT_LIMIT, int(current_a * 1000 + 0.5)) +
        pack_u8(TVLDataType.POWER_STATE, 1 if enabled else 0)
    )
    request(TVLCommand.WRITE, payload)
```

### 5) 单位换算规则

- 电压：固件传输 `mV`，上位机显示 `V = value / 1000.0`
- 电流：固件传输 `mA`，上位机显示 `A = value / 1000.0`
- 温度：固件传输 `mC`，上位机显示 `C = value / 1000.0`
- `FAN_SPEED`：当前为风扇 PWM 命令值，范围 `0-1000`，不是实际 RPM
- `POWER_STATE`：`0=OFF`，`1=ON`
- `CC_CV_MODE`：`0=CC`，`1=CV`

### 6) 推荐上位机界面改动

- 增加主动上报接收线程或串口事件循环，持续解析 `REPORT`
- 将 `REPORT` 缓存为最新状态对象，UI 定时从缓存刷新
- 输出设置区提供电压、电流、启停三个控件，提交时发送一次 `WRITE` 多 TLV
- 等待 `ACK/NACK` 的请求函数必须跳过或缓存 `REPORT`
- UI 字段不要写死单位和长度，建议按 DataType 元数据表集中维护
