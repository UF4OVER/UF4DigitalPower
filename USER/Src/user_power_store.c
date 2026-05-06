#include "../Inc/user_power_store.h"

#include "../Inc/user_w25qxx.h"

#include <string.h>

#define USER_PWR_STORAGE_ADDR    0x000000U
#define USER_PWR_STORAGE_MAGIC   0x55505752UL
#define USER_PWR_STORAGE_VERSION 1U

typedef struct
{
    uint32_t magic;
    uint16_t version;
    uint16_t reserved;
    user_power_config_t config;
    uint16_t crc;
} user_power_storage_t;

static uint16_t user_power_crc16(const uint8_t *data, uint16_t length)
{
    uint16_t crc = 0xFFFFU;
    uint16_t i;

    while (length-- > 0U)
    {
        crc ^= *data++;
        for (i = 0U; i < 8U; ++i)
        {
            crc = (crc & 1U) ? (uint16_t)((crc >> 1) ^ 0xA001U) : (uint16_t)(crc >> 1);
        }
    }

    return crc;
}

HAL_StatusTypeDef UserPowerStore_Init(void)
{
    return UserW25Qxx_Init();
}

void UserPowerStore_Load(user_power_config_t *config)
{
    user_power_storage_t image;
    uint16_t crc;

    if (config == NULL)
    {
        return;
    }

    if (UserW25Qxx_Read(USER_PWR_STORAGE_ADDR, (uint8_t *)&image, sizeof(image)) != HAL_OK)
    {
        return;
    }

    crc = user_power_crc16((const uint8_t *)&image, (uint16_t)(sizeof(image) - sizeof(image.crc)));
    if ((image.magic != USER_PWR_STORAGE_MAGIC) ||
        (image.version != USER_PWR_STORAGE_VERSION) ||
        (crc != image.crc))
    {
        return;
    }

    *config = image.config;
}

void UserPowerStore_Save(const user_power_config_t *config)
{
    user_power_storage_t image;

    if (config == NULL)
    {
        return;
    }

    memset(&image, 0, sizeof(image));
    image.magic = USER_PWR_STORAGE_MAGIC;
    image.version = USER_PWR_STORAGE_VERSION;
    image.config = *config;
    image.config.voltage_pid.integral = 0.0f;
    image.config.current_pid.integral = 0.0f;
    image.config.voltage_pid.prev_error = 0.0f;
    image.config.current_pid.prev_error = 0.0f;
    image.config.voltage_pid.prev_measurement = 0.0f;
    image.config.current_pid.prev_measurement = 0.0f;
    image.crc = user_power_crc16((const uint8_t *)&image, (uint16_t)(sizeof(image) - sizeof(image.crc)));

    if (UserW25Qxx_EraseSector(USER_PWR_STORAGE_ADDR) == HAL_OK)
    {
        (void)UserW25Qxx_Write(USER_PWR_STORAGE_ADDR, (const uint8_t *)&image, sizeof(image));
    }
}

