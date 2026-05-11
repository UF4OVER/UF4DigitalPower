#ifndef USER_POWER_H
#define USER_POWER_H

#include "user_power_types.h"

void UserPower_Init(volatile uint16_t *adc_dma_buffer);
void UserPower_FastLoop(void);
void UserPower_5msTask(void);
void UserPower_CommTask(void);
void UserPower_AuxTask(void);
void UserPower_SaveTask(void);
void UserPower_BackgroundTask(void);

void UserPower_GetStatus(user_power_status_t *out_status);
void UserPower_GetConfig(user_power_config_t *out_config);

void UserPower_SetVoltageLimitMv(uint32_t value_mv);
void UserPower_SetCurrentLimitMa(uint32_t value_ma);
void UserPower_SetOvpMv(uint32_t value_mv);
void UserPower_SetOcpMa(uint32_t value_ma);
void UserPower_SetOtpMc(uint32_t value_mc);
void UserPower_SetFanValue(uint32_t value);
void UserPower_SetPowerState(uint8_t enabled);
void UserPower_RequestSave(void);

#endif
