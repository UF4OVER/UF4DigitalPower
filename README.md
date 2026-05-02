### 1. 项目目标

我要在上位机中通过串口与一个 STM32 数字电源固件通信，实现：

1. 读取实时状态：
   - 输入电压
   - 输入电流
   - 输出电压
   - 输出电流
   - 核心温度
   - 板载温度
   - CC/CV 模式
   - 电源开关状态
   - 故障状态
   - 状态机状态
   - Buck / Boost / Mix 拓扑状态

2. 写入控制参数：
   - 输出电压设定值
   - 输出电流设定值
   - 输出过压保护阈值
   - 输出过流保护阈值
   - 过温保护阈值
   - 电源开关状态

3. 完整处理：
   - 帧封装
   - CRC16 校验
   - ACK/NACK 响应
   - 超时
   - 串口读写异常
   - TLV 解析与编码

请把代码写成“可复用的通信模块”，适合作为上位机项目中的独立文件或独立类。

---

### 2. 串口参数

- 波特率：`115200`
- 数据位：`8`
- 停止位：`1`
- 校验位：`None`
- 即：`115200 8N1`

---

### 3. 帧协议

#### 3.1 帧格式

每一帧格式如下：

```text
+--------+--------+-------------------+------+-----+---------+-----------+
| SOF0   | SOF1   | body_len (uint16) | cmd  | seq | payload | crc16     |
+--------+--------+-------------------+------+-----+---------+-----------+
| 0xAA   | 0x55   | little-endian     | 1B   | 1B  | N bytes | 2B LE     |
+--------+--------+-------------------+------+-----+---------+-----------+
```

其中：

- `SOF0 = 0xAA`
- `SOF1 = 0x55`
- `body_len = cmd + seq + payload` 的总长度
- `cmd` 为命令字
- `seq` 为请求序号，范围 `0~255`
- `payload` 为 TLV 数据区
- `crc16` 为对 `SOF0` 开始到 `payload` 结束这一整段数据做 CRC16/MODBUS，结果按 little-endian 存放

#### 3.2 CRC16 算法

使用标准 `CRC16/MODBUS`：

- 初值：`0xFFFF`
- 多项式：`0xA001`
- 输出 16 位结果
- 帧尾 CRC 按 little-endian 写入

---

### 4. 命令字定义

```python
ACK   = 0x00
READ  = 0x01
WRITE = 0x02
REPORT = 0x03
NACK  = 0xFF
```

说明：

- 上位机发送 `READ` 请求读取数据
- 上位机发送 `WRITE` 请求写入数据
- 设备正常响应 `ACK`
- 设备每 1000 ms 主动发送 `REPORT`，payload 为常用状态 TLV，`seq = 0`
- 设备出错响应 `NACK`

---

### 5. TLV 结构

payload 由多个 TLV 拼接组成，每个 TLV 结构如下：

```text
+--------+------------------+------------------+
| type   | length (uint16)  | value            |
+--------+------------------+------------------+
| 1 byte | little-endian    | length bytes     |
+--------+------------------+------------------+
```

说明：

- `type` 是数据项编号
- `length` 是 value 字节长度
- `value` 是具体数据内容

读取时：

- 上位机发送 `READ` 帧
- payload 中每个 TLV 的 `length = 0`
- value 为空
- 设备看到 `type` 后，在 ACK 中回填对应数据

写入时：

- 上位机发送 `WRITE` 帧
- payload 中每个 TLV 带要写入的值
- 设备写成功后返回 ACK

---

### 6. 数据类型与单位

设备返回的大多数测量值和设定值都使用 `uint32 little-endian`，但单位不是浮点原始值，而是“放大后的整数”：

- 电压：单位 `mV`
- 电流：单位 `mA`
- 温度：单位 `mC`，即毫摄氏度
- 状态量：通常 `uint8`
- 故障位：`uint32 bitmask`

因此上位机显示时需要换算：

- `12000` -> `12.000 V`
- `3000` -> `3.000 A`
- `80000` -> `80.000 C`

---

### 7. DataType 定义

请严格使用以下 type 编号，不要自行修改：

