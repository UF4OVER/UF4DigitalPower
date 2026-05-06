#ifndef USER_TVLCOM_H
#define USER_TVLCOM_H

#include "main.h"

typedef enum
{
    USER_TVL_CMD_ACK = 0x00U,
    USER_TVL_CMD_READ = 0x01U,
    USER_TVL_CMD_WRITE = 0x02U,
    USER_TVL_CMD_REPORT = 0x03U,
    USER_TVL_CMD_NACK = 0xFFU
} user_tvl_cmd_t;

typedef enum
{
    USER_TVL_VALUE_U8 = 1U,
    USER_TVL_VALUE_U32 = 4U
} user_tvl_value_type_t;

typedef enum
{
    USER_TVL_ACCESS_READ = 0x01U,
    USER_TVL_ACCESS_WRITE = 0x02U,
    USER_TVL_ACCESS_READ_WRITE = USER_TVL_ACCESS_READ | USER_TVL_ACCESS_WRITE
} user_tvl_access_t;

typedef enum
{
    USER_TVL_INPUT_VOLTAGE = 10U,
    USER_TVL_INPUT_CURRENT = 11U,
    USER_TVL_OUTPUT_VOLTAGE = 12U,
    USER_TVL_OUTPUT_CURRENT = 13U,
    USER_TVL_CORE_TEMPERATURE = 14U,
    USER_TVL_BOARD_TEMPERATURE = 15U,
    USER_TVL_SET_VOLTAGE_LIMIT = 17U,
    USER_TVL_SET_CURRENT_LIMIT = 18U,
    USER_TVL_CC_CV_MODE = 20U,
    USER_TVL_POWER_STATE = 21U,
    USER_TVL_FAULT_STATE = 22U,
    USER_TVL_STATE_MACHINE_FLAG_BITS = 23U,
    USER_TVL_STATE_MACHINE_STATE = 24U,
    USER_TVL_INPUT_VOLTAGE_RAW = 25U,
    USER_TVL_INPUT_CURRENT_RAW = 26U,
    USER_TVL_OUTPUT_VOLTAGE_RAW = 27U,
    USER_TVL_OUTPUT_CURRENT_RAW = 28U,
    USER_TVL_OTP_VALUE = 29U,
    USER_TVL_OTP_SET_VALUE = 30U,
    USER_TVL_OVP_VALUE = 31U,
    USER_TVL_OVP_SET_VALUE = 32U,
    USER_TVL_OCP_VALUE = 33U,
    USER_TVL_OCP_SET_VALUE = 34U,
    USER_TVL_FAN_SPEED = 38U,
    USER_TVL_FAN_SET_VALUE = 39U,
    USER_TVL_DEBUG_SNAPSHOT = 40U
} user_tvl_data_type_t;

typedef struct
{
    user_tvl_data_type_t type;
    user_tvl_value_type_t value_type;
    user_tvl_access_t access;
    const char *unit;
} user_tvl_data_descriptor_t;

extern const user_tvl_data_descriptor_t g_user_tvl_data_descriptors[];
extern const uint8_t g_user_tvl_data_descriptor_count;

void UserTvlcom_Init(void);
void UserTvlcom_1msTask(void);
void UserTvlcom_RequestReport(void);
void UserTvlcom_BackgroundTask(void);
void UserTvlcom_TxPump(void);
void UserTvlcom_OnBytes(const uint8_t *data, uint16_t length);

#endif

