#ifdef TVLCOM_USE_STM32_HAL

#include "tvlcom.h"
#include "usart.h"

#include <string.h>

#define TVLCOM_UART_RX_CHUNK 64U

static tvlcom_parser_t g_tvl_parser;
static tvlcom_dispatcher_t g_tvl_dispatcher;
static uint8_t g_uart_rx_chunk[TVLCOM_UART_RX_CHUNK];

static void tvlcom_send_control(UART_HandleTypeDef *huart, uint8_t cmd, uint8_t seq)
{
    uint8_t tx_frame[TVLCOM_MAX_FRAME_SIZE];
    uint16_t tx_frame_len = 0U;

    if (tvlcom_frame_build(cmd,
                           seq,
                           NULL,
                           0U,
                           tx_frame,
                           sizeof(tx_frame),
                           &tx_frame_len) == TVLCOM_OK)
    {
        (void)HAL_UART_Transmit(huart, tx_frame, tx_frame_len, 100U);
    }
}

static void tvlcom_handle_ack(uint8_t cmd,
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

    /*
     * 可选 ACK 回调：
     * 专属 ACK 命令固定为 TVLCOM_CMD_ACK(0x00)。
     * 可以在这里按 cmd + seq 做配对或释放等待状态。
     */
}

static void tvlcom_handle_nack(uint8_t cmd,
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

    /*
     * 可选 NACK 回调：
     * 专属 NACK 命令固定为 TVLCOM_CMD_NACK(0xFF)。
     */
}

static void tvlcom_handle_test(uint8_t seq,
                               const uint8_t *payload,
                               uint16_t payload_len,
                               void *user_ctx)
{
    float value_f = 0.0f;
    uint16_t value_u16 = 0U;
    UART_HandleTypeDef *huart = (UART_HandleTypeDef *)user_ctx;

    (void)tvlcom_payload_get_u16(payload, payload_len, TVLCOM_TYPE_U16, &value_u16);
    (void)tvlcom_payload_get_float(payload, payload_len, TVLCOM_TYPE_FLOAT, &value_f);

    (void)value_u16;
    (void)value_f;
    tvlcom_send_control(huart, TVLCOM_CMD_ACK, seq);
}

void TVLCOM_AppInit(UART_HandleTypeDef *huart)
{
    tvlcom_parser_init(&g_tvl_parser);
    tvlcom_dispatcher_init(&g_tvl_dispatcher);
    tvlcom_dispatcher_set_ack_handler(&g_tvl_dispatcher, tvlcom_handle_ack, NULL);
    tvlcom_dispatcher_set_nack_handler(&g_tvl_dispatcher, tvlcom_handle_nack, NULL);
    (void)tvlcom_dispatcher_register(&g_tvl_dispatcher,
                                     0x01U,
                                     tvlcom_handle_test,
                                     huart);

    (void)HAL_UARTEx_ReceiveToIdle_IT(huart,
                                      g_uart_rx_chunk,
                                      sizeof(g_uart_rx_chunk));
}

void TVLCOM_SendTest(UART_HandleTypeDef *huart, uint8_t seq)
{
    uint8_t payload[TVLCOM_MAX_PAYLOAD_SIZE];
    uint8_t frame[TVLCOM_MAX_FRAME_SIZE];
    uint16_t payload_len = 0U;
    uint16_t frame_len = 0U;

    (void)tvlcom_payload_add_u16(payload,
                                 sizeof(payload),
                                 &payload_len,
                                 TVLCOM_TYPE_U16,
                                 1250U);
    (void)tvlcom_payload_add_float(payload,
                                   sizeof(payload),
                                   &payload_len,
                                   TVLCOM_TYPE_FLOAT,
                                   1.23f);

    if (tvlcom_frame_build(0x01U,
                           seq,
                           payload,
                           payload_len,
                           frame,
                           sizeof(frame),
                           &frame_len) == TVLCOM_OK)
    {
        (void)HAL_UART_Transmit(huart, frame, frame_len, 100U);
    }
}

void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *huart, uint16_t Size)
{
    tvlcom_frame_t frames[4];
    uint8_t frame_count = 0U;
    uint8_t i;

    if (Size > 0U)
    {
        (void)tvlcom_parser_input(&g_tvl_parser,
                                  g_uart_rx_chunk,
                                  Size,
                                  frames,
                                  4U,
                                  &frame_count);

        for (i = 0U; i < frame_count; ++i)
        {
            if (tvlcom_dispatcher_dispatch(&g_tvl_dispatcher, &frames[i]) == TVLCOM_ERR_NOT_FOUND)
            {
                if ((frames[i].cmd != TVLCOM_CMD_ACK) && (frames[i].cmd != TVLCOM_CMD_NACK))
                {
                    tvlcom_send_control(huart, TVLCOM_CMD_NACK, frames[i].seq);
                }
            }
        }
    }

    (void)HAL_UARTEx_ReceiveToIdle_IT(huart,
                                      g_uart_rx_chunk,
                                      sizeof(g_uart_rx_chunk));
}

#endif

