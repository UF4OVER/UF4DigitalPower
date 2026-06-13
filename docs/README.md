# 通信协议 V3

适用于：

- UART
- USB CDC
- RS485
- TCP透传
- 数字电源控制器
- STM32上位机调试

---

# 1. 帧格式

| 字段    | 长度(Byte) | 示例       | 说明       |
|-------|---------:|----------|----------|
| SOF   |        2 | AA 55    | 固定帧头     |
| SEQ   |        1 | 01       | 帧序号      |
| FLAGS |        1 | 01       | 控制标志     |
| CMD   |        1 | 01       | 命令码      |
| LEN   |        1 | 09       | DATA总字节数 |
| DATA  |        N | 0A 33 20 | 数据区      |
| CRC16 |        2 | XX XX    | CRC校验    |

---

# 2. CRC16

## 参数

| 参数     | 值      |
|--------|--------|
| Poly   | 0x1021 |
| Init   | 0xFFFF |
| XorOut | 0x0000 |

## 计算范围

| 包含    |
|-------|
| SEQ   |
| FLAGS |
| CMD   |
| LEN   |
| DATA  |

## 不包含

| 不包含   |
|-------|
| SOF   |
| CRC16 |

## 字节序

| 字段    | 顺序          |
|-------|-------------|
| CRC16 | CRC_L CRC_H |

即：

```text
Little Endian
```

---

# 3. FLAGS定义

| Bit | Mask | 名称        | 说明     |
|-----|------|-----------|--------|
| 0   | 0x01 | ACK_REQ   | 请求ACK  |
| 1   | 0x02 | ACK_FRAME | ACK回复帧 |
| 2   | 0x04 | ERROR     | 错误响应   |
| 3~7 | -    | Reserved  | 保留     |

## FLAGS示例

| FLAGS | 含义         |
|-------|------------|
| 0x00  | 普通数据帧      |
| 0x01  | 请求ACK      |
| 0x02  | ACK回复      |
| 0x06  | ACK回复 + 错误 |

---

# 4. CMD定义

| CMD(hex) | 名称               | 方向       |
|----------|------------------|----------|
| 0x01     | READ_REQ         | PC → MCU |
| 0x81     | READ_RSP         | MCU → PC |
| 0x02     | WRITE_REQ        | PC → MCU |
| 0x82     | WRITE_RSP        | MCU → PC |
| 0x10     | STREAM_START_REQ | PC → MCU |
| 0x90     | STREAM_START_RSP | MCU → PC |
| 0x11     | STREAM_STOP_REQ  | PC → MCU |
| 0x91     | STREAM_STOP_RSP  | MCU → PC |
| 0x15     | STREAM_DATA      | MCU → PC |

---

# 5. DATA格式

采用固定长度 TV 格式。

## 单个数据项

| 字段    | 长度(Byte) |
|-------|---------:|
| ID    |        1 |
| VALUE |        2 |

总长度：

| 项目   | 长度(Byte) |
|------|---------:|
| 单个TV |        3 |

---

## 数据格式

```text
+------+----------+
| ID   | VALUE    |
+------+----------+
 1Byte   2Byte
```

---

## VALUE定义

| 类型       | 长度     | 范围        |
|----------|--------|-----------|
| uint16_t | 2 Byte | 0 ~ 65535 |

适用于：

- 电压
- 电流
- 温度
- PWM
- ADC
- DAC
- 风扇转速
- 状态量

---

# 6. LEN定义

LEN表示：

```text
DATA总字节数(Byte)
```

## 示例

| 数据项数量 | DATA长度(Byte) | LEN |
|------:|-------------:|----:|
|     1 |            3 |   3 |
|     2 |            6 |   6 |
|     3 |            9 |   9 |
|     4 |           12 |  12 |
|     8 |           24 |  24 |

---

# 7. READ示例

## 上位机发送

读取：

- INPUT_VOLTAGE
- INPUT_CURRENT
- OUTPUT_VOLTAGE

