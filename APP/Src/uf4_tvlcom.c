/**
 * @file    : uf4_tvlcom.c
 * @brief   : USB CDC implementation of the UF4DigitalPower TLV command contract.
 */

#include "uf4_tvlcom.h"

#include "hrtim.h"
#include "uf4_power_main.h"
#include "usbd_cdc_if.h"

#include <stdbool.h>
#include <string.h>

#define TVL_SOF0 0xAAU
#define TVL_SOF1 0x55U
#define TVL_MAX_PAYLOAD 192U
#define TVL_MAX_FRAME (2U + 2U + 1U + 1U + TVL_MAX_PAYLOAD + 2U)
#define TVL_RX_RING_SIZE 512U

typedef enum
{
    TVL_CMD_ACK = 0x00,
    TVL_CMD_READ = 0x01,
    TVL_CMD_WRITE = 0x02,
    TVL_CMD_REPORT = 0x03,
    TVL_CMD_NACK = 0xFF
} tvl_cmd_t;

typedef enum
{
    TVL_TYPE_INPUT_VOLTAGE = 10,
    TVL_TYPE_INPUT_CURRENT = 11,
    TVL_TYPE_OUTPUT_VOLTAGE = 12,
    TVL_TYPE_OUTPUT_CURRENT = 13,
    TVL_TYPE_CORE_TEMPERATURE = 14,
    TVL_TYPE_BOARD_TEMPERATURE = 15,
    TVL_TYPE_SET_VOLTAGE_LIMIT = 17,
    TVL_TYPE_SET_CURRENT_LIMIT = 18,
    TVL_TYPE_CC_CV_MODE = 20,
    TVL_TYPE_POWER_STATE = 21,
    TVL_TYPE_FAULT_STATE = 22,
    TVL_TYPE_STATE_MACHINE_FLAG_BITS = 23,
    TVL_TYPE_STATE_MACHINE_STATE = 24,
    TVL_TYPE_INPUT_VOLTAGE_RAW = 25,
    TVL_TYPE_INPUT_CURRENT_RAW = 26,
    TVL_TYPE_OUTPUT_VOLTAGE_RAW = 27,
    TVL_TYPE_OUTPUT_CURRENT_RAW = 28,
    TVL_TYPE_OTP_VALUE = 29,
    TVL_TYPE_OTP_SET_VALUE = 30,
    TVL_TYPE_OVP_VALUE = 31,
    TVL_TYPE_OVP_SET_VALUE = 32,
    TVL_TYPE_OCP_VALUE = 33,
    TVL_TYPE_OCP_SET_VALUE = 34,
    TVL_TYPE_DUTY_CMD = 35,
    TVL_TYPE_PWM_A_COMPARE = 36,
    TVL_TYPE_PWM_D_COMPARE = 37,
    TVL_TYPE_FAN_SPEED = 38,
    TVL_TYPE_FAN_SET_VALUE = 39,
    TVL_TYPE_DEBUG_SNAPSHOT = 40
} tvl_data_type_t;

extern volatile float MAX_OTP_VAL;
extern volatile float MAX_VOUT_OVP_VAL;
extern volatile float MAX_VOUT_OCP_VAL;
extern volatile _CVCC_Mode CVCC_Mode;

static uint8_t rx_frame[TVL_MAX_FRAME];
static uint8_t rx_ring[TVL_RX_RING_SIZE];
static uint8_t tx_frame[TVL_MAX_FRAME];
static uint16_t rx_index;
static uint16_t rx_expected;
static volatile uint16_t rx_head;
static volatile uint16_t rx_tail;
static uint16_t fan_set_permille;
static uint16_t fan_current_permille;

static uint16_t tvl_crc16(const uint8_t *data, uint16_t len)
{
    uint16_t crc = 0xFFFFU;

    for (uint16_t i = 0; i < len; i++)
    {
        crc ^= data[i];
        for (uint8_t bit = 0; bit < 8; bit++)
        {
            if ((crc & 0x0001U) != 0U)
                crc = (crc >> 1U) ^ 0xA001U;
            else
                crc >>= 1U;
        }
    }

    return crc;
}

static void put_u16(uint8_t *dst, uint16_t value)
{
    dst[0] = (uint8_t)value;
    dst[1] = (uint8_t)(value >> 8U);
}

static void put_u32(uint8_t *dst, uint32_t value)
{
    dst[0] = (uint8_t)value;
    dst[1] = (uint8_t)(value >> 8U);
    dst[2] = (uint8_t)(value >> 16U);
    dst[3] = (uint8_t)(value >> 24U);
}

