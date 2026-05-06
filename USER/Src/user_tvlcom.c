#include "../Inc/user_tvlcom.h"

#include "../Inc/user_power.h"
#include "tvlcom.h"
#include "usbd_cdc_if.h"

#include <string.h>

#define USER_TVL_REPORT_INTERVAL_MS 500U

const user_tvl_data_descriptor_t g_user_tvl_data_descriptors[] = {
    {USER_TVL_INPUT_VOLTAGE, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ, "mV"},
    {USER_TVL_INPUT_CURRENT, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ, "mA"},
    {USER_TVL_OUTPUT_VOLTAGE, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ, "mV"},
    {USER_TVL_OUTPUT_CURRENT, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ, "mA"},
    {USER_TVL_CORE_TEMPERATURE, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ, "mC"},
    {USER_TVL_BOARD_TEMPERATURE, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ, "mC"},
    {USER_TVL_SET_VOLTAGE_LIMIT, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ_WRITE, "mV"},
    {USER_TVL_SET_CURRENT_LIMIT, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ_WRITE, "mA"},
    {USER_TVL_CC_CV_MODE, USER_TVL_VALUE_U8, USER_TVL_ACCESS_READ, "enum"},
    {USER_TVL_POWER_STATE, USER_TVL_VALUE_U8, USER_TVL_ACCESS_READ_WRITE, "bool"},
    {USER_TVL_FAULT_STATE, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ, "bitmask"},
    {USER_TVL_STATE_MACHINE_FLAG_BITS, USER_TVL_VALUE_U8, USER_TVL_ACCESS_READ, "bitmask"},
    {USER_TVL_STATE_MACHINE_STATE, USER_TVL_VALUE_U8, USER_TVL_ACCESS_READ, "enum"},
    {USER_TVL_INPUT_VOLTAGE_RAW, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ, "adc"},
    {USER_TVL_INPUT_CURRENT_RAW, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ, "adc"},
    {USER_TVL_OUTPUT_VOLTAGE_RAW, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ, "adc"},
    {USER_TVL_OUTPUT_CURRENT_RAW, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ, "adc"},
    {USER_TVL_OTP_VALUE, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ, "mC"},
    {USER_TVL_OTP_SET_VALUE, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ_WRITE, "mC"},
    {USER_TVL_OVP_VALUE, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ, "mV"},
    {USER_TVL_OVP_SET_VALUE, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ_WRITE, "mV"},
    {USER_TVL_OCP_VALUE, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ, "mA"},
    {USER_TVL_OCP_SET_VALUE, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ_WRITE, "mA"},
    {USER_TVL_FAN_SPEED, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ, "permille"},
    {USER_TVL_FAN_SET_VALUE, USER_TVL_VALUE_U32, USER_TVL_ACCESS_READ_WRITE, "permille"}};

const uint8_t g_user_tvl_data_descriptor_count =
    (uint8_t)(sizeof(g_user_tvl_data_descriptors) / sizeof(g_user_tvl_data_descriptors[0]));

static tvlcom_parser_t g_parser;
static volatile uint8_t g_report_pending = 0U;
static uint16_t g_report_ticks = 0U;
static uint32_t g_next_report_tick = 0U;
static uint8_t g_report_frame[TVLCOM_MAX_FRAME_SIZE];
static uint16_t g_report_frame_len = 0U;
static volatile uint8_t g_report_frame_pending = 0U;

static uint8_t user_tvlcom_send(uint8_t cmd, uint8_t seq, const uint8_t *payload, uint16_t payload_len)
{
    uint8_t frame[TVLCOM_MAX_FRAME_SIZE];
    uint16_t frame_len = 0U;
    uint32_t timeout;
    uint8_t result;

    if (tvlcom_frame_build(cmd, seq, payload, payload_len, frame, sizeof(frame), &frame_len) != TVLCOM_OK)
    {
        return 0U;
    }

    timeout = HAL_GetTick() + 20U;
    do
    {
        result = CDC_Transmit_FS(frame, frame_len);
        if (result == USBD_OK)
        {
            return 1U;
        }
        if (result != USBD_BUSY)
        {
            return 0U;
        }
    } while (HAL_GetTick() < timeout);

    return 0U;
}