```python
INPUT_VOLTAGE = 10          # uint32, mV, 只读
INPUT_CURRENT = 11          # uint32, mA, 只读
OUTPUT_VOLTAGE = 12         # uint32, mV, 只读
OUTPUT_CURRENT = 13         # uint32, mA, 只读
CORE_TEMPERATURE = 14       # uint32, mC, 只读
BOARD_TEMPERATURE = 15      # uint32, mC, 只读

SET_VOLTAGE_LIMIT = 17      # uint32, mV, 读写
SET_CURRENT_LIMIT = 18      # uint32, mA, 读写

CC_CV_MODE = 20             # uint8,  0=CC,1=CV, 只读
POWER_STATE = 21            # uint8,  0=OFF,1=ON, 读写
FAULT_STATE = 22            # uint32, bitmask, 只读

STATE_MACHINE_FLAG_BITS = 23 # uint8, 状态位, 只读
STATE_MACHINE_STATE = 24     # uint8, 0=NA,1=BUCK,2=BOOST,3=MIX, 只读

INPUT_VOLTAGE_RAW = 25      # uint32, ADC raw, 只读
INPUT_CURRENT_RAW = 26      # uint32, ADC raw, 只读
OUTPUT_VOLTAGE_RAW = 27     # uint32, ADC raw, 只读
OUTPUT_CURRENT_RAW = 28     # uint32, ADC raw, 只读

OTP_VALUE = 29              # uint32, mC, 当前板温, 只读
OTP_SET_VALUE = 30          # uint32, mC, 过温阈值, 读写
OVP_VALUE = 31              # uint32, mV, 当前输出电压, 只读
OVP_SET_VALUE = 32          # uint32, mV, 过压阈值, 读写
OCP_VALUE = 33              # uint32, mA, 当前输出电流, 只读
OCP_SET_VALUE = 34          # uint32, mA, 过流阈值, 读写

FAN_SPEED = 38              # uint32, 风扇PWM命令值，0-1000，只读
FAN_SET_VALUE = 39          # uint32, 风扇PWM命令值，0-1000，读写预留
```

固件还维护一张数据项描述表，包含 `type / value_type / access / unit`：

- `value_type`: `U8 = 1`, `U32 = 4`
- `access`: `READ = 0x01`, `WRITE = 0x02`, `READ_WRITE = 0x03`
- 单位使用 `mV / mA / mC / enum / bool / bitmask / adc / permille`

上位机建议用同样的元数据表生成读写 UI 和参数校验，避免把长度、单位、读写权限散落在界面代码里。

### 7.1 主动上报 REPORT

设备每 1000 ms 主动发送一帧：

```text
--------+-----+----------------------+
| cmd    | seq | payload              |
+--------+-----+----------------------+
| 0x03   | 0   | 多个状态 TLV          |
+--------+-----+----------------------+
```

当前 `REPORT` payload 至少包含：

- `INPUT_VOLTAGE`
- `INPUT_CURRENT`
- `OUTPUT_VOLTAGE`
- `OUTPUT_CURRENT`
- `CORE_TEMPERATURE`
- `BOARD_TEMPERATURE`
- `CC_CV_MODE`
- `POWER_STATE`
- `FAULT_STATE`
- `STATE_MACHINE_FLAG_BITS`
- `STATE_MACHINE_STATE`
- `FAN_SPEED`

上位机在发送请求后等待 `ACK/NACK` 时，如果先收到 `REPORT`，应先解析/缓存或直接忽略该帧，然后继续等待相同 `seq` 的响应。

---

### 8. 故障位定义

`FAULT_STATE` 是一个 bitmask，按如下解析：

```python
NO_ERROR = 0x0000
INPUT_UNDER_VOLTAGE = 0x0001
INPUT_OVER_VOLTAGE = 0x0002
OUTPUT_UNDER_VOLTAGE = 0x0004
OUTPUT_OVER_VOLTAGE = 0x0008
OUTPUT_OVER_CURRENT = 0x0010
OUTPUT_SHORT_CIRCUIT = 0x0020
OVER_TEMPERATURE_PROTECTION = 0x0040
```

上位机需要提供：

- 原始整数值
- 可读的故障名称列表

---