| 字段    | 值                          |
|-------|----------------------------|
| SOF   | AA 55                      |
| SEQ   | 01                         |
| FLAGS | 01                         |
| CMD   | 01                         |
| LEN   | 09                         |
| DATA  | 0A 00 00 0B 00 00 0C 00 00 |

---

## 下位机回复

| 字段    | 值                          |
|-------|----------------------------|
| SOF   | AA 55                      |
| SEQ   | 01                         |
| FLAGS | 02                         |
| CMD   | 81                         |
| LEN   | 09                         |
| DATA  | 0A 33 20 0B 01 40 0C 12 34 |

---

## DATA解析

| ID   | VALUE(hex) | VALUE(dec) |
|------|------------|-----------:|
| 0x0A | 0x3320     |      13088 |
| 0x0B | 0x0140     |        320 |
| 0x0C | 0x1234     |       4660 |

---

# 8. WRITE示例

## 上位机发送

设置：

| 参数                |   数值 |
|-------------------|-----:|
| SET_VOLTAGE_LIMIT | 2500 |
| SET_CURRENT_LIMIT | 1000 |
| FAN_SET_VALUE     |  100 |

对应DATA：

| Byte流                      |
|----------------------------|
| 11 09 C4 12 03 E8 27 00 64 |

完整帧：

| 字段    | 值                          |
|-------|----------------------------|
| SOF   | AA55                       |
| SEQ   | 02                         |
| FLAGS | 01                         |
| CMD   | 02                         |
| LEN   | 09                         |
| DATA  | 11 09 C4 12 03 E8 27 00 64 |

---

## 下位机回复

| 字段    | 值    |
|-------|------|
| SOF   | AA55 |
| SEQ   | 02   |
| FLAGS | 02   |
| CMD   | 82   |
| LEN   | 09   |
| DATA  | 原样回显 |

---

# 9. STREAM_START示例

## 上位机发送

启动周期上传：

- 输入电压
- 输入电流
- 输出电压

| 字段   | 值                          |
|------|----------------------------|
| CMD  | 10                         |
| LEN  | 09                         |
| DATA | 0A 00 00 0B 00 00 0C 00 00 |

---

## 下位机回复

| 字段  | 值  |
|-----|----|
| CMD | 90 |
| LEN | 00 |

---

# 10. STREAM_DATA示例

下位机主动发送：

| 字段    | 值                          |
|-------|----------------------------|
| CMD   | 15                         |
| FLAGS | 00                         |
| LEN   | 09                         |
| DATA  | 0A 33 20 0B 01 40 0C 12 34 |

说明：

```text
主动上传数据
无需ACK
```

---

# 11. STREAM_STOP示例

## 上位机发送

| 字段  | 值  |
|-----|----|
| CMD | 11 |
| LEN | 00 |

---

## 下位机回复

| 字段  | 值  |
|-----|----|
| CMD | 91 |
| LEN | 00 |

---

# 12. 错误响应

## 错误帧格式

| 字段    | 值      |
|-------|--------|
| FLAGS | 06     |
| CMD   | 原响应CMD |
| DATA  | 错误码    |

---

## 示例

读取不存在ID：

| 字段    | 值        |
|-------|----------|
| SOF   | AA55     |
| SEQ   | 03       |
| FLAGS | 06       |
| CMD   | 81       |
| LEN   | 03       |
| DATA  | FF 00 01 |

---

# 13. 错误码定义

| 错误码    | 名称             | 说明    |
|--------|----------------|-------|
| 0x0000 | OK             | 成功    |
| 0x0001 | INVALID_ID     | ID不存在 |
| 0x0002 | INVALID_CMD    | 命令错误  |
| 0x0003 | CRC_ERROR      | CRC错误 |
| 0x0004 | INVALID_LEN    | 长度错误  |
| 0x0005 | WRITE_PROTECT  | 不允许写入 |
| 0x0006 | OUT_OF_RANGE   | 参数超范围 |
| 0x0007 | DEVICE_BUSY    | 设备忙   |
| 0x0008 | INTERNAL_ERROR | 内部错误  |

