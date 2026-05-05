#ifndef APP_W25QXX_H
#define APP_W25QXX_H

#include "main.h"

#include <stdint.h>

HAL_StatusTypeDef AppW25Qxx_Init(void);
HAL_StatusTypeDef AppW25Qxx_Read(uint32_t address, uint8_t *buffer, uint16_t length);
HAL_StatusTypeDef AppW25Qxx_Write(uint32_t address, const uint8_t *buffer, uint16_t length);
HAL_StatusTypeDef AppW25Qxx_EraseSector(uint32_t address);

#endif
