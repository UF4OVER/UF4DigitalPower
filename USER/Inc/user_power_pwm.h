#ifndef USER_POWER_PWM_H
#define USER_POWER_PWM_H

#include "user_power_types.h"

#include <stdint.h>

void UserPowerPwm_Init(user_power_status_t *status);
void UserPowerPwm_Start(void);
void UserPowerPwm_Stop(user_power_status_t *status);
void UserPowerPwm_ApplyDuty(user_power_topology_t topology, float duty, user_power_status_t *status);

#endif