### 9. 状态位定义

`STATE_MACHINE_FLAG_BITS` 的含义：

```python
INIT = 0b0001
WAIT = 0b0010
RISE = 0b0100
RUN  = 0b1000
ERR  = 0b1111
```

`STATE_MACHINE_STATE` 的含义：

```python
NA = 0
BUCK = 1
BOOST = 2
MIX = 3
```

---

### 10. 读操作规则

如果上位机要读取多个数据项，请构造一个 `READ` 帧，payload 中放多个空 TLV：

例如要读取：

- 输入电压
- 输出电压
- 输出电流
- 故障状态

则 payload 逻辑上是：

```text
TLV(type=10, length=0)
TLV(type=12, length=0)
TLV(type=13, length=0)
TLV(type=22, length=0)
```

设备返回 `ACK`，payload 中会包含这些 type 对应的 TLV 及真实值。

要求 AI 生成的代码支持：

- 单项读取
- 多项批量读取
- 自动把结果解析成字典或结构体

---

### 11. 写操作规则

写操作发送 `WRITE` 帧，payload 中放带 value 的 TLV。

例如：

- 设置输出电压 12V -> `12000 mV`
- 设置输出电流 3A -> `3000 mA`
- 开启输出 -> `1`

逻辑上：

```text
TLV(type=17, length=4, value=12000 as uint32 LE)
TLV(type=18, length=4, value=3000 as uint32 LE)
TLV(type=21, length=1, value=1)
```

设备成功后返回 `ACK`。

要求 AI 生成的代码支持以下高层接口：

- `set_voltage_limit_mv(value_mv)`
- `set_current_limit_ma(value_ma)`
- `set_ovp_mv(value_mv)`
- `set_ocp_ma(value_ma)`
- `set_otp_mc(value_mc)`
- `set_power_state(enabled: bool)`


---

### 12. 代码要求

请严格遵守以下要求：

1. 使用 Python 3
2. 串口库使用 `pyserial`
3. 类型注解尽量完整
4. 读写逻辑不要写死在 UI 中，要做成可复用模块
5. 提供：
   - 低层接口：发送帧、收帧、解析 TLV
   - 高层接口：读取状态、设置参数
6. 代码中加入必要注释，但不要写无意义注释
7. 所有整数解码默认使用 little-endian
8. 设备返回 `NACK` 时抛出明确异常
9. 接收超时时抛出明确异常
10. CRC 校验失败时抛出明确异常

---

### 13. 希望生成的高层接口示例

我希望最终能这样调用：

```python
host = TVLHost("COM6", 115200, timeout=1.0)

host.set_voltage_limit_mv(12000)
host.set_current_limit_ma(3000)
host.set_ovp_mv(33000)
host.set_ocp_ma(10000)
host.set_otp_mc(80000)
host.set_power_state(True)

status = host.read_status()
print(status.vin_v)
print(status.vout_v)
print(status.iout_a)
print(status.fault_state)

host.close()
```

其中：

- `vin_v` / `vout_v` 以 `float` 返回，单位 `V`
- `iin_a` / `iout_a` 以 `float` 返回，单位 `A`
- `core_temp_c` / `board_temp_c` 以 `float` 返回，单位 `C`
- `fault_state` 保留原始 bitmask
- 再提供一个函数把 bitmask 转成字符串列表

---

### 14. 响应处理细节

AI 生成代码时必须正确处理以下细节：

1. 发送请求后只接受相同 `seq` 的响应
2. 如果响应 `seq` 不一致，应报错
3. 如果响应命令不是 `ACK` 或 `NACK`，应报错
4. 如果响应为 `NACK`，应抛异常
5. 允许一次 `READ` 返回多个 TLV
6. 解析 TLV 时，如果结构不完整，应抛异常
7. 如果某个请求的数据项未在响应中出现，应抛异常或给出明确提示

---

### 15. 不要做的事

请不要：

1. 不要把协议改成 JSON
2. 不要把数值直接按浮点发给设备
3. 不要擅自修改 type 编号
4. 不要省略 CRC
5. 不要假设设备会主动上报数据
6. 不要把 UI 和协议耦合在同一个函数里

---

---