---

# 14. 数据ID定义

| ID(hex) | 名称                             | RW | 单位   | 说明       |
|---------|--------------------------------|----|------|----------|
| 0x0A    | INPUT_VOLTAGE                  | R  | mV   | 输入电压     |
| 0x0B    | INPUT_CURRENT                  | R  | mA   | 输入电流     |
| 0x0C    | OUTPUT_VOLTAGE                 | R  | mV   | 输出电压     |
| 0x0D    | OUTPUT_CURRENT                 | R  | mA   | 输出电流     |
| 0x0E    | CORE_TEMPERATURE               | R  | m℃   | 核心温度     |
| 0x0F    | TEMP1_TEMPERATURE              | R  | m℃   | 第一温度     |
| 0x10    | TEMP2_TEMPERATURE              | R  | m℃   | 第二温度     |
| 0x11    | SET_VOLTAGE_LIMIT              | RW | mV   | 电压设定值    |
| 0x12    | SET_CURRENT_LIMIT              | RW | mA   | 电流设定值    |
| 0x14    | CC_CV_MODE                     | R  | -    | CC/CV模式  |
| 0x15    | POWER_STATE                    | RW | -    | 电源状态     |
| 0x16    | FAULT_STATE                    | R  | -    | 故障状态     |
| 0x17    | STATE_MACHINE_FLAG_BITS        | R  | -    | 状态机标志    |
| 0x18    | STATE_MACHINE_STATE            | R  | -    | 状态机状态    |
| 0x19    | INPUT_VOLTAGE_RAW              | R  | ADC  | 原始输入电压   |
| 0x1A    | INPUT_CURRENT_RAW              | R  | ADC  | 原始输入电流   |
| 0x1B    | OUTPUT_VOLTAGE_RAW             | R  | ADC  | 原始输出电压   |
| 0x1C    | OUTPUT_CURRENT_RAW             | R  | ADC  | 原始输出电流   |
| 0x1D    | OTP_VALUE                      | R  | m℃   | 当前OTP值   |
| 0x1E    | OTP_SET_VALUE                  | RW | m℃   | OTP设定值   |
| 0x1F    | OVP_VALUE                      | R  | mV   | 当前OVP值   |
| 0x20    | OVP_SET_VALUE                  | RW | mV   | OVP设定值   |
| 0x21    | OCP_VALUE                      | R  | mA   | 当前OCP值   |
| 0x22    | OCP_SET_VALUE                  | RW | mA   | OCP设定值   |
| 0x23    | DUTY_CMD                       | RW | ‰    | 占空比命令    |
| 0x24    | PWM_A_COMPARE                  | R  | Tick | PWM_A比较值 |
| 0x25    | PWM_D_COMPARE                  | R  | Tick | PWM_D比较值 |
| 0x26    | FAN_SPEED                      | R  | RPM  | 风扇转速     |
| 0x27    | FAN_SET_VALUE                  | RW | %    | 风扇设定值    |
| 0x29    | LOOP_CURRENT_FEEDBACK          | R  | ADC  | 电流反馈     |
| 0x2A    | LOOP_CURRENT_REFERENCE         | R  | ADC  | 电流参考     |
| 0x2B    | VOLTAGE_LOOP_CURRENT_REFERENCE | R  | ADC  | 电压环参考    |

---

# 15. 协议特点

| 特性          | 支持 |
|-------------|----|
| CRC校验       | ✓  |
| ACK机制       | ✓  |
| 错误响应        | ✓  |
| 请求响应分离      | ✓  |
| 批量读写        | ✓  |
| 流模式         | ✓  |
| 固定长度解析      | ✓  |
| STM32状态机友好  | ✓  |
| USB CDC     | ✓  |
| RS485       | ✓  |
| TCP透传       | ✓  |
| WebSocket透传 | ✓  |