static uint16_t get_u16(const uint8_t *src)
{
    return (uint16_t)src[0] | ((uint16_t)src[1] << 8U);
}

static uint32_t get_u32(const uint8_t *src)
{
    return (uint32_t)src[0] | ((uint32_t)src[1] << 8U) | ((uint32_t)src[2] << 16U) | ((uint32_t)src[3] << 24U);
}

static bool append_tlv(uint8_t *payload, uint16_t *offset, uint8_t type, const void *value, uint16_t len)
{
    if ((*offset + 3U + len) > TVL_MAX_PAYLOAD)
        return false;

    payload[(*offset)++] = type;
    put_u16(&payload[*offset], len);
    *offset += 2U;
    if (len > 0U)
    {
        memcpy(&payload[*offset], value, len);
        *offset += len;
    }

    return true;
}

static bool append_u8(uint8_t *payload, uint16_t *offset, uint8_t type, uint8_t value)
{
    return append_tlv(payload, offset, type, &value, 1U);
}

static bool append_u32(uint8_t *payload, uint16_t *offset, uint8_t type, uint32_t value)
{
    uint8_t bytes[4];
    put_u32(bytes, value);
    return append_tlv(payload, offset, type, bytes, sizeof(bytes));
}

static uint32_t non_negative_milli(float value)
{
    int32_t milli = UF4_FloatToMilli(value);
    if (milli < 0)
        milli = 0;
    return (uint32_t)milli;
}

static uint8_t state_bits(void)
{
    switch (DF.SMFlag)
    {
    case Init:
        return 0x01U;
    case Wait:
        return 0x02U;
    case Rise:
        return 0x04U;
    case Run:
        return 0x08U;
    case Err:
        return 0x0FU;
    default:
        return 0U;
    }
}

static uint32_t fan_to_permille(void)
{
    return fan_current_permille;
}

static bool read_data(uint8_t type, uint8_t *payload, uint16_t *offset)
{
    switch ((tvl_data_type_t)type)
    {
    case TVL_TYPE_INPUT_VOLTAGE:
        return append_u32(payload, offset, type, (uint32_t)UF4_FloatToMilli(VIN));
    case TVL_TYPE_INPUT_CURRENT:
        return append_u32(payload, offset, type, non_negative_milli(IIN));
    case TVL_TYPE_OUTPUT_VOLTAGE:
        return append_u32(payload, offset, type, (uint32_t)UF4_FloatToMilli(VOUT));
    case TVL_TYPE_OUTPUT_CURRENT:
        return append_u32(payload, offset, type, non_negative_milli(IOUT));
    case TVL_TYPE_CORE_TEMPERATURE:
        return append_u32(payload, offset, type, (uint32_t)UF4_FloatToMilli(CPU_TEMP));
    case TVL_TYPE_BOARD_TEMPERATURE:
        return append_u32(payload, offset, type, (uint32_t)UF4_FloatToMilli(MainBoard_TEMP));
    case TVL_TYPE_SET_VOLTAGE_LIMIT:
        return append_u32(payload, offset, type, (uint32_t)UF4_FloatToMilli(SET_Value.Vout));
    case TVL_TYPE_SET_CURRENT_LIMIT:
        return append_u32(payload, offset, type, (uint32_t)UF4_FloatToMilli(SET_Value.Iout));
    case TVL_TYPE_CC_CV_MODE:
        if ((DF.OUTPUT_Flag == 0U) || (DF.SMFlag != Run))
            return append_u8(payload, offset, type, 1U);
        return append_u8(payload, offset, type, (CVCC_Mode == CC) ? 0U : 1U);
    case TVL_TYPE_POWER_STATE:
        return append_u8(payload, offset, type, DF.OUTPUT_Flag);
    case TVL_TYPE_FAULT_STATE:
        return append_u32(payload, offset, type, DF.ErrFlag);
    case TVL_TYPE_STATE_MACHINE_FLAG_BITS:
        return append_u8(payload, offset, type, state_bits());
    case TVL_TYPE_STATE_MACHINE_STATE:
        return append_u8(payload, offset, type, DF.BBFlag);
    case TVL_TYPE_INPUT_VOLTAGE_RAW:
        return append_u32(payload, offset, type, ADC1_RESULT[0]);
    case TVL_TYPE_INPUT_CURRENT_RAW:
        return append_u32(payload, offset, type, ADC1_RESULT[1]);
    case TVL_TYPE_OUTPUT_VOLTAGE_RAW:
        return append_u32(payload, offset, type, ADC1_RESULT[2]);
    case TVL_TYPE_OUTPUT_CURRENT_RAW:
        return append_u32(payload, offset, type, ADC1_RESULT[3]);
    case TVL_TYPE_OTP_VALUE:
    case TVL_TYPE_OTP_SET_VALUE:
        return append_u32(payload, offset, type, (uint32_t)UF4_FloatToMilli(MAX_OTP_VAL));
    case TVL_TYPE_OVP_VALUE:
    case TVL_TYPE_OVP_SET_VALUE:
        return append_u32(payload, offset, type, (uint32_t)UF4_FloatToMilli(MAX_VOUT_OVP_VAL));
    case TVL_TYPE_OCP_VALUE:
    case TVL_TYPE_OCP_SET_VALUE:
        return append_u32(payload, offset, type, (uint32_t)UF4_FloatToMilli(MAX_VOUT_OCP_VAL));
    case TVL_TYPE_DUTY_CMD:
        return append_u32(payload, offset, type, (uint32_t)CtrValue.BuckDuty);
    case TVL_TYPE_PWM_A_COMPARE:
        return append_u32(payload, offset, type, (uint32_t)__HAL_HRTIM_GETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_1));
    case TVL_TYPE_PWM_D_COMPARE:
        return append_u32(payload, offset, type, (uint32_t)__HAL_HRTIM_GETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_D, HRTIM_COMPAREUNIT_1));
    case TVL_TYPE_FAN_SPEED:
        return append_u32(payload, offset, type, fan_to_permille());
    case TVL_TYPE_FAN_SET_VALUE:
        return append_u32(payload, offset, type, fan_set_permille);
    case TVL_TYPE_DEBUG_SNAPSHOT:
        return read_data(TVL_TYPE_OUTPUT_VOLTAGE_RAW, payload, offset) &&
               read_data(TVL_TYPE_OUTPUT_VOLTAGE, payload, offset) &&
               read_data(TVL_TYPE_OVP_SET_VALUE, payload, offset);
    default:
        return false;
    }
}

