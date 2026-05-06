#ifndef USER_POWER_TYPES_H
#define USER_POWER_TYPES_H

#include "main.h"

#include <stdint.h>

#define USER_POWER_ADC_CHANNEL_COUNT 4U

typedef enum
{
    USER_POWER_MODE_CC = 0U,
    USER_POWER_MODE_CV = 1U
} user_power_reg_mode_t;

typedef enum
{
    USER_POWER_STATE_INIT = 0U,
    USER_POWER_STATE_WAIT = 1U,
    USER_POWER_STATE_RISE = 2U,
    USER_POWER_STATE_RUN = 3U,
    USER_POWER_STATE_ERR = 4U
} user_power_state_t;

typedef enum
{
    USER_POWER_TOPOLOGY_NA = 0U,
    USER_POWER_TOPOLOGY_BUCK = 1U,
    USER_POWER_TOPOLOGY_BOOST = 2U,
    USER_POWER_TOPOLOGY_MIX = 3U
} user_power_topology_t;

enum
{
    USER_POWER_FAULT_INPUT_UNDER_VOLTAGE = 0x0001U,
    USER_POWER_FAULT_INPUT_OVER_VOLTAGE = 0x0002U,
    USER_POWER_FAULT_OUTPUT_UNDER_VOLTAGE = 0x0004U,
    USER_POWER_FAULT_OUTPUT_OVER_VOLTAGE = 0x0008U,
    USER_POWER_FAULT_OUTPUT_OVER_CURRENT = 0x0010U,
    USER_POWER_FAULT_OUTPUT_SHORT = 0x0020U,
    USER_POWER_FAULT_OVER_TEMPERATURE = 0x0040U
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
} user_power_pid_t;

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
    user_power_pid_t voltage_pid;
    user_power_pid_t current_pid;
} user_power_config_t;

typedef struct
{
    uint16_t raw_adc[USER_POWER_ADC_CHANNEL_COUNT];
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
    user_power_state_t state;
    user_power_topology_t topology;
    user_power_reg_mode_t regulation_mode;
} user_power_status_t;

#endif