static void user_tvlcom_send_nack(uint8_t seq)
{
    user_tvlcom_send(USER_TVL_CMD_NACK, seq, NULL, 0U);
}

static const user_tvl_data_descriptor_t *user_tvlcom_descriptor(uint8_t type)
{
    uint8_t index;

    for (index = 0U; index < g_user_tvl_data_descriptor_count; ++index)
    {
        if ((uint8_t)g_user_tvl_data_descriptors[index].type == type)
        {
            return &g_user_tvl_data_descriptors[index];
        }
    }

    return NULL;
}

static uint8_t user_tvlcom_state_bits(user_power_state_t state)
{
    switch (state)
    {
    case USER_POWER_STATE_INIT:
        return 0x01U;
    case USER_POWER_STATE_WAIT:
        return 0x02U;
    case USER_POWER_STATE_RISE:
        return 0x04U;
    case USER_POWER_STATE_RUN:
        return 0x08U;
    case USER_POWER_STATE_ERR:
        return 0x0FU;
    default:
        return 0U;
    }
}

static uint32_t user_tvlcom_float_to_mv(float value)
{
    if (value <= 0.0F)
    {
        return 0U;
    }
    return (uint32_t)(value * 1000.0F + 0.5F);
}

static int32_t user_tvlcom_float_to_ma(float value)
{
    value = value < 0.0F ? 0.0F : value;
    return (int32_t)(value * 1000.0F + 0.5F);
}

static uint32_t user_tvlcom_float_to_mc(float value)
{
    return (uint32_t)(value * 1000.0F + 0.5F);
}

static tvlcom_status_t user_tvlcom_append_type(uint8_t *payload,
                                               uint16_t *payload_len,
                                               uint8_t type,
                                               const user_power_status_t *status,
                                               const user_power_config_t *config)
{
    switch (type)
    {
    case USER_TVL_DEBUG_SNAPSHOT:
        if (tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, USER_TVL_OUTPUT_VOLTAGE_RAW, status->raw_adc[2]) != TVLCOM_OK)
        {
            return TVLCOM_ERR_OVERFLOW;
        }
        if (tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, USER_TVL_OUTPUT_VOLTAGE, user_tvlcom_float_to_mv(status->vout_v)) != TVLCOM_OK)
        {
            return TVLCOM_ERR_OVERFLOW;
        }
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, USER_TVL_OVP_SET_VALUE, user_tvlcom_float_to_mv(config->ovp_v));
    case USER_TVL_INPUT_VOLTAGE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, user_tvlcom_float_to_mv(status->vin_v));
    case USER_TVL_INPUT_CURRENT:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, (uint32_t)user_tvlcom_float_to_ma(status->iin_a));
    case USER_TVL_OUTPUT_VOLTAGE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, user_tvlcom_float_to_mv(status->vout_v));
    case USER_TVL_OUTPUT_CURRENT:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, (uint32_t)user_tvlcom_float_to_ma(status->iout_a));
    case USER_TVL_CORE_TEMPERATURE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, user_tvlcom_float_to_mc(status->core_temp_c));
    case USER_TVL_BOARD_TEMPERATURE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, user_tvlcom_float_to_mc(status->board_temp_c));
    case USER_TVL_SET_VOLTAGE_LIMIT:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, user_tvlcom_float_to_mv(config->target_voltage_v));
    case USER_TVL_SET_CURRENT_LIMIT:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, (uint32_t)user_tvlcom_float_to_ma(config->target_current_a));
    case USER_TVL_CC_CV_MODE:
        return tvlcom_payload_add_u8(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, (uint8_t)status->regulation_mode);
    case USER_TVL_POWER_STATE:
        return tvlcom_payload_add_u8(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, config->power_enabled);
    case USER_TVL_FAULT_STATE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, status->fault_mask);
    case USER_TVL_STATE_MACHINE_FLAG_BITS:
        return tvlcom_payload_add_u8(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, user_tvlcom_state_bits(status->state));
    case USER_TVL_STATE_MACHINE_STATE:
        return tvlcom_payload_add_u8(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, (uint8_t)status->topology);
    case USER_TVL_INPUT_VOLTAGE_RAW:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, status->raw_adc[0]);
    case USER_TVL_INPUT_CURRENT_RAW:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, status->raw_adc[1]);
    case USER_TVL_OUTPUT_VOLTAGE_RAW:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, status->raw_adc[2]);
    case USER_TVL_OUTPUT_CURRENT_RAW:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, status->raw_adc[3]);
    case USER_TVL_OTP_VALUE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, user_tvlcom_float_to_mc(status->board_temp_c));
    case USER_TVL_OTP_SET_VALUE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, user_tvlcom_float_to_mc(config->otp_c));
    case USER_TVL_OVP_VALUE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, user_tvlcom_float_to_mv(status->vout_v));
    case USER_TVL_OVP_SET_VALUE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, user_tvlcom_float_to_mv(config->ovp_v));
    case USER_TVL_OCP_VALUE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, (uint32_t)user_tvlcom_float_to_ma(status->iout_a));
    case USER_TVL_OCP_SET_VALUE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, (uint32_t)user_tvlcom_float_to_ma(config->ocp_a));
    case USER_TVL_FAN_SPEED:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, status->fan_speed);
    case USER_TVL_FAN_SET_VALUE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, config->fan_set_value);
    default:
        return TVLCOM_ERR_NOT_FOUND;
    }
}