static float milli_to_float(uint32_t milli)
{
    return (float)((int32_t)milli) / 1000.0F;
}

static void clamp_settings(void)
{
    if (SET_Value.Vout < MIN_OUTPUT_VOLTAGE)
        SET_Value.Vout = MIN_OUTPUT_VOLTAGE;
    if (SET_Value.Vout > MAX_OUTPUT_VOLTAGE)
        SET_Value.Vout = MAX_OUTPUT_VOLTAGE;
    if (SET_Value.Iout < 0.0F)
        SET_Value.Iout = 0.0F;
    if (SET_Value.Iout > MAX_OUTPUT_CURRENT)
        SET_Value.Iout = MAX_OUTPUT_CURRENT;
}

static bool write_data(uint8_t type, const uint8_t *value, uint16_t len, bool *output_settings_changed)
{
    float next_value;

    switch ((tvl_data_type_t)type)
    {
    case TVL_TYPE_SET_VOLTAGE_LIMIT:
        if (len != 4U)
            return false;
        next_value = milli_to_float(get_u32(value));
        if (next_value < MIN_OUTPUT_VOLTAGE)
            next_value = MIN_OUTPUT_VOLTAGE;
        if (next_value > MAX_OUTPUT_VOLTAGE)
            next_value = MAX_OUTPUT_VOLTAGE;
        if ((next_value - SET_Value.Vout > 0.001F) || (SET_Value.Vout - next_value > 0.001F))
            *output_settings_changed = true;
        SET_Value.Vout = next_value;
        clamp_settings();
        SET_Value.SET_modified_flag = 1;
        return true;
    case TVL_TYPE_SET_CURRENT_LIMIT:
        if (len != 4U)
            return false;
        next_value = milli_to_float(get_u32(value));
        if (next_value < 0.0F)
            next_value = 0.0F;
        if (next_value > MAX_OUTPUT_CURRENT)
            next_value = MAX_OUTPUT_CURRENT;
        if ((next_value - SET_Value.Iout > 0.001F) || (SET_Value.Iout - next_value > 0.001F))
            *output_settings_changed = true;
        SET_Value.Iout = next_value;
        clamp_settings();
        SET_Value.SET_modified_flag = 1;
        return true;
    case TVL_TYPE_POWER_STATE:
        if (len != 1U)
            return false;
        {
            const uint8_t requested = (value[0] != 0U) ? 1U : 0U;
            if (requested != DF.OUTPUT_Flag)
                UF4_PowerSetOutputEnabled(requested);
        }
        return true;
    case TVL_TYPE_OTP_SET_VALUE:
        if (len != 4U)
            return false;
        MAX_OTP_VAL = milli_to_float(get_u32(value));
        SET_Value.SET_modified_flag = 1;
        return true;
    case TVL_TYPE_OVP_SET_VALUE:
        if (len != 4U)
            return false;
        MAX_VOUT_OVP_VAL = milli_to_float(get_u32(value));
        SET_Value.SET_modified_flag = 1;
        return true;
    case TVL_TYPE_OCP_SET_VALUE:
        if (len != 4U)
            return false;
        MAX_VOUT_OCP_VAL = milli_to_float(get_u32(value));
        SET_Value.SET_modified_flag = 1;
        return true;
    case TVL_TYPE_FAN_SET_VALUE:
        if (len != 4U)
            return false;
        fan_set_permille = (uint16_t)get_u32(value);
        if (fan_set_permille > 1000U)
            fan_set_permille = 1000U;
        FAN_PWM_set(fan_set_permille / 10U);
        fan_current_permille = fan_set_permille;
        return true;
    default:
        return false;
    }
}

