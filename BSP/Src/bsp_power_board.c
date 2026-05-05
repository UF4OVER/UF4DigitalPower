#include "bsp_power_board.h"

#include "adc.h"
#include "hrtim.h"
#include "tim.h"

#include <math.h>

#define BSP_POWER_TEMP_CAL_30C ((float)(*(__IO uint16_t *)0x1FFF75A8U))
#define BSP_POWER_TEMP_CAL_130C ((float)(*(__IO uint16_t *)0x1FFF75CAU))

volatile uint16_t g_bsp_power_adc_dma[BSP_POWER_ADC_CHANNEL_COUNT] = {0U};

static float bsp_clampf(float value, float min_value, float max_value)
{
    if (value < min_value)
    {
        return min_value;
    }
    if (value > max_value)
    {
        return max_value;
    }
    return value;
}

void BSP_PowerBoard_Init(void)
{
    (void)HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);
    (void)HAL_ADCEx_Calibration_Start(&hadc2, ADC_SINGLE_ENDED);
    (void)HAL_ADCEx_Calibration_Start(&hadc5, ADC_SINGLE_ENDED);

    BSP_PowerBoard_StartAdcDma();
    BSP_PowerBoard_StartPwmTimebase();
    BSP_PowerBoard_StartFanPwm();
    BSP_PowerBoard_DisablePowerPwm();
}

void BSP_PowerBoard_StartAdcDma(void)
{
    (void)HAL_ADC_Start_DMA(&hadc1, (uint32_t *)g_bsp_power_adc_dma, BSP_POWER_ADC_CHANNEL_COUNT);
}

void BSP_PowerBoard_StartPwmTimebase(void)
{
    (void)HAL_HRTIM_WaveformCountStart_IT(&hhrtim1, HRTIM_TIMERID_TIMER_A);
    (void)HAL_HRTIM_WaveformCountStart(&hhrtim1, HRTIM_TIMERID_TIMER_D);
}

void BSP_PowerBoard_StartFanPwm(void)
{
    (void)HAL_TIM_PWM_Start(&htim8, TIM_CHANNEL_3);
}

void BSP_PowerBoard_EnablePowerPwm(void)
{
    (void)HAL_HRTIM_WaveformOutputStart(&hhrtim1, HRTIM_OUTPUT_TA1 | HRTIM_OUTPUT_TA2);
    (void)HAL_HRTIM_WaveformOutputStart(&hhrtim1, HRTIM_OUTPUT_TD1 | HRTIM_OUTPUT_TD2);
}

void BSP_PowerBoard_DisablePowerPwm(void)
{
    (void)HAL_HRTIM_WaveformOutputStop(&hhrtim1, HRTIM_OUTPUT_TA1 | HRTIM_OUTPUT_TA2);
    (void)HAL_HRTIM_WaveformOutputStop(&hhrtim1, HRTIM_OUTPUT_TD1 | HRTIM_OUTPUT_TD2);
    BSP_PowerBoard_SetBuckCompare(BSP_POWER_HRTIM_PERIOD);
    BSP_PowerBoard_SetBoostCompare(BSP_POWER_MIN_BOOST_DUTY);
}

void BSP_PowerBoard_SetBuckCompare(uint16_t compare)
{
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_1, compare);
}

void BSP_PowerBoard_SetBoostCompare(uint16_t compare)
{
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_D, HRTIM_COMPAREUNIT_1, compare);
}

void BSP_PowerBoard_SetAdcTriggerCompare(uint16_t compare)
{
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_3, compare);
}

void BSP_PowerBoard_SetFanPwm(uint16_t pwm)
{
    if (pwm > 1000U)
    {
        pwm = 1000U;
    }
    __HAL_TIM_SET_COMPARE(&htim8, TIM_CHANNEL_3, pwm);
}

uint16_t BSP_PowerBoard_GetRawAdc(uint8_t index)
{
    if (index >= BSP_POWER_ADC_CHANNEL_COUNT)
    {
        return 0U;
    }
    return g_bsp_power_adc_dma[index];
}

float BSP_PowerBoard_AdcToVoltage(uint16_t raw)
{
    return ((float)raw * BSP_POWER_VREF * BSP_POWER_VOLTAGE_DIVIDER_RATIO) / BSP_POWER_ADC_MAX_VALUE;
}

float BSP_PowerBoard_AdcToCurrent(uint16_t raw)
{
    float voltage = ((float)raw * BSP_POWER_VREF) / BSP_POWER_ADC_MAX_VALUE;
    return (voltage - BSP_POWER_CURRENT_ZERO_V) /
           (BSP_POWER_CURRENT_GAIN * BSP_POWER_CURRENT_SHUNT_OHM);
}

float BSP_PowerBoard_ReadBoardTemperatureC(void)
{
    uint32_t raw;
    float voltage;
    float ratio;

    (void)HAL_ADC_Start(&hadc2);
    (void)HAL_ADC_PollForConversion(&hadc2, 2U);
    raw = HAL_ADC_GetValue(&hadc2);

    voltage = ((float)raw * BSP_POWER_VREF) / 4095.0F;
    voltage = bsp_clampf(voltage, 0.05F, 3.25F);
    ratio = (BSP_POWER_VREF / voltage) - 1.0F;
    ratio = bsp_clampf(ratio, 0.01F, 1000.0F);

    return (1.0F / ((1.0F / 298.15F) + logf(ratio) / 3950.0F)) - 273.15F;
}

float BSP_PowerBoard_ReadCpuTemperatureC(void)
{
    float raw;

    (void)HAL_ADC_Start(&hadc5);
    (void)HAL_ADC_PollForConversion(&hadc5, 2U);
    raw = (float)HAL_ADC_GetValue(&hadc5);

    return (((raw - BSP_POWER_TEMP_CAL_30C) * (130.0F - 30.0F)) /
            (BSP_POWER_TEMP_CAL_130C - BSP_POWER_TEMP_CAL_30C)) +
           30.0F;
}
