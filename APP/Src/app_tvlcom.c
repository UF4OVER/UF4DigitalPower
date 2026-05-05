#include "app_tvlcom.h"

#include "app_power.h"
#include "tvlcom.h"
#include "usbd_cdc_if.h"

#include <string.h>

#define APP_TVL_REPORT_INTERVAL_MS 1000U

const app_tvl_data_descriptor_t g_app_tvl_data_descriptors[] = {
    {APP_TVL_INPUT_VOLTAGE, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ, "mV"},
    {APP_TVL_INPUT_CURRENT, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ, "mA"},
    {APP_TVL_OUTPUT_VOLTAGE, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ, "mV"},
    {APP_TVL_OUTPUT_CURRENT, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ, "mA"},
    {APP_TVL_CORE_TEMPERATURE, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ, "mC"},
    {APP_TVL_BOARD_TEMPERATURE, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ, "mC"},
    {APP_TVL_SET_VOLTAGE_LIMIT, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ_WRITE, "mV"},
    {APP_TVL_SET_CURRENT_LIMIT, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ_WRITE, "mA"},
    {APP_TVL_CC_CV_MODE, APP_TVL_VALUE_U8, APP_TVL_ACCESS_READ, "enum"},
    {APP_TVL_POWER_STATE, APP_TVL_VALUE_U8, APP_TVL_ACCESS_READ_WRITE, "bool"},
    {APP_TVL_FAULT_STATE, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ, "bitmask"},
    {APP_TVL_STATE_MACHINE_FLAG_BITS, APP_TVL_VALUE_U8, APP_TVL_ACCESS_READ, "bitmask"},
    {APP_TVL_STATE_MACHINE_STATE, APP_TVL_VALUE_U8, APP_TVL_ACCESS_READ, "enum"},
    {APP_TVL_INPUT_VOLTAGE_RAW, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ, "adc"},
    {APP_TVL_INPUT_CURRENT_RAW, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ, "adc"},
    {APP_TVL_OUTPUT_VOLTAGE_RAW, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ, "adc"},
    {APP_TVL_OUTPUT_CURRENT_RAW, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ, "adc"},
    {APP_TVL_OTP_VALUE, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ, "mC"},
    {APP_TVL_OTP_SET_VALUE, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ_WRITE, "mC"},
    {APP_TVL_OVP_VALUE, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ, "mV"},
    {APP_TVL_OVP_SET_VALUE, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ_WRITE, "mV"},
    {APP_TVL_OCP_VALUE, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ, "mA"},
    {APP_TVL_OCP_SET_VALUE, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ_WRITE, "mA"},
    {APP_TVL_FAN_SPEED, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ, "permille"},
    {APP_TVL_FAN_SET_VALUE, APP_TVL_VALUE_U32, APP_TVL_ACCESS_READ_WRITE, "permille"}};

const uint8_t g_app_tvl_data_descriptor_count =
    (uint8_t)(sizeof(g_app_tvl_data_descriptors) / sizeof(g_app_tvl_data_descriptors[0]));

static tvlcom_parser_t g_parser;
static volatile uint8_t g_report_pending = 0U;
static uint16_t g_report_ticks = 0U;
static uint32_t g_next_report_tick = 0U;
static uint8_t g_report_frame[TVLCOM_MAX_FRAME_SIZE];
static uint16_t g_report_frame_len = 0U;
static volatile uint8_t g_report_frame_pending = 0U;

static uint8_t app_tvlcom_send(uint8_t cmd, uint8_t seq, const uint8_t *payload, uint16_t payload_len)
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

static uint8_t app_tvlcom_send_nowait(uint8_t cmd, uint8_t seq, const uint8_t *payload, uint16_t payload_len)
{
    uint8_t frame[TVLCOM_MAX_FRAME_SIZE];
    uint16_t frame_len = 0U;

    if (tvlcom_frame_build(cmd, seq, payload, payload_len, frame, sizeof(frame), &frame_len) != TVLCOM_OK)
    {
        return 0U;
    }

    return (CDC_Transmit_FS(frame, frame_len) == USBD_OK) ? 1U : 0U;
}

static void app_tvlcom_send_nack(uint8_t seq)
{
    app_tvlcom_send(APP_TVL_CMD_NACK, seq, NULL, 0U);
}

static const app_tvl_data_descriptor_t *app_tvlcom_descriptor(uint8_t type)
{
    uint8_t index;

    for (index = 0U; index < g_app_tvl_data_descriptor_count; ++index)
    {
        if ((uint8_t)g_app_tvl_data_descriptors[index].type == type)
        {
            return &g_app_tvl_data_descriptors[index];
        }
    }

    return NULL;
}

