#ifndef BSP_POWER_BOARD_H
#define BSP_POWER_BOARD_H

#ifdef __cplusplus
extern "C" {
#endif

#include "main.h"
#include <stdint.h>

#define BSP_POWER_ADC_CHANNEL_COUNT 4U
#define BSP_POWER_HRTIM_PERIOD 30000U
#define BSP_POWER_ADC_MAX_VALUE 8190.0F
#define BSP_POWER_VREF 3.2806F
#define BSP_POWER_VOLTAGE_DIVIDER_RATIO (75.0F / 5.6F)  // 电压缩放
#define BSP_POWER_CURRENT_SHUNT_OHM 0.008F   // 采样电阻
#define BSP_POWER_CURRENT_GAIN 20.0F  // 电流增益

#define BSP_POWER_MIN_BUCK_DUTY 100U
#define BSP_POWER_MAX_BUCK_DUTY 28200U
#define BSP_POWER_MAX_BUCK_MIX_DUTY 24000U
#define BSP_POWER_MIN_BOOST_DUTY 100U
#define BSP_POWER_MIN_BOOST_FIXED_DUTY 1800U
#define BSP_POWER_MAX_BOOST_DUTY 19500U
#define BSP_POWER_MAX_BOOST_MIX_DUTY 28200U


typedef enum
{
    BSP_POWER_PWM_LEG_BUCK = 0U,
    BSP_POWER_PWM_LEG_BOOST = 1U
} bsp_power_pwm_leg_t;

extern volatile uint16_t g_bsp_power_adc_dma[BSP_POWER_ADC_CHANNEL_COUNT];

void BSP_PowerBoard_Init(void);
void BSP_PowerBoard_StartAdcDma(void);
void BSP_PowerBoard_StartPwmTimebase(void);
void BSP_PowerBoard_StartFanPwm(void);
void BSP_PowerBoard_EnablePowerPwm(void);
void BSP_PowerBoard_DisablePowerPwm(void);
void BSP_PowerBoard_SetBuckCompare(uint16_t compare);
void BSP_PowerBoard_SetBoostCompare(uint16_t compare);
void BSP_PowerBoard_SetAdcTriggerCompare(uint16_t compare);
void BSP_PowerBoard_SetFanPwm(uint16_t pwm);
uint16_t BSP_PowerBoard_GetRawAdc(uint8_t index);
float BSP_PowerBoard_AdcToVoltage(uint16_t raw);
float BSP_PowerBoard_AdcToCurrent(uint16_t raw);
float BSP_PowerBoard_ReadBoardTemperatureC(void);
float BSP_PowerBoard_ReadCpuTemperatureC(void);

#ifdef __cplusplus
}
#endif

#endif
