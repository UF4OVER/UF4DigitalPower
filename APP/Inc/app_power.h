#ifndef APP_POWER_H
#define APP_POWER_H

#include "main.h"

#include <stdint.h>

#define POWER_APP_ADC_CHANNEL_COUNT 4U

typedef enum
{
    POWER_APP_MODE_CC = 0U,
    POWER_APP_MODE_CV = 1U
} power_app_reg_mode_t;

typedef enum
{
    POWER_APP_STATE_INIT = 0U,
    POWER_APP_STATE_WAIT = 1U,
    POWER_APP_STATE_RISE = 2U,
    POWER_APP_STATE_RUN = 3U,
    POWER_APP_STATE_ERR = 4U
} power_app_state_t;

typedef enum
{
    POWER_APP_TOPOLOGY_NA = 0U,
    POWER_APP_TOPOLOGY_BUCK = 1U,
    POWER_APP_TOPOLOGY_BOOST = 2U,
    POWER_APP_TOPOLOGY_MIX = 3U
} power_app_topology_t;

enum
{
    POWER_APP_FAULT_INPUT_UNDER_VOLTAGE = 0x0001U,
    POWER_APP_FAULT_INPUT_OVER_VOLTAGE = 0x0002U,
    POWER_APP_FAULT_OUTPUT_UNDER_VOLTAGE = 0x0004U,
    POWER_APP_FAULT_OUTPUT_OVER_VOLTAGE = 0x0008U,
    POWER_APP_FAULT_OUTPUT_OVER_CURRENT = 0x0010U,
    POWER_APP_FAULT_OUTPUT_SHORT = 0x0020U,
    POWER_APP_FAULT_OVER_TEMPERATURE = 0x0040U
};

typedef struct
{
    float kp;
    float ki;
    float kd;
    float integral;
    float prev_error;
    float prev_measurement;
    float out_min;
    float out_max;
} power_app_pid_t;

typedef struct
{
    float target_voltage_v;
    float target_current_a;
    float otp_c;
    float ovp_v;
    float ocp_a;
    float input_uvp_v;
    float input_ovp_v;
    uint8_t power_enabled;
    power_app_pid_t voltage_pid;
    power_app_pid_t current_pid;
} power_app_config_t;

typedef struct
{
    uint16_t raw_adc[POWER_APP_ADC_CHANNEL_COUNT];
    float vin_v;
    float iin_a;
    float vout_v;
    float iout_a;
    float core_temp_c;
    float board_temp_c;
    float current_ref_a;
    float duty_cmd;
    uint32_t fan_speed;
    uint16_t pwm_a_compare;
    uint16_t pwm_d_compare;
    uint16_t fault_mask;
    power_app_state_t state;
    power_app_topology_t topology;
    power_app_reg_mode_t regulation_mode;
} power_app_status_t;

extern volatile uint16_t ADC1_RESULT[POWER_APP_ADC_CHANNEL_COUNT];

void PowerApp_Init(void);
void PowerApp_FastLoop(void);
void PowerApp_1msTask(void);
void PowerApp_5msTask(void);
void PowerApp_CommTask(void);
void PowerApp_BackgroundTask(void);
void PowerApp_OnCommBytes(const uint8_t *data, uint16_t length);

void PowerApp_GetStatus(power_app_status_t *out_status);
void PowerApp_GetConfig(power_app_config_t *out_config);

void PowerApp_SetVoltageLimitMv(uint32_t value_mv);
void PowerApp_SetCurrentLimitMa(uint32_t value_ma);
void PowerApp_SetOvpMv(uint32_t value_mv);
void PowerApp_SetOcpMa(uint32_t value_ma);
void PowerApp_SetOtpMc(uint32_t value_mc);
void PowerApp_SetPowerState(uint8_t enabled);
void PowerApp_RequestSave(void);

#endif
