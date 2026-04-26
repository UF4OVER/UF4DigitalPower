# TVLCOM STM32 / C 版本使用说明

这个目录提供了与 Python 版本 **字节级兼容** 的 STM32 / C 实现。

对应关系如下：

- `stm32/Inc/tvlcom.h`：对外 API 头文件
- `stm32/Src/tvlcom.c`：协议核心实现
- `stm32/Src/tvlcom_stm32_hal_example.c`：基于 STM32 HAL UART 的接收/回发示例
- `stm32/tests/test_tvlcom.c`：宿主机自测程序，可先在 PC 上验证协议行为

---

## 1. 协议保持不变

C 版与 Python 版使用完全相同的协议格式：

### 帧格式

```text
SOF(2) + Length(2, little-endian) + CMD(1) + SEQ(1) + Payload(N) + CRC16(2, little-endian)
```

- `SOF = AA 55`
- `Length = CMD + SEQ + Payload` 的长度
- `CRC16`：初值 `0xFFFF`，多项式 `0xA001`
- 保留控制命令：`TVLCOM_CMD_ACK = 0x00`、`TVLCOM_CMD_NACK = 0xFF`

### TLV 格式

```text
Type(1) + Length(2, little-endian) + Value(N)
```

内置类型：

- `TVLCOM_TYPE_U8   = 0x01`
- `TVLCOM_TYPE_U16  = 0x02`
- `TVLCOM_TYPE_U32  = 0x03`
- `TVLCOM_TYPE_FLOAT= 0x10`
- `TVLCOM_TYPE_STRING = 0x20`

---

## 2. 适合 STM32 工程的放置方式

通常直接复制到 CubeMX 工程：

```text
Core/
├─ Inc/
│  └─ tvlcom.h
└─ Src/
   ├─ tvlcom.c
   └─ tvlcom_stm32_hal_example.c   # 可选
```

如果你不想要 HAL 示例，只放：

- `tvlcom.h`
- `tvlcom.c`

即可。

---

## 3. 可配置项

在包含 `tvlcom.h` 之前，可以按项目资源情况修改：

```c
#define TVLCOM_MAX_PAYLOAD_SIZE 256U
#define TVLCOM_MAX_HANDLERS 16U
#include "tvlcom.h"
```

说明：

- `TVLCOM_MAX_PAYLOAD_SIZE`：单帧最大载荷长度
- `TVLCOM_MAX_FRAME_SIZE = TVLCOM_MAX_PAYLOAD_SIZE + 8`
- `TVLCOM_MAX_HANDLERS`：命令回调表大小

---

## 4. 最小发送示例

```c
#include "tvlcom.h"

uint8_t payload[TVLCOM_MAX_PAYLOAD_SIZE];
uint8_t frame[TVLCOM_MAX_FRAME_SIZE];
uint16_t payload_len = 0;
uint16_t frame_len = 0;

void send_test(void)
{
    tvlcom_payload_add_u16(payload,
                           sizeof(payload),
                           &payload_len,
                           TVLCOM_TYPE_U16,
                           1250U);

    tvlcom_payload_add_float(payload,
                             sizeof(payload),
                             &payload_len,
                             TVLCOM_TYPE_FLOAT,
                             1.23f);

    tvlcom_frame_build(0x01U,
                       0x01U,
                       payload,
                       payload_len,
                       frame,
                       sizeof(frame),
                       &frame_len);

    // HAL_UART_Transmit(&huart1, frame, frame_len, 100);
}
```

生成结果与 Python 示例一致：

```text
AA 55 0E 00 01 01 02 02 00 E2 04 10 04 00 A4 70 9D 3F E0 7E
```

---

## 5. 最小接收示例

```c
#include "tvlcom.h"

tvlcom_parser_t parser;
tvlcom_frame_t frames[4];
uint8_t frame_count;

void app_init(void)
{
    tvlcom_parser_init(&parser);
}

void on_uart_bytes(uint8_t *rx, uint16_t rx_len)
{
    uint8_t i;

    tvlcom_parser_input(&parser,
                        rx,
                        rx_len,
                        frames,
                        4U,
                        &frame_count);

    for (i = 0; i < frame_count; ++i)
    {
        uint16_t voltage = 0;
        float current = 0.0f;

        tvlcom_payload_get_u16(frames[i].payload,
                               frames[i].payload_len,
                               TVLCOM_TYPE_U16,
                               &voltage);

        tvlcom_payload_get_float(frames[i].payload,
                                 frames[i].payload_len,
                                 TVLCOM_TYPE_FLOAT,
                                 &current);

        // 这里处理业务
    }
}
```

特性和 Python 版一致：

- 支持整帧输入
- 支持分包输入
- 支持粘包输入
- 支持前导脏数据自动丢弃
- CRC 错误帧自动丢弃

---

## 6. 命令分发示例

