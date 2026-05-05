#ifndef APP_TVLCOM_H
#define APP_TVLCOM_H

#include "main.h"

typedef enum
{
    APP_TVL_CMD_ACK = 0x00U,
    APP_TVL_CMD_READ = 0x01U,
    APP_TVL_CMD_WRITE = 0x02U,
    APP_TVL_CMD_REPORT = 0x03U,
    APP_TVL_CMD_NACK = 0xFFU
} app_tvl_cmd_t;

typedef enum
{
    APP_TVL_VALUE_U8 = 1U,
    APP_TVL_VALUE_U32 = 4U
} app_tvl_value_type_t;

typedef enum
{
    APP_TVL_ACCESS_READ = 0x01U,
    APP_TVL_ACCESS_WRITE = 0x02U,
    APP_TVL_ACCESS_READ_WRITE = APP_TVL_ACCESS_READ | APP_TVL_ACCESS_WRITE
} app_tvl_access_t;

typedef enum
{
    APP_TVL_INPUT_VOLTAGE = 10U,
    APP_TVL_INPUT_CURRENT = 11U,
    APP_TVL_OUTPUT_VOLTAGE = 12U,
    APP_TVL_OUTPUT_CURRENT = 13U,
    APP_TVL_CORE_TEMPERATURE = 14U,
    APP_TVL_BOARD_TEMPERATURE = 15U,
    APP_TVL_SET_VOLTAGE_LIMIT = 17U,
    APP_TVL_SET_CURRENT_LIMIT = 18U,
    APP_TVL_CC_CV_MODE = 20U,
    APP_TVL_POWER_STATE = 21U,
    APP_TVL_FAULT_STATE = 22U,
    APP_TVL_STATE_MACHINE_FLAG_BITS = 23U,
    APP_TVL_STATE_MACHINE_STATE = 24U,
    APP_TVL_INPUT_VOLTAGE_RAW = 25U,
    APP_TVL_INPUT_CURRENT_RAW = 26U,
    APP_TVL_OUTPUT_VOLTAGE_RAW = 27U,
    APP_TVL_OUTPUT_CURRENT_RAW = 28U,
    APP_TVL_OTP_VALUE = 29U,
    APP_TVL_OTP_SET_VALUE = 30U,
    APP_TVL_OVP_VALUE = 31U,
    APP_TVL_OVP_SET_VALUE = 32U,
    APP_TVL_OCP_VALUE = 33U,
    APP_TVL_OCP_SET_VALUE = 34U,
    APP_TVL_FAN_SPEED = 38U,
    APP_TVL_FAN_SET_VALUE = 39U,
    APP_TVL_DEBUG_SNAPSHOT = 40U
} app_tvl_data_type_t;

typedef struct
{
    app_tvl_data_type_t type;
    app_tvl_value_type_t value_type;
    app_tvl_access_t access;
    const char *unit;
} app_tvl_data_descriptor_t;

extern const app_tvl_data_descriptor_t g_app_tvl_data_descriptors[];
extern const uint8_t g_app_tvl_data_descriptor_count;

void AppTvlcom_Init(void);
void AppTvlcom_1msTask(void);
void AppTvlcom_RequestReport(void);
void AppTvlcom_BackgroundTask(void);
void AppTvlcom_TxPump(void);
void AppTvlcom_OnBytes(const uint8_t *data, uint16_t length);

#endif
