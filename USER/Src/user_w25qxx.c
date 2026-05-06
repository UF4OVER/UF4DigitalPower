#include "../Inc/user_w25qxx.h"

#include "spi.h"

#define USER_W25QXX_CMD_WRITE_ENABLE 0x06U
#define USER_W25QXX_CMD_READ_STATUS  0x05U
#define USER_W25QXX_CMD_READ_DATA    0x03U
#define USER_W25QXX_CMD_PAGE_PROGRAM 0x02U
#define USER_W25QXX_CMD_SECTOR_ERASE 0x20U

#define USER_W25QXX_PAGE_SIZE   256U
#define USER_W25QXX_SECTOR_SIZE 4096U

static void user_w25qxx_select(void)
{
    HAL_GPIO_WritePin(SPI3_CS_GPIO_Port, SPI3_CS_Pin, GPIO_PIN_RESET);
}

static void user_w25qxx_deselect(void)
{
    HAL_GPIO_WritePin(SPI3_CS_GPIO_Port, SPI3_CS_Pin, GPIO_PIN_SET);
}

static HAL_StatusTypeDef user_w25qxx_transfer(uint8_t *tx, uint8_t *rx, uint16_t size)
{
    return HAL_SPI_TransmitReceive(&hspi3, tx, rx, size, 100U);
}

static HAL_StatusTypeDef user_w25qxx_write_enable(void)
{
    uint8_t tx[1] = {USER_W25QXX_CMD_WRITE_ENABLE};
    uint8_t rx[1] = {0U};

    user_w25qxx_select();
    if (user_w25qxx_transfer(tx, rx, 1U) != HAL_OK)
    {
        user_w25qxx_deselect();
        return HAL_ERROR;
    }
    user_w25qxx_deselect();
    return HAL_OK;
}

static HAL_StatusTypeDef user_w25qxx_wait_ready(void)
{
    uint32_t timeout = HAL_GetTick() + 200U;
    uint8_t tx[2] = {USER_W25QXX_CMD_READ_STATUS, 0xFFU};
    uint8_t rx[2] = {0U};

    while (HAL_GetTick() <= timeout)
    {
        user_w25qxx_select();
        if (user_w25qxx_transfer(tx, rx, 2U) != HAL_OK)
        {
            user_w25qxx_deselect();
            return HAL_ERROR;
        }
        user_w25qxx_deselect();

        if ((rx[1] & 0x01U) == 0U)
        {
            return HAL_OK;
        }
    }

    return HAL_TIMEOUT;
}

HAL_StatusTypeDef UserW25Qxx_Init(void)
{
    hspi3.Init.DataSize = SPI_DATASIZE_8BIT;
    hspi3.Init.NSSPMode = SPI_NSS_PULSE_DISABLE;
    if (HAL_SPI_Init(&hspi3) != HAL_OK)
    {
        return HAL_ERROR;
    }

    user_w25qxx_deselect();
    return user_w25qxx_wait_ready();
}

HAL_StatusTypeDef UserW25Qxx_Read(uint32_t address, uint8_t *buffer, uint16_t length)
{
    uint8_t header[4];

    if ((buffer == NULL) || (length == 0U))
    {
        return HAL_ERROR;
    }

    header[0] = USER_W25QXX_CMD_READ_DATA;
    header[1] = (uint8_t)(address >> 16);
    header[2] = (uint8_t)(address >> 8);
    header[3] = (uint8_t)address;

    user_w25qxx_select();
    if (HAL_SPI_Transmit(&hspi3, header, 4U, 100U) != HAL_OK)
    {
        user_w25qxx_deselect();
        return HAL_ERROR;
    }
    if (HAL_SPI_Receive(&hspi3, buffer, length, 100U) != HAL_OK)
    {
        user_w25qxx_deselect();
        return HAL_ERROR;
    }
    user_w25qxx_deselect();
    return HAL_OK;
}

HAL_StatusTypeDef UserW25Qxx_EraseSector(uint32_t address)
{
    uint8_t header[4];

    if (user_w25qxx_write_enable() != HAL_OK)
    {
        return HAL_ERROR;
    }

    header[0] = USER_W25QXX_CMD_SECTOR_ERASE;
    header[1] = (uint8_t)(address >> 16);
    header[2] = (uint8_t)(address >> 8);
    header[3] = (uint8_t)address;

    user_w25qxx_select();
    if (HAL_SPI_Transmit(&hspi3, header, 4U, 100U) != HAL_OK)
    {
        user_w25qxx_deselect();
        return HAL_ERROR;
    }
    user_w25qxx_deselect();

    return user_w25qxx_wait_ready();
}

HAL_StatusTypeDef UserW25Qxx_Write(uint32_t address, const uint8_t *buffer, uint16_t length)
{
    uint16_t chunk;
    uint8_t header[4];

    if ((buffer == NULL) || (length == 0U))
    {
        return HAL_ERROR;
    }

    while (length > 0U)
    {
        chunk = (uint16_t)(USER_W25QXX_PAGE_SIZE - (address % USER_W25QXX_PAGE_SIZE));
        if (chunk > length)
        {
            chunk = length;
        }

        if (user_w25qxx_write_enable() != HAL_OK)
        {
            return HAL_ERROR;
        }

        header[0] = USER_W25QXX_CMD_PAGE_PROGRAM;
        header[1] = (uint8_t)(address >> 16);
        header[2] = (uint8_t)(address >> 8);
        header[3] = (uint8_t)address;

        user_w25qxx_select();
        if (HAL_SPI_Transmit(&hspi3, header, 4U, 100U) != HAL_OK)
        {
            user_w25qxx_deselect();
            return HAL_ERROR;
        }
        if (HAL_SPI_Transmit(&hspi3, (uint8_t *)buffer, chunk, 100U) != HAL_OK)
        {
            user_w25qxx_deselect();
            return HAL_ERROR;
        }
        user_w25qxx_deselect();

        if (user_w25qxx_wait_ready() != HAL_OK)
        {
            return HAL_ERROR;
        }

        address += chunk;
        buffer += chunk;
        length = (uint16_t)(length - chunk);
    }

    return HAL_OK;
}