```c
#include "tvlcom.h"

static tvlcom_dispatcher_t dispatcher;

static void handle_ack(uint8_t cmd,
                       uint8_t seq,
                       const uint8_t *payload,
                       uint16_t payload_len,
                       void *user_ctx)
{
    (void)cmd;
    (void)seq;
    (void)payload;
    (void)payload_len;
    (void)user_ctx;

    // 仅当收到 TVLCOM_CMD_ACK(0x00) 时触发
}

static void handle_nack(uint8_t cmd,
                        uint8_t seq,
                        const uint8_t *payload,
                        uint16_t payload_len,
                        void *user_ctx)
{
    (void)cmd;
    (void)seq;
    (void)payload;
    (void)payload_len;
    (void)user_ctx;

    // 仅当收到 TVLCOM_CMD_NACK(0xFF) 时触发
}

static void handle_cmd_test(uint8_t seq,
                            const uint8_t *payload,
                            uint16_t payload_len,
                            void *user_ctx)
{
    uint16_t voltage = 0;
    float current = 0.0f;

    (void)user_ctx;
    tvlcom_payload_get_u16(payload, payload_len, TVLCOM_TYPE_U16, &voltage);
    tvlcom_payload_get_float(payload, payload_len, TVLCOM_TYPE_FLOAT, &current);

    // 用户自己的业务处理
}

void app_dispatch_init(void)
{
    tvlcom_dispatcher_init(&dispatcher);
    tvlcom_dispatcher_set_ack_handler(&dispatcher, handle_ack, NULL);    // 可选
    tvlcom_dispatcher_set_nack_handler(&dispatcher, handle_nack, NULL);  // 可选
    tvlcom_dispatcher_register(&dispatcher, 0x01U, handle_cmd_test, NULL);
}

void process_frame(const tvlcom_frame_t *frame)
{
    tvlcom_dispatcher_dispatch(&dispatcher, frame);
}
```

### ACK / NACK 控制命令说明

协议保留了两个**专属控制命令**：

- `TVLCOM_CMD_ACK  = 0x00`
- `TVLCOM_CMD_NACK = 0xFF`

因此 C 版提供了两个可选控制回调：

```c
void tvlcom_dispatcher_set_ack_handler(tvlcom_dispatcher_t *dispatcher,
                                       tvlcom_ack_handler_t ack_handler,
                                       void *user_ctx);

void tvlcom_dispatcher_set_nack_handler(tvlcom_dispatcher_t *dispatcher,
                                        tvlcom_nack_handler_t nack_handler,
                                        void *user_ctx);
```

特性如下：

- `ack_handler == NULL` 时表示关闭 ACK 回调
- `nack_handler == NULL` 时表示关闭 NACK 回调
- 只有收到 `TVLCOM_CMD_ACK` 才会触发 ACK 回调
- 只有收到 `TVLCOM_CMD_NACK` 才会触发 NACK 回调
- 其他命令仍然按 `cmd` 查找普通命令处理函数
- `TVLCOM_CMD_ACK/TVLCOM_CMD_NACK` 属于保留命令，不能注册为普通业务 handler

适合发送端做：

- `SEQ` 配对
- 超时等待释放
- 发送成功确认
- 错误回执处理

---

## 7. 与 STM32 HAL 的集成建议

如果你使用 `HAL_UARTEx_ReceiveToIdle_IT()`：

1. 初始化时启动一次接收
2. 在 `HAL_UARTEx_RxEventCallback()` 中把收到的字节喂给 `tvlcom_parser_input()`
3. 遍历解析出的帧并分发处理
4. 回调末尾重新启动一次接收

仓库中可参考：

- `stm32/Src/tvlcom_stm32_hal_example.c`

启用方式：

```c
#define TVLCOM_USE_STM32_HAL
```

然后把该文件加入工程，并根据你的 `huart1/huart2` 实例调整。

---

## 8. 自定义类型扩展

当前 C 版默认提供了几种常见类型的辅助函数。

如果你要加自定义类型，比如：

- 二进制结构体
- 自定义定点数
- 时间戳
- 数组

可以直接调用：

```c
tvlcom_payload_append_raw(payload,
                          sizeof(payload),
                          &payload_len,
                          custom_type_id,
                          raw_bytes,
                          raw_len);
```

接收时则用：

```c
const uint8_t *value_ptr;
uint16_t value_len;

tvlcom_payload_get_raw(frame.payload,
                       frame.payload_len,
                       custom_type_id,
                       &value_ptr,
                       &value_len);
```

---

## 9. 宿主机验证

在 Windows + MinGW 环境可直接编译测试：

```powershell
gcc -std=c11 -Wall -Wextra -I .\stm32\Inc .\stm32\Src\tvlcom.c .\stm32\tests\test_tvlcom.c -o .\stm32\tests\test_tvlcom.exe
.\stm32\tests\test_tvlcom.exe
```

预期输出：

```text
All STM32/C TVLCOM tests passed.
```

---

## 10. 和 Python 版语义差异

为了更适合 MCU，C 版做了这些调整：

1. **不返回 Python 字典**，改为 TLV 遍历 / 类型读取函数。
2. **增加了错误码**，例如参数错误、格式错误、CRC 错误、缓冲区溢出。
3. **解析时做了边界检查**，避免越界读取。
4. **同一 Type 多次出现时，读取函数默认返回最后一个值**，保持与 Python `Payload.parse()` 最终覆盖语义一致。
5. **保留专属 ACK/NACK 命令**，并提供可选 ACK/NACK 回调；普通业务命令不会误触发这些控制回调。

---

## 11. 推荐集成方式

如果你的 STM32 项目是串口透传场景，建议按下面方式组织：

- 中断 / DMA：只负责把字节交给协议层
- 协议层：只负责组帧、解帧、CRC、TLV 解析
- 业务层：只负责根据 `cmd` 和 TLV 内容做业务处理

这样后续切换：

- UART
- USB CDC
- RS485
- BLE 透传
- TCP

都不需要改协议核心。