static tvlcom_status_t user_tvlcom_append_report_payload(uint8_t *payload, uint16_t *payload_len)
{
    static const uint8_t report_types[] = {
        USER_TVL_INPUT_VOLTAGE,
        USER_TVL_INPUT_CURRENT,
        USER_TVL_OUTPUT_VOLTAGE,
        USER_TVL_OUTPUT_CURRENT,
        USER_TVL_CORE_TEMPERATURE,
        USER_TVL_BOARD_TEMPERATURE,
        USER_TVL_CC_CV_MODE,
        USER_TVL_FAULT_STATE,
        USER_TVL_STATE_MACHINE_FLAG_BITS,
        USER_TVL_STATE_MACHINE_STATE,
        USER_TVL_FAN_SPEED};
    user_power_status_t status;
    user_power_config_t config;
    uint8_t index;
    tvlcom_status_t status_code;

    UserPower_GetStatus(&status);
    UserPower_GetConfig(&config);

    for (index = 0U; index < (uint8_t)(sizeof(report_types) / sizeof(report_types[0])); ++index)
    {
        status_code = user_tvlcom_append_type(payload, payload_len, report_types[index], &status, &config);
        if (status_code != TVLCOM_OK)
        {
            return status_code;
        }
    }

    return TVLCOM_OK;
}

static void user_tvlcom_handle_read(uint8_t seq, const uint8_t *payload, uint16_t payload_len)
{
    user_power_status_t status;
    user_power_config_t config;
    tvlcom_tlv_t tlv;
    uint16_t offset = 0U;
    uint8_t ack_payload[TVLCOM_MAX_PAYLOAD_SIZE];
    uint16_t ack_len = 0U;

    UserPower_GetStatus(&status);
    if ((status.state == USER_POWER_STATE_INIT) || (status.state == USER_POWER_STATE_WAIT))
    {
        UserPower_5msTask();
        UserPower_GetStatus(&status);
    }
    UserPower_GetConfig(&config);

    while (tvlcom_payload_next(payload, payload_len, &offset, &tlv) == TVLCOM_OK)
    {
        if (user_tvlcom_append_type(ack_payload, &ack_len, tlv.type, &status, &config) != TVLCOM_OK)
        {
            user_tvlcom_send_nack(seq);
            return;
        }
    }

    user_tvlcom_send(USER_TVL_CMD_ACK, seq, ack_payload, ack_len);
}

