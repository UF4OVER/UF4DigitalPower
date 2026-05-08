#ifndef USER_POWER_CFG_H
#define USER_POWER_CFG_H

/* ADC and sensor conversion constants from README assumptions. */
#define USER_PWR_ADC_VREF_V                3.285f
/* ADC1 uses oversampling ratio 4 + right shift 1, effective full-scale is 8190. */
#define USER_PWR_ADC_MAX_COUNT             8190.0f
#define USER_PWR_VOLTAGE_SCALE             75.0f/5.6f

#define USER_PWR_SHUNT_RES_OHM             0.008f
#define USER_PWR_CURRENT_GAIN              20.0f
#define USER_PWR_CURRENT_ZERO_V            1.65f
#define USER_PWR_IIN_ZERO_V                USER_PWR_CURRENT_ZERO_V
#define USER_PWR_IOUT_ZERO_V               USER_PWR_CURRENT_ZERO_V
#define USER_PWR_CURRENT_SCALE             (USER_PWR_SHUNT_RES_OHM * USER_PWR_CURRENT_GAIN)

#define USER_PWR_IIN_CAL_GAIN              1.00f
#define USER_PWR_IOUT_CAL_GAIN             1.00f

#define USER_PWR_CURRENT_DEADBAND_V        0.0065f
#define USER_PWR_MEAS_FILTER_ALPHA         0.15f

/* Control and protection defaults (single-direction first). */
#define USER_PWR_DEFAULT_VOUT_V            5.0f
#define USER_PWR_DEFAULT_IOUT_A            0.5f
#define USER_PWR_DEFAULT_OVP_V             44.0f
#define USER_PWR_DEFAULT_OCP_A             10.0f
#define USER_PWR_DEFAULT_OTP_C             80.0f
#define USER_PWR_DEFAULT_INPUT_UVP_V       6.0f
#define USER_PWR_DEFAULT_INPUT_OVP_V       45.0f
#define USER_PWR_DEFAULT_POWER_ENABLED     1U
#define USER_PWR_DEFAULT_FAN_VALUE         500U

/* The MCU may stay powered while the power input is hot-plugged.
 * Do not start conversion until VIN is safely above this threshold. */
#define USER_PWR_INPUT_START_MIN_V         7.0f
#define USER_PWR_INPUT_CURRENT_LIMIT_A     3.0f
#define USER_PWR_INPUT_DROOP_FOLDBACK_V    8.0f
#define USER_PWR_INPUT_UVP_FAULT_TICKS     2000U
#define USER_PWR_INPUT_UVP_RECOVER_MARGIN_V 0.3f

/* Board temperature NTC divider on ADC_TEMP(PA4):
 * 3.3V -> 10K B3380 NTC -> PA4 -> 10K resistor -> GND. */
#define USER_PWR_BOARD_NTC_R0_OHM          10000.0f
#define USER_PWR_BOARD_NTC_BETA            3380.0f
#define USER_PWR_BOARD_NTC_T0_K            298.15f
#define USER_PWR_BOARD_PULLDOWN_OHM        10000.0f

#define USER_PWR_VOLTAGE_KP                0.025f
#define USER_PWR_VOLTAGE_KI                0.00008f
#define USER_PWR_CURRENT_KP                1.2f
#define USER_PWR_CURRENT_KI                0.02f
#define USER_PWR_CC_ENTER_MARGIN_A         0.03f
#define USER_PWR_CC_EXIT_MARGIN_A          0.08f
#define USER_PWR_CC_VREF_RISE_STEP_V       0.05f
#define USER_PWR_CC_VREF_FALL_STEP_V       0.25f
#define USER_PWR_CC_MODE_VREF_MARGIN_V     0.05f

#define USER_PWR_CONTROL_DIVIDER_TICKS     50U
#define USER_PWR_DUTY_MIN                  0.01f
#define USER_PWR_DUTY_MAX                  0.95f
#define USER_PWR_DUTY_BOOTSTRAP            0.05f
#define USER_PWR_RISE_DUTY_START           0.01f
#define USER_PWR_RISE_DUTY_STEP            0.005f
#define USER_PWR_RISE_DUTY_MAX             0.85f
#define USER_PWR_RISE_DUTY_MARGIN          0.08f
#define USER_PWR_SOFTSTART_STEP_V          0.05f

#define USER_PWR_SHORT_VOUT_V              0.5f
#define USER_PWR_SHORT_DETECT_DELAY_TICKS  2000U

#endif