static void send_frame(uint8_t cmd, uint8_t seq, const uint8_t *payload, uint16_t payload_len)
{
    const uint16_t len = (uint16_t)(2U + payload_len);
    uint16_t pos = 0;

    tx_frame[pos++] = TVL_SOF0;
    tx_frame[pos++] = TVL_SOF1;
    put_u16(&tx_frame[pos], len);
    pos += 2U;
    tx_frame[pos++] = cmd;
    tx_frame[pos++] = seq;
    if (payload_len > 0U)
    {
        memcpy(&tx_frame[pos], payload, payload_len);
        pos += payload_len;
    }

    const uint16_t crc = tvl_crc16(tx_frame, pos);
    put_u16(&tx_frame[pos], crc);
    pos += 2U;

    for (uint32_t retry = 0; retry < 1000U; retry++)
    {
        if (CDC_Transmit_FS(tx_frame, pos) == USBD_OK)
            break;
    }
}

static void send_nack(uint8_t seq)
{
    send_frame(TVL_CMD_NACK, seq, NULL, 0U);
}

static void handle_read(uint8_t seq, const uint8_t *payload, uint16_t payload_len)
{
    uint8_t response[TVL_MAX_PAYLOAD];
    uint16_t response_len = 0;
    uint16_t pos = 0;

    while (pos < payload_len)
    {
        if ((payload_len - pos) < 3U)
        {
            send_nack(seq);
            return;
        }

        const uint8_t type = payload[pos++];
        const uint16_t len = get_u16(&payload[pos]);
        pos += 2U;
        if (len != 0U || !read_data(type, response, &response_len))
        {
            send_nack(seq);
            return;
        }
    }

    send_frame(TVL_CMD_ACK, seq, response, response_len);
}

static void handle_write(uint8_t seq, const uint8_t *payload, uint16_t payload_len)
{
    uint16_t pos = 0;
    bool output_settings_changed = false;

    while (pos < payload_len)
    {
        if ((payload_len - pos) < 3U)
        {
            send_nack(seq);
            return;
        }

        const uint8_t type = payload[pos++];
        const uint16_t len = get_u16(&payload[pos]);
        pos += 2U;

        if ((payload_len - pos) < len || !write_data(type, &payload[pos], len, &output_settings_changed))
        {
            send_nack(seq);
            return;
        }
        pos += len;
    }

    if (output_settings_changed)
    {
        UF4_PowerApplySetpoints();
    }

    send_frame(TVL_CMD_ACK, seq, NULL, 0U);
}