static void user_tvlcom_handle_write(uint8_t seq, const uint8_t *payload, uint16_t payload_len)
{
    tvlcom_tlv_t tlv;
    uint16_t offset = 0U;
    uint32_t value_u32 = 0U;

    while (tvlcom_payload_next(payload, payload_len, &offset, &tlv) == TVLCOM_OK)
    {
        const user_tvl_data_descriptor_t *descriptor;

        if (tlv.length != 4U && tlv.length != 1U)
        {
            user_tvlcom_send_nack(seq);
            return;
        }

        descriptor = user_tvlcom_descriptor(tlv.type);
        if ((descriptor == NULL) ||
            ((descriptor->access & USER_TVL_ACCESS_WRITE) == 0U) ||
            ((uint16_t)descriptor->value_type != tlv.length))
        {
            user_tvlcom_send_nack(seq);
            return;
        }

        value_u32 = 0U;
        if (tlv.length == 1U)
        {
            value_u32 = tlv.value[0];
        }
        else if (tvlcom_payload_get_u32(payload, payload_len, tlv.type, &value_u32) != TVLCOM_OK)
        {
            user_tvlcom_send_nack(seq);
            return;
        }

        switch (tlv.type)
        {
        case USER_TVL_SET_VOLTAGE_LIMIT:
            UserPower_SetVoltageLimitMv(value_u32);
            break;
        case USER_TVL_SET_CURRENT_LIMIT:
            UserPower_SetCurrentLimitMa(value_u32);
            break;
        case USER_TVL_POWER_STATE:
            UserPower_SetPowerState((uint8_t)value_u32);
            break;
        case USER_TVL_OTP_SET_VALUE:
            UserPower_SetOtpMc(value_u32);
            break;
        case USER_TVL_OVP_SET_VALUE:
            UserPower_SetOvpMv(value_u32);
            break;
        case USER_TVL_OCP_SET_VALUE:
            UserPower_SetOcpMa(value_u32);
            break;
        case USER_TVL_FAN_SET_VALUE:
            UserPower_SetFanValue(value_u32);
            break;
        default:
            user_tvlcom_send_nack(seq);
            return;
        }
    }

    UserPower_RequestSave();
    user_tvlcom_send(USER_TVL_CMD_ACK, seq, NULL, 0U);
}

void UserTvlcom_Init(void)
{
    tvlcom_parser_init(&g_parser);
    g_report_ticks = 0U;
    g_report_pending = 0U;
    g_next_report_tick = HAL_GetTick() + USER_TVL_REPORT_INTERVAL_MS;
    g_report_frame_len = 0U;
    g_report_frame_pending = 0U;
}

void UserTvlcom_1msTask(void)
{
    /* Passive mode: no unsolicited telemetry. */
}

void UserTvlcom_RequestReport(void)
{
    /* Keep API for compatibility; ignored in passive mode. */
    g_report_pending = 0U;
}

void UserTvlcom_BackgroundTask(void)
{
    /* Passive mode: only pump queued TX if any synchronous path queued data. */
    UserTvlcom_TxPump();
}

void UserTvlcom_TxPump(void)
{
    if ((g_report_frame_pending != 0U) && (g_report_frame_len > 0U))
    {
        if (CDC_Transmit_FS(g_report_frame, g_report_frame_len) == USBD_OK)
        {
            g_report_frame_pending = 0U;
        }
    }
}

void UserTvlcom_OnBytes(const uint8_t *data, uint16_t length)
{
    tvlcom_frame_t frames[2];
    uint8_t count = 0U;
    uint8_t index;

    if ((data == NULL) || (length == 0U))
    {
        return;
    }

    if (tvlcom_parser_input(&g_parser, data, length, frames, 2U, &count) < TVLCOM_OK)
    {
        return;
    }

    for (index = 0U; index < count; ++index)
    {
        if (frames[index].cmd == USER_TVL_CMD_READ)
        {
            user_tvlcom_handle_read(frames[index].seq, frames[index].payload, frames[index].payload_len);
        }
        else if (frames[index].cmd == USER_TVL_CMD_WRITE)
        {
            user_tvlcom_handle_write(frames[index].seq, frames[index].payload, frames[index].payload_len);
        }
        else
        {
            user_tvlcom_send_nack(frames[index].seq);
        }
    }
}
