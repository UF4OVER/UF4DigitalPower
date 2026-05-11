/**
 * @file    : bsp_board_.h
 * @brief   : TODO: 请填写模块功能简介
 * @author  : UF4
 * @date    : 2026/5/11 18:38
 * @version : CLion
 * @project : UF4DigitalPower
 * @details : 
 * TODO: 请填写详细说明
 */

#ifndef UF4DIGITALPOWER_BSP_BOARD__H
#define UF4DIGITALPOWER_BSP_BOARD__H

#include <stdint.h>

#define ADC_MAX_VALUE 8190.0F
#define ADC_REF_VOLTAGE 3.3F
#define REF_3V3 ADC_REF_VOLTAGE
#define BSP_ADC_OVERSAMPLED_MAX_VALUE 65520.0F

#define BSP_INPUT_VOLTAGE_R_HIGH_OHM 75_000.0F
#define BSP_INPUT_VOLTAGE_R_LOW_OHM  5_560.0F

#define BSP_OUTPUT_VOLTAGE_R_HIGH_OHM 75_000.0F
#define BSP_OUTPUT_VOLTAGE_R_LOW_OHM  5_560.0F

#define INPUT_VOLTAGE_DIVIDER_GAIN  (BSP_INPUT_VOLTAGE_R_HIGH_OHM / BSP_INPUT_VOLTAGE_R_LOW_OHM)
#define OUTPUT_VOLTAGE_DIVIDER_GAIN (BSP_OUTPUT_VOLTAGE_R_HIGH_OHM / BSP_OUTPUT_VOLTAGE_R_LOW_OHM)
#define VOLTAGE_DIVIDER_GAIN OUTPUT_VOLTAGE_DIVIDER_GAIN

#define INPUT_CURRENT_SHUNT_OHM 0.008F
#define OUTPUT_CURRENT_SHUNT_OHM 0.008F

#define INPUT_CURRENT_AMP_GAIN 20.0F
#define OUTPUT_CURRENT_AMP_GAIN 20.0F

#define CURRENT_SHUNT_OHM OUTPUT_CURRENT_SHUNT_OHM
#define CURRENT_AMP_GAIN OUTPUT_CURRENT_AMP_GAIN

#define CURRENT_ADC_ZERO_V 1.65F
#define CURRENT_SENSE_GAIN (CURRENT_SHUNT_OHM * CURRENT_AMP_GAIN)
#define INPUT_CURRENT_SENSE_GAIN (INPUT_CURRENT_SHUNT_OHM * INPUT_CURRENT_AMP_GAIN)
#define OUTPUT_CURRENT_SENSE_GAIN (OUTPUT_CURRENT_SHUNT_OHM * OUTPUT_CURRENT_AMP_GAIN)
#define CURRENT_FORWARD_DEADBAND_A 0.02F
#define INPUT_CURRENT_ADC_ZERO_V CURRENT_ADC_ZERO_V
#define OUTPUT_CURRENT_ADC_ZERO_V CURRENT_ADC_ZERO_V
#define INPUT_CURRENT_POLARITY (-1.0F)
#define OUTPUT_CURRENT_POLARITY (-1.0F)

#define CAL_VOUT_K 4099
#define CAL_VOUT_B 1
#define CAL_IOUT_K 4095
#define CAL_IOUT_B 1

#define TS_CAL1 (*(volatile uint16_t *)0x1FFF75A8)
#define TS_CAL2 (*(volatile uint16_t *)0x1FFF75CA)

#define TS_CAL1_TEMP 30.0F
#define TS_CAL2_TEMP 130.0F

#define BSP_NTC_PULLUP_OHM 10000.0F
#define BSP_NTC_R25_OHM 10000.0F

#define BSP_NTC_B_VALUE 3950.0F
#define BSP_NTC_T0_KELVIN (273.15F + 25.0F)
#define BSP_KELVIN_OFFSET 273.15F

float UF4_AdcToVoltage(uint32_t adc);
float UF4_AdcToInputVoltage(uint32_t adc);
float UF4_AdcToOutputVoltage(uint32_t adc);
float UF4_AdcToCurrent(uint32_t adc);
float UF4_AdcToInputCurrent(uint32_t adc);
float UF4_AdcToOutputCurrent(uint32_t adc);

uint32_t UF4_VoltageToAdc(float voltage);
uint32_t UF4_InputVoltageToAdc(float voltage);
uint32_t UF4_OutputVoltageToAdc(float voltage);
uint32_t UF4_CurrentToAdc(float current);

float GET_NTC_Temperature(void);
float GET_CPU_Temperature(void);
void FAN_PWM_set(uint16_t dutyCycle);
void Auto_FAN(void);
void UF4_BoardSetRunLed(uint8_t enabled);
void UF4_BoardSetStatusLed(uint8_t enabled);
void UF4_BoardToggleStatusLed(void);

#ifdef __cplusplus
extern "C" {
#endif

#ifdef __cplusplus
}
#endif

#endif /* UF4DIGITALPOWER_BSP_BOARD__H */