static uint8_t app_tvlcom_state_bits(power_app_state_t state)
{
    switch (state)
    {
    case POWER_APP_STATE_INIT:
        return 0x01U;
    case POWER_APP_STATE_WAIT:
        return 0x02U;
    case POWER_APP_STATE_RISE:
        return 0x04U;
    case POWER_APP_STATE_RUN:
        return 0x08U;
    case POWER_APP_STATE_ERR:
        return 0x0FU;
    default:
        return 0U;
    }
}

static uint32_t app_tvlcom_float_to_mv(float value)
{
    if (value <= 0.0F)
    {
        return 0U;
    }
    return (uint32_t)(value * 1000.0F + 0.5F);
}

static int32_t app_tvlcom_float_to_ma(float value)
{
    value = value < 0.0F ? 0.0F : value;
    return (int32_t)(value * 1000.0F + 0.5F);
}

static uint32_t app_tvlcom_float_to_mc(float value)
{
    return (uint32_t)(value * 1000.0F + 0.5F);
}

static tvlcom_status_t app_tvlcom_append_type(uint8_t *payload,
                                              uint16_t *payload_len,
                                              uint8_t type,
                                              const power_app_status_t *status,
                                              const power_app_config_t *config)
{
    switch (type)
    {
    case APP_TVL_INPUT_VOLTAGE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, app_tvlcom_float_to_mv(status->vin_v));
    case APP_TVL_INPUT_CURRENT:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, (uint32_t)app_tvlcom_float_to_ma(status->iin_a));
    case APP_TVL_OUTPUT_VOLTAGE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, app_tvlcom_float_to_mv(status->vout_v));
    case APP_TVL_OUTPUT_CURRENT:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, (uint32_t)app_tvlcom_float_to_ma(status->iout_a));
    case APP_TVL_CORE_TEMPERATURE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, app_tvlcom_float_to_mc(status->core_temp_c));
    case APP_TVL_BOARD_TEMPERATURE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, app_tvlcom_float_to_mc(status->board_temp_c));
    case APP_TVL_SET_VOLTAGE_LIMIT:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, app_tvlcom_float_to_mv(config->target_voltage_v));
    case APP_TVL_SET_CURRENT_LIMIT:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, (uint32_t)app_tvlcom_float_to_ma(config->target_current_a));
    case APP_TVL_CC_CV_MODE:
        return tvlcom_payload_add_u8(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, (uint8_t)status->regulation_mode);
    case APP_TVL_POWER_STATE:
        return tvlcom_payload_add_u8(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, config->power_enabled);
    case APP_TVL_FAULT_STATE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, status->fault_mask);
    case APP_TVL_STATE_MACHINE_FLAG_BITS:
        return tvlcom_payload_add_u8(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, app_tvlcom_state_bits(status->state));
    case APP_TVL_STATE_MACHINE_STATE:
        return tvlcom_payload_add_u8(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, (uint8_t)status->topology);
    case APP_TVL_INPUT_VOLTAGE_RAW:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, status->raw_adc[0]);
    case APP_TVL_INPUT_CURRENT_RAW:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, status->raw_adc[1]);
    case APP_TVL_OUTPUT_VOLTAGE_RAW:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, status->raw_adc[2]);
    case APP_TVL_OUTPUT_CURRENT_RAW:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, status->raw_adc[3]);
    case APP_TVL_OTP_VALUE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, app_tvlcom_float_to_mc(status->board_temp_c));
    case APP_TVL_OTP_SET_VALUE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, app_tvlcom_float_to_mc(config->otp_c));
    case APP_TVL_OVP_VALUE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, app_tvlcom_float_to_mv(status->vout_v));
    case APP_TVL_OVP_SET_VALUE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, app_tvlcom_float_to_mv(config->ovp_v));
    case APP_TVL_OCP_VALUE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, (uint32_t)app_tvlcom_float_to_ma(status->iout_a));
    case APP_TVL_OCP_SET_VALUE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, (uint32_t)app_tvlcom_float_to_ma(config->ocp_a));
    case APP_TVL_FAN_SPEED:
    case APP_TVL_FAN_SET_VALUE:
        return tvlcom_payload_add_u32(payload, TVLCOM_MAX_PAYLOAD_SIZE, payload_len, type, status->fan_speed);
    default:
        return TVLCOM_ERR_NOT_FOUND;
    }
}

