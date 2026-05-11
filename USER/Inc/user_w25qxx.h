#ifndef USER_W25QXX_H
#define USER_W25QXX_H

#include "main.h"

#include <stdint.h>

HAL_StatusTypeDef UserW25Qxx_Init(void);
HAL_StatusTypeDef UserW25Qxx_Read(uint32_t address, uint8_t *buffer, uint16_t length);
HAL_StatusTypeDef UserW25Qxx_Write(uint32_t address, const uint8_t *buffer, uint16_t length);
HAL_StatusTypeDef UserW25Qxx_EraseSector(uint32_t address);

#endif

