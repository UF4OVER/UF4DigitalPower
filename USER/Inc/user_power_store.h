#ifndef USER_POWER_STORE_H
#define USER_POWER_STORE_H

#include "user_power_types.h"

HAL_StatusTypeDef UserPowerStore_Init(void);
void UserPowerStore_Load(user_power_config_t *config);
void UserPowerStore_Save(const user_power_config_t *config);

#endif