static tvlcom_status_t app_tvlcom_append_report_payload(uint8_t *payload, uint16_t *payload_len)
{
    static const uint8_t report_types[] = {
        APP_TVL_INPUT_VOLTAGE,
        APP_TVL_INPUT_CURRENT,
        APP_TVL_OUTPUT_VOLTAGE,
        APP_TVL_OUTPUT_CURRENT,
        APP_TVL_CORE_TEMPERATURE,
        APP_TVL_BOARD_TEMPERATURE,
        APP_TVL_SET_VOLTAGE_LIMIT,
        APP_TVL_SET_CURRENT_LIMIT,
        APP_TVL_CC_CV_MODE,
        APP_TVL_POWER_STATE,
        APP_TVL_FAULT_STATE,
        APP_TVL_STATE_MACHINE_FLAG_BITS,
        APP_TVL_STATE_MACHINE_STATE,
        APP_TVL_OTP_SET_VALUE,
        APP_TVL_OVP_SET_VALUE,
        APP_TVL_OCP_SET_VALUE,
        APP_TVL_FAN_SPEED};
    power_app_status_t status;
    power_app_config_t config;
    uint8_t index;
    tvlcom_status_t status_code;

    PowerApp_GetStatus(&status);
    PowerApp_GetConfig(&config);

    for (index = 0U; index < (uint8_t)(sizeof(report_types) / sizeof(report_types[0])); ++index)
    {
        status_code = app_tvlcom_append_type(payload, payload_len, report_types[index], &status, &config);
        if (status_code != TVLCOM_OK)
        {
            return status_code;
        }
    }

    return TVLCOM_OK;
}

static tvlcom_status_t app_tvlcom_append_debug_snapshot(uint8_t *payload,
                                                        uint16_t *payload_len,
                                                        const power_app_status_t *status,
                                                        const power_app_config_t *config)
{
    tvlcom_status_t status_code;

    status_code = tvlcom_payload_add_u32(payload,
                                         TVLCOM_MAX_PAYLOAD_SIZE,
                                         payload_len,
                                         APP_TVL_OUTPUT_VOLTAGE_RAW,
                                         status->raw_adc[2]);
    if (status_code != TVLCOM_OK)
    {
        return status_code;
    }

    status_code = tvlcom_payload_add_u32(payload,
                                         TVLCOM_MAX_PAYLOAD_SIZE,
                                         payload_len,
                                         APP_TVL_OUTPUT_VOLTAGE,
                                         app_tvlcom_float_to_mv(status->vout_v));
    if (status_code != TVLCOM_OK)
    {
        return status_code;
    }

    return tvlcom_payload_add_u32(payload,
                                  TVLCOM_MAX_PAYLOAD_SIZE,
                                  payload_len,
                                  APP_TVL_OVP_SET_VALUE,
                                  app_tvlcom_float_to_mv(config->ovp_v));
}

static void app_tvlcom_handle_read(uint8_t seq, const uint8_t *payload, uint16_t payload_len)
{
    power_app_status_t status;
    power_app_config_t config;
    tvlcom_tlv_t tlv;
    uint16_t offset = 0U;
    uint8_t ack_payload[TVLCOM_MAX_PAYLOAD_SIZE];
    uint16_t ack_len = 0U;

    PowerApp_GetStatus(&status);
    PowerApp_GetConfig(&config);

    while (tvlcom_payload_next(payload, payload_len, &offset, &tlv) == TVLCOM_OK)
    {
        if (tlv.type == APP_TVL_DEBUG_SNAPSHOT)
        {
            if (app_tvlcom_append_debug_snapshot(ack_payload, &ack_len, &status, &config) != TVLCOM_OK)
            {
                app_tvlcom_send_nack(seq);
                return;
            }
            continue;
        }

        if (app_tvlcom_append_type(ack_payload, &ack_len, tlv.type, &status, &config) != TVLCOM_OK)
        {
            app_tvlcom_send_nack(seq);
            return;
        }
    }

    app_tvlcom_send(APP_TVL_CMD_ACK, seq, ack_payload, ack_len);
}

