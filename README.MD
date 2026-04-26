设计一个基于 STM32 的数字电源控制系统（C语言，HAL库），用于同步 Buck/Boost 功率拓扑，要求高实时性与模块化结构。

系统参数：

PWM频率：200kHz
输出范围：0–33V，0–10A
控制结构：电压环 + 电流环（双闭环 PID）

采样与量化：

电压采样（输入/输出相同方式）：
电压经 1/10 分压进入 ADC
实际 0–33V → ADC 0–3.3V
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
使用TVLCOM_V2_FULL进行串口通信，提供实时数据监控和参数调整接口。
## TVLCOM 常量（与 Python 一一对应）

### 1) 命令字

```python
class TVL_Command(IntEnum):
    ACK = 0x00      # 设备应答
    READ = 0x01     # 读取
    WRITE = 0x02    # 写入
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

    FAN_SPEED = 38              # RPM,只读(当前固件未接测速，返回0)
    FAN_SET_VALUE = 39          # RPM,读写
```

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

## TVLCOM 帧拼接用法

### 1) 帧格式

```text
SOF0 SOF1 LEN_L LEN_H CMD SEQ PAYLOAD... CRC_L CRC_H
```

- `SOF0=0xAA`, `SOF1=0x55`
- `LEN = CMD+SEQ+PAYLOAD` 的总长度（小端）
- `CRC16` 使用项目 `tvlcom_crc16`（Modbus 多项式 `0xA001`，初值 `0xFFFF`）

### 2) TLV 格式

```text
TYPE LEN_L LEN_H VALUE...
```

- 本项目中 `TYPE = TVL_DataType`
- `VALUE` 推荐用 `uint32` 小端（工程当前主要按此解析）

### 3) Python 示例：拼 READ / WRITE

```python
import struct
from enum import IntEnum

class TVL_Command(IntEnum):
    ACK = 0x00
    READ = 0x01
    WRITE = 0x02
    NACK = 0xFF

class TVL_DataType(IntEnum):
    OUTPUT_VOLTAGE = 12
    OUTPUT_CURRENT = 13
    SET_VOLTAGE_LIMIT = 17
    SET_CURRENT_LIMIT = 18
    POWER_STATE = 21

def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if (crc & 1) else (crc >> 1)
    return crc & 0xFFFF

def pack_tlv_u32(data_type: int, value: int) -> bytes:
    return struct.pack("<BHI", data_type, 4, value)

def build_frame(cmd: int, seq: int, payload: bytes) -> bytes:
    body_len = 2 + len(payload)  # CMD + SEQ + payload
    head = struct.pack("<BBHBB", 0xAA, 0x55, body_len, cmd, seq)
    crc = crc16_modbus(head + payload)
    return head + payload + struct.pack("<H", crc)

# READ: 读输出电压/电流
read_payload = pack_tlv_u32(TVL_DataType.OUTPUT_VOLTAGE, 0) + \
               pack_tlv_u32(TVL_DataType.OUTPUT_CURRENT, 0)
frame_read = build_frame(TVL_Command.READ, seq=1, payload=read_payload)

# WRITE: 设定 12V, 3A, 打开输出
write_payload = pack_tlv_u32(TVL_DataType.SET_VOLTAGE_LIMIT, 12000) + \
                pack_tlv_u32(TVL_DataType.SET_CURRENT_LIMIT, 3000) + \
                pack_tlv_u32(TVL_DataType.POWER_STATE, 1)
frame_write = build_frame(TVL_Command.WRITE, seq=2, payload=write_payload)
```

### 4) 响应解析约定

- 收到 `CMD=0x00(ACK)`：表示成功；若有 payload，按 TLV 解析读取值
- 收到 `CMD=0xFF(NACK)`：表示参数错误、类型不支持或格式错误
- 数值单位统一：
  - 电压：`mV`
  - 电流：`mA`
  - 温度：`mC`（摄氏度 x1000）