static void handle_report(uint8_t seq)
{
    static const uint8_t report_types[] = {
        TVL_TYPE_INPUT_VOLTAGE,
        TVL_TYPE_INPUT_CURRENT,
        TVL_TYPE_OUTPUT_VOLTAGE,
        TVL_TYPE_OUTPUT_CURRENT,
        TVL_TYPE_CORE_TEMPERATURE,
        TVL_TYPE_BOARD_TEMPERATURE,
        TVL_TYPE_SET_VOLTAGE_LIMIT,
        TVL_TYPE_SET_CURRENT_LIMIT,
        TVL_TYPE_CC_CV_MODE,
        TVL_TYPE_POWER_STATE,
        TVL_TYPE_FAULT_STATE,
        TVL_TYPE_STATE_MACHINE_FLAG_BITS,
        TVL_TYPE_STATE_MACHINE_STATE,
        TVL_TYPE_OTP_VALUE,
        TVL_TYPE_OTP_SET_VALUE,
        TVL_TYPE_OVP_VALUE,
        TVL_TYPE_OVP_SET_VALUE,
        TVL_TYPE_OCP_VALUE,
        TVL_TYPE_OCP_SET_VALUE,
        TVL_TYPE_DUTY_CMD,
        TVL_TYPE_PWM_A_COMPARE,
        TVL_TYPE_PWM_D_COMPARE,
        TVL_TYPE_FAN_SPEED,
        TVL_TYPE_FAN_SET_VALUE,
    };
    uint8_t response[TVL_MAX_PAYLOAD];
    uint16_t response_len = 0;

    for (uint16_t i = 0; i < (sizeof(report_types) / sizeof(report_types[0])); i++)
    {
        if (!read_data(report_types[i], response, &response_len))
        {
            send_nack(seq);
            return;
        }
    }

    send_frame(TVL_CMD_REPORT, seq, response, response_len);
}

static void handle_frame(const uint8_t *frame, uint16_t frame_len)
{
    uint8_t seq = 0U;

    if (frame_len >= 6U)
        seq = frame[5];

    if (frame_len < 8U)
    {
        send_nack(seq);
        return;
    }

    const uint16_t body_len = get_u16(&frame[2]);

    if (body_len < 2U || body_len > (TVL_MAX_PAYLOAD + 2U) || frame_len < (uint16_t)(4U + body_len + 2U))
    {
        send_nack(seq);
        return;
    }

    const uint16_t received_crc = get_u16(&frame[4U + body_len]);
    const uint16_t actual_crc = tvl_crc16(frame, (uint16_t)(4U + body_len));

    if (received_crc != actual_crc)
    {
        send_nack(seq);
        return;
    }

    const uint8_t cmd = frame[4];
    const uint8_t *payload = &frame[6];
    const uint16_t payload_len = (uint16_t)(body_len - 2U);

    switch ((tvl_cmd_t)cmd)
    {
    case TVL_CMD_READ:
        handle_read(seq, payload, payload_len);
        break;
    case TVL_CMD_WRITE:
        handle_write(seq, payload, payload_len);
        break;
    case TVL_CMD_REPORT:
        if (payload_len == 0U)
            handle_report(seq);
        else
            send_nack(seq);
        break;
    default:
        send_nack(seq);
        break;
    }
}

void UF4_TvlcomInit(void)
{
    rx_index = 0;
    rx_expected = 0;
    rx_head = 0;
    rx_tail = 0;
    fan_set_permille = 0;
    fan_current_permille = 0;
}

void UF4_TvlcomFeed(const uint8_t *data, uint16_t len)
{
    for (uint16_t i = 0; i < len; i++)
    {
        const uint16_t next = (uint16_t)((rx_head + 1U) % TVL_RX_RING_SIZE);
        if (next == rx_tail)
            break;
        rx_ring[rx_head] = data[i];
        rx_head = next;
    }
}

void UF4_TvlcomProcess(void)
{
    while (rx_tail != rx_head)
    {
        const uint8_t byte = rx_ring[rx_tail];
        rx_tail = (uint16_t)((rx_tail + 1U) % TVL_RX_RING_SIZE);

        if (rx_index == 0U && byte != TVL_SOF0)
            continue;
        if (rx_index == 1U && byte != TVL_SOF1)
        {
            rx_index = 0;
            continue;
        }

        rx_frame[rx_index++] = byte;

        if (rx_index == 4U)
        {
            const uint16_t body_len = get_u16(&rx_frame[2]);
            if (body_len < 2U || body_len > (TVL_MAX_PAYLOAD + 2U))
            {
                rx_index = 0;
                rx_expected = 0;
                continue;
            }
            rx_expected = (uint16_t)(4U + body_len + 2U);
        }

        if (rx_expected != 0U && rx_index >= rx_expected)
        {
            handle_frame(rx_frame, rx_expected);
            rx_index = 0;
            rx_expected = 0;
        }

        if (rx_index >= TVL_MAX_FRAME)
        {
            rx_index = 0;
            rx_expected = 0;
        }
    }
}
