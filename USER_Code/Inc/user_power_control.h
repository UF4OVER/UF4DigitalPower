#ifndef USER_POWER_CONTROL_H
#define USER_POWER_CONTROL_H

#ifdef __cplusplus
extern "C" {
#endif

#include "main.h"
#include <stdint.h>

typedef enum
{
    USER_POWER_MODE_NA = 0U,
    USER_POWER_MODE_BUCK = 1U,
    USER_POWER_MODE_BOOST = 2U,
    USER_POWER_MODE_MIX = 3U
} user_power_mode_t;

typedef enum
{
    USER_POWER_REG_CV = 0U,
    USER_POWER_REG_CC = 1U
} user_power_regulation_t;

typedef struct
{
    uint16_t raw_vin;
    uint16_t raw_iin;
    uint16_t raw_vout;
    uint16_t raw_iout;
    uint32_t avg_vin;
    uint32_t avg_iin;
    uint32_t avg_vout;
    uint32_t avg_iout;
    float vin_v;
    float iin_a;
    float vout_v;
    float iout_a;
    float board_temp_c;
    float cpu_temp_c;
} user_power_sample_t;

typedef struct
{
    float set_vout_v;
    float set_iout_a;
    float ovp_v;
    float ocp_a;
    float otp_c;
    uint8_t output_enable;
} user_power_setpoint_t;

void UserPower_Init(void);
void UserPower_FastLoop(void);
void UserPower_5msTask(void);
void UserPower_SetOutput(float voltage_v, float current_a, uint8_t enable);
const user_power_sample_t *UserPower_GetSample(void);
const user_power_setpoint_t *UserPower_GetSetpoint(void);
user_power_mode_t UserPower_GetMode(void);
user_power_regulation_t UserPower_GetRegulation(void);

#ifdef __cplusplus
}
#endif

#endif