static void app_tvlcom_handle_write(uint8_t seq, const uint8_t *payload, uint16_t payload_len)
{
    tvlcom_tlv_t tlv;
    uint16_t offset = 0U;
    uint32_t value_u32 = 0U;

    while (tvlcom_payload_next(payload, payload_len, &offset, &tlv) == TVLCOM_OK)
    {
        if (tlv.length != 4U && tlv.length != 1U)
        {
            app_tvlcom_send_nack(seq);
            return;
        }

        const app_tvl_data_descriptor_t *descriptor = app_tvlcom_descriptor(tlv.type);
        if ((descriptor == NULL) ||
            ((descriptor->access & APP_TVL_ACCESS_WRITE) == 0U) ||
            ((uint16_t)descriptor->value_type != tlv.length))
        {
            app_tvlcom_send_nack(seq);
            return;
        }

        value_u32 = 0U;
        if (tlv.length == 1U)
        {
            value_u32 = tlv.value[0];
        }
        else if (tvlcom_payload_get_u32(payload, payload_len, tlv.type, &value_u32) != TVLCOM_OK)
        {
            app_tvlcom_send_nack(seq);
            return;
        }

        switch (tlv.type)
        {
        case APP_TVL_SET_VOLTAGE_LIMIT:
            PowerApp_SetVoltageLimitMv(value_u32);
            break;
        case APP_TVL_SET_CURRENT_LIMIT:
            PowerApp_SetCurrentLimitMa(value_u32);
            break;
        case APP_TVL_POWER_STATE:
            PowerApp_SetPowerState((uint8_t)value_u32);
            break;
        case APP_TVL_OTP_SET_VALUE:
            PowerApp_SetOtpMc(value_u32);
            break;
        case APP_TVL_OVP_SET_VALUE:
            PowerApp_SetOvpMv(value_u32);
            break;
        case APP_TVL_OCP_SET_VALUE:
            PowerApp_SetOcpMa(value_u32);
            break;
        case APP_TVL_FAN_SET_VALUE:
            break;
        default:
            app_tvlcom_send_nack(seq);
            return;
        }
    }

    PowerApp_RequestSave();
    app_tvlcom_send(APP_TVL_CMD_ACK, seq, NULL, 0U);
}

void AppTvlcom_Init(void)
{
    tvlcom_parser_init(&g_parser);
    g_report_ticks = 0U;
    g_report_pending = 0U;
    g_next_report_tick = HAL_GetTick() + APP_TVL_REPORT_INTERVAL_MS;
    g_report_frame_len = 0U;
    g_report_frame_pending = 0U;
}

void AppTvlcom_1msTask(void)
{
    if (++g_report_ticks >= APP_TVL_REPORT_INTERVAL_MS)
    {
        g_report_ticks = 0U;
        AppTvlcom_RequestReport();
    }
}

void AppTvlcom_RequestReport(void)
{
    g_report_pending = 1U;
}

void AppTvlcom_BackgroundTask(void)
{
    uint8_t payload[TVLCOM_MAX_PAYLOAD_SIZE];
    uint16_t payload_len = 0U;
    uint32_t now = HAL_GetTick();

    if ((int32_t)(now - g_next_report_tick) >= 0)
    {
        g_next_report_tick = now + APP_TVL_REPORT_INTERVAL_MS;
        g_report_pending = 1U;
    }

    if ((g_report_pending != 0U) && (g_report_frame_pending == 0U))
    {
        if (app_tvlcom_append_report_payload(payload, &payload_len) == TVLCOM_OK)
        {
            if (tvlcom_frame_build(APP_TVL_CMD_REPORT,
                                   0U,
                                   payload,
                                   payload_len,
                                   g_report_frame,
                                   sizeof(g_report_frame),
                                   &g_report_frame_len) == TVLCOM_OK)
            {
                g_report_frame_pending = 1U;
                g_report_pending = 0U;
            }
        }
    }

    AppTvlcom_TxPump();
}

void AppTvlcom_TxPump(void)
{
    if ((g_report_frame_pending != 0U) && (g_report_frame_len > 0U))
    {
        if (CDC_Transmit_FS(g_report_frame, g_report_frame_len) == USBD_OK)
        {
            g_report_frame_pending = 0U;
        }
    }
}

void AppTvlcom_OnBytes(const uint8_t *data, uint16_t length)
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
        if (frames[index].cmd == APP_TVL_CMD_READ)
        {
            app_tvlcom_handle_read(frames[index].seq, frames[index].payload, frames[index].payload_len);
        }
        else if (frames[index].cmd == APP_TVL_CMD_WRITE)
        {
            app_tvlcom_handle_write(frames[index].seq, frames[index].payload, frames[index].payload_len);
        }
        else
        {
            app_tvlcom_send_nack(frames[index].seq);
        }
    }
}
