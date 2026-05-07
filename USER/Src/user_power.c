#include "../Inc/user_power.h"

#include "../Inc/user_power_cfg.h"
#include "../Inc/user_power_pwm.h"
#include "../Inc/user_power_store.h"
#include "../Inc/user_tvlcom.h"

#include "adc.h"
#include "hrtim.h"
#include "tim.h"

#include <math.h>
#include <string.h>

static user_power_config_t g_user_config;
static user_power_status_t g_user_status;
static volatile uint16_t *g_adc_result = NULL;
static uint8_t g_save_pending = 0U;
static uint16_t g_softstart_tick = 0U;
static uint16_t g_voltage_loop_divider = 0U;
static uint16_t g_fast_state_divider = 0U;
static uint16_t g_input_uvp_fault_ticks = 0U;
static uint8_t g_measurement_ready = 0U;
static uint8_t g_aux_measurement_ready = 0U;
static uint32_t g_aux_sample_tick = 0U;
static uint32_t g_background_1ms_tick = 0U;
static float g_iin_zero_v = USER_PWR_CURRENT_ZERO_V;
static float g_iout_zero_v = USER_PWR_CURRENT_ZERO_V;
static float g_control_duty = USER_PWR_DUTY_MIN;
static float g_voltage_ref_v = 0.0f;

static float user_pwr_clamp(float value, float min_value, float max_value)
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

static void user_pwr_pid_reset(user_power_pid_t *pid)
{
    pid->integral = 0.0f;
    pid->prev_error = 0.0f;
    pid->prev_measurement = 0.0f;
}

static void user_pwr_control_reset(void)
{
    g_control_duty = USER_PWR_DUTY_MIN;
    g_voltage_loop_divider = 0U;
    g_input_uvp_fault_ticks = 0U;
    user_pwr_pid_reset(&g_user_config.voltage_pid);
    user_pwr_pid_reset(&g_user_config.current_pid);
    g_user_status.current_ref_a = 0.0f;
}

static void user_pwr_seed_voltage_ref(float start_v)
{
    g_voltage_ref_v = user_pwr_clamp(start_v, 0.0f, 33.0f);
}

static void user_pwr_slew_voltage_ref(void)
{
    float target = g_user_config.target_voltage_v;

    if (g_voltage_ref_v < target)
    {
        g_voltage_ref_v += USER_PWR_SOFTSTART_STEP_V;
        if (g_voltage_ref_v > target)
        {
            g_voltage_ref_v = target;
        }
    }
    else if (g_voltage_ref_v > target)
    {
        g_voltage_ref_v -= USER_PWR_SOFTSTART_STEP_V;
        if (g_voltage_ref_v < target)
        {
            g_voltage_ref_v = target;
        }
    }
}

static uint8_t user_pwr_voltage_ref_at_target(void)
{
    float error = g_voltage_ref_v - g_user_config.target_voltage_v;

    return (error < USER_PWR_SOFTSTART_STEP_V) &&
           (error > -USER_PWR_SOFTSTART_STEP_V);
}

static void user_pwr_set_defaults(void)
{
    memset(&g_user_config, 0, sizeof(g_user_config));
    memset(&g_user_status, 0, sizeof(g_user_status));

    g_user_config.target_voltage_v = USER_PWR_DEFAULT_VOUT_V;
    g_user_config.target_current_a = USER_PWR_DEFAULT_IOUT_A;
    g_user_config.ovp_v = USER_PWR_DEFAULT_OVP_V;
    g_user_config.ocp_a = USER_PWR_DEFAULT_OCP_A;
    g_user_config.otp_c = USER_PWR_DEFAULT_OTP_C;
    g_user_config.input_uvp_v = USER_PWR_DEFAULT_INPUT_UVP_V;
    g_user_config.input_ovp_v = USER_PWR_DEFAULT_INPUT_OVP_V;
    g_user_config.fan_set_value = USER_PWR_DEFAULT_FAN_VALUE;
    g_user_config.power_enabled = USER_PWR_DEFAULT_POWER_ENABLED;

    g_user_config.voltage_pid.kp = USER_PWR_VOLTAGE_KP;
    g_user_config.voltage_pid.ki = USER_PWR_VOLTAGE_KI;
    g_user_config.voltage_pid.kd = 0.0f;
    g_user_config.voltage_pid.out_min = 0.0f;
    g_user_config.voltage_pid.out_max = USER_PWR_DEFAULT_OCP_A;

    g_user_config.current_pid.kp = USER_PWR_CURRENT_KP;
    g_user_config.current_pid.ki = USER_PWR_CURRENT_KI;
    g_user_config.current_pid.kd = 0.0f;
    g_user_config.current_pid.out_min = USER_PWR_DUTY_MIN;
    g_user_config.current_pid.out_max = USER_PWR_DUTY_MAX;

    user_pwr_control_reset();

    g_user_status.state = USER_POWER_STATE_INIT;
    g_user_status.topology = USER_POWER_TOPOLOGY_NA;
    g_user_status.regulation_mode = USER_POWER_MODE_CV;
}

static float user_pwr_adc_to_voltage(uint16_t adc)
{
    float vadc = ((float)adc * USER_PWR_ADC_VREF_V) / USER_PWR_ADC_MAX_COUNT;
    return vadc * USER_PWR_VOLTAGE_SCALE;
}

static float user_pwr_adc_to_sensor_voltage(uint16_t adc)
{
    return ((float)adc * USER_PWR_ADC_VREF_V) / USER_PWR_ADC_MAX_COUNT;
}

static float user_pwr_sensor_voltage_to_current(float sensor_v, float zero_v)
{
    return (sensor_v - zero_v) / USER_PWR_CURRENT_SCALE;
}

static float user_pwr_lpf(float prev, float input)
{
    const float alpha = 0.15f;
    return prev + alpha * (input - prev);
}

static void user_pwr_update_measurements(void)
{
    float iin_sensor_v;
    float iout_sensor_v;
    float iin;
    float iout;
    float vin_v;
    float vout_v;

    if (g_adc_result == NULL)
    {
        return;
    }

    /* CubeMX ADC1 DMA order: [0]=VIN, [1]=IIN, [2]=VOUT, [3]=IOUT */
    g_user_status.raw_adc[0] = g_adc_result[0];
    g_user_status.raw_adc[1] = g_adc_result[1];
    g_user_status.raw_adc[2] = g_adc_result[2];
    g_user_status.raw_adc[3] = g_adc_result[3];

    vin_v = user_pwr_adc_to_voltage(g_adc_result[0]);
    vout_v = user_pwr_adc_to_voltage(g_adc_result[2]);

    iin_sensor_v = user_pwr_adc_to_sensor_voltage(g_adc_result[1]);
    iout_sensor_v = user_pwr_adc_to_sensor_voltage(g_adc_result[3]);

    /* Track current-sense zero whenever PWM is not delivering power. */
    if ((g_user_config.power_enabled == 0U) ||
        ((g_user_status.state != USER_POWER_STATE_RISE) &&
         (g_user_status.state != USER_POWER_STATE_RUN)))
    {
        g_iin_zero_v = g_iin_zero_v + 0.02f * (iin_sensor_v - g_iin_zero_v);
        g_iout_zero_v = g_iout_zero_v + 0.02f * (iout_sensor_v - g_iout_zero_v);
    }

    iin = user_pwr_sensor_voltage_to_current(iin_sensor_v, g_iin_zero_v);
    iout = user_pwr_sensor_voltage_to_current(iout_sensor_v, g_iout_zero_v);

    if (g_measurement_ready == 0U)
    {
        g_user_status.vin_v = vin_v;
        g_user_status.vout_v = vout_v;
        g_user_status.iin_a = user_pwr_clamp(iin, -12.0f, 12.0f);
        g_user_status.iout_a = user_pwr_clamp(iout, -12.0f, 12.0f);
        g_measurement_ready = 1U;
        return;
    }

    g_user_status.vin_v = user_pwr_lpf(g_user_status.vin_v, vin_v);
    g_user_status.vout_v = user_pwr_lpf(g_user_status.vout_v, vout_v);
    g_user_status.iin_a = user_pwr_lpf(g_user_status.iin_a, user_pwr_clamp(iin, -12.0f, 12.0f));
    g_user_status.iout_a = user_pwr_lpf(g_user_status.iout_a, user_pwr_clamp(iout, -12.0f, 12.0f));
}

static uint8_t user_pwr_input_ready(void)
{
    float start_min_v = user_pwr_clamp(USER_PWR_INPUT_START_MIN_V,
                                       g_user_config.input_uvp_v,
                                       g_user_config.input_ovp_v);

    return (g_measurement_ready != 0U) &&
           (g_user_status.vin_v >= start_min_v) &&
           (g_user_status.vin_v <= g_user_config.input_ovp_v);
}

static uint8_t user_pwr_has_only_input_fault(void)
{
    const uint16_t input_faults = USER_POWER_FAULT_INPUT_UNDER_VOLTAGE |
                                  USER_POWER_FAULT_INPUT_OVER_VOLTAGE;

    return (g_user_status.fault_mask != 0U) &&
           ((g_user_status.fault_mask & (uint16_t)~input_faults) == 0U);
}

static float user_pwr_board_temp_from_adc(uint16_t adc)
{
    float ratio;
    float ntc_ohm;
    float temp_k;

    if (adc == 0U)
    {
        return -40.0f;
    }
    if (adc >= 4095U)
    {
        return 150.0f;
    }

    ratio = (float)adc / 4095.0f;
    ntc_ohm = USER_PWR_BOARD_PULLDOWN_OHM * ((1.0f / ratio) - 1.0f);
    temp_k = 1.0f / ((1.0f / USER_PWR_BOARD_NTC_T0_K) +
                     (logf(ntc_ohm / USER_PWR_BOARD_NTC_R0_OHM) / USER_PWR_BOARD_NTC_BETA));

    return temp_k - 273.15f;
}

static uint16_t user_pwr_adc2_oversampled_to_12bit(uint32_t raw)
{
    raw = (raw + 8U) / 16U;
    return raw > 4095U ? 4095U : (uint16_t)raw;
}

static uint16_t user_pwr_adc5_oversampled_to_12bit(uint32_t raw)
{
    raw = (raw + 4U) / 8U;
    return raw > 4095U ? 4095U : (uint16_t)raw;
}

static uint8_t user_pwr_adc_read_blocking(ADC_HandleTypeDef *hadc, uint32_t *value)
{
    if ((hadc == NULL) || (value == NULL))
    {
        return 0U;
    }

    if (HAL_ADC_Start(hadc) != HAL_OK)
    {
        return 0U;
    }

    if (HAL_ADC_PollForConversion(hadc, 2U) != HAL_OK)
    {
        (void)HAL_ADC_Stop(hadc);
        return 0U;
    }

    *value = HAL_ADC_GetValue(hadc);
    (void)HAL_ADC_Stop(hadc);
    return 1U;
}

static void user_pwr_apply_fan_value(uint32_t value)
{
    uint32_t clamped = value > 1000U ? 1000U : value;

    g_user_config.fan_set_value = clamped;
    g_user_status.fan_speed = clamped;
    __HAL_TIM_SET_COMPARE(&htim8, TIM_CHANNEL_3, clamped);
}

static void user_pwr_update_aux_measurements(void)
{
    uint32_t raw;
    uint16_t raw_12bit;
    int32_t core_temp_c;
    uint8_t updated = 0U;
    float board_temp_c = g_user_status.board_temp_c;
    float mcu_temp_c = g_user_status.core_temp_c;

    if (user_pwr_adc_read_blocking(&hadc2, &raw) != 0U)
    {
        raw_12bit = user_pwr_adc2_oversampled_to_12bit(raw);
        board_temp_c = user_pwr_board_temp_from_adc(raw_12bit);
        updated = 1U;
    }

    if (user_pwr_adc_read_blocking(&hadc5, &raw) != 0U)
    {
        raw_12bit = user_pwr_adc5_oversampled_to_12bit(raw);
        core_temp_c = __HAL_ADC_CALC_TEMPERATURE(3300UL, raw_12bit, ADC_RESOLUTION_12B);
        if (core_temp_c != LL_ADC_TEMPERATURE_CALC_ERROR)
        {
            mcu_temp_c = (float)core_temp_c;
            updated = 1U;
        }
    }

    if (updated == 0U)
    {
        return;
    }

    if (g_aux_measurement_ready == 0U)
    {
        g_user_status.board_temp_c = board_temp_c;
        g_user_status.core_temp_c = mcu_temp_c;
        g_aux_measurement_ready = 1U;
        return;
    }

    g_user_status.board_temp_c = user_pwr_lpf(g_user_status.board_temp_c, board_temp_c);
    g_user_status.core_temp_c = user_pwr_lpf(g_user_status.core_temp_c, mcu_temp_c);
}

static void user_pwr_select_topology(float vref)
{
    float vin = g_user_status.vin_v;
    user_power_topology_t previous = g_user_status.topology;

    if (vin < 0.5f)
    {
        g_user_status.topology = USER_POWER_TOPOLOGY_NA;
        return;
    }

    switch (g_user_status.topology)
    {
    case USER_POWER_TOPOLOGY_BUCK:
        if (vref > (vin * 1.2f))
        {
            g_user_status.topology = USER_POWER_TOPOLOGY_BOOST;
        }
        else if (vref > (vin * 0.85f))
        {
            g_user_status.topology = USER_POWER_TOPOLOGY_MIX;
        }
        break;
    case USER_POWER_TOPOLOGY_BOOST:
        if (vref < (vin * 0.8f))
        {
            g_user_status.topology = USER_POWER_TOPOLOGY_BUCK;
        }
        else if (vref < (vin * 1.15f))
        {
            g_user_status.topology = USER_POWER_TOPOLOGY_MIX;
        }
        break;
    case USER_POWER_TOPOLOGY_MIX:
        if (vref < (vin * 0.8f))
        {
            g_user_status.topology = USER_POWER_TOPOLOGY_BUCK;
        }
        else if (vref > (vin * 1.2f))
        {
            g_user_status.topology = USER_POWER_TOPOLOGY_BOOST;
        }
        break;
    default:
        if (vref < (vin * 0.8f))
        {
            g_user_status.topology = USER_POWER_TOPOLOGY_BUCK;
        }
        else if (vref > (vin * 1.2f))
        {
            g_user_status.topology = USER_POWER_TOPOLOGY_BOOST;
        }
        else
        {
            g_user_status.topology = USER_POWER_TOPOLOGY_MIX;
        }
        break;
    }

    if (previous != g_user_status.topology)
    {
        g_user_config.voltage_pid.integral *= 0.5f;
        g_user_config.voltage_pid.prev_error = 0.0f;
    }
}

static void user_pwr_set_fault(uint16_t fault)
{
    g_user_status.fault_mask |= fault;
    g_user_status.state = USER_POWER_STATE_ERR;
    UserPowerPwm_Stop(&g_user_status);
}

static void user_pwr_protection_fast_check(void)
{
    if ((g_user_status.state != USER_POWER_STATE_RISE) && (g_user_status.state != USER_POWER_STATE_RUN))
    {
        g_input_uvp_fault_ticks = 0U;
        return;
    }

    if (g_user_status.vin_v < g_user_config.input_uvp_v)
    {
        if (g_input_uvp_fault_ticks < USER_PWR_INPUT_UVP_FAULT_TICKS)
        {
            g_input_uvp_fault_ticks++;
        }
        if (g_input_uvp_fault_ticks >= USER_PWR_INPUT_UVP_FAULT_TICKS)
        {
            user_pwr_set_fault(USER_POWER_FAULT_INPUT_UNDER_VOLTAGE);
            return;
        }
    }
    else if (g_user_status.vin_v > (g_user_config.input_uvp_v + USER_PWR_INPUT_UVP_RECOVER_MARGIN_V))
    {
        g_input_uvp_fault_ticks = 0U;
    }

    if (g_user_status.vin_v > g_user_config.input_ovp_v)
    {
        user_pwr_set_fault(USER_POWER_FAULT_INPUT_OVER_VOLTAGE);
        return;
    }

    if (g_user_status.vout_v > g_user_config.ovp_v)
    {
        user_pwr_set_fault(USER_POWER_FAULT_OUTPUT_OVER_VOLTAGE);
        return;
    }

    if ((g_user_status.iout_a > g_user_config.ocp_a) || (g_user_status.iout_a < -g_user_config.ocp_a))
    {
        user_pwr_set_fault(USER_POWER_FAULT_OUTPUT_OVER_CURRENT);
        return;
    }

    if ((g_user_status.state == USER_POWER_STATE_RUN) &&
        (g_softstart_tick > USER_PWR_SHORT_DETECT_DELAY_TICKS) &&
        (g_user_status.vout_v < USER_PWR_SHORT_VOUT_V) &&
        (g_user_status.iout_a > (g_user_config.ocp_a * 0.6f)))
    {
        user_pwr_set_fault(USER_POWER_FAULT_OUTPUT_SHORT);
    }
}

static float user_pwr_pi_step(user_power_pid_t *pid, float setpoint, float measurement)
{
    float error = setpoint - measurement;
    float out;

    pid->integral += pid->ki * error;
    pid->integral = user_pwr_clamp(pid->integral, pid->out_min, pid->out_max);

    out = (pid->kp * error) + pid->integral;
    out = user_pwr_clamp(out, pid->out_min, pid->out_max);

    if (((out >= pid->out_max) && (error > 0.0f)) || ((out <= pid->out_min) && (error < 0.0f)))
    {
        pid->integral -= pid->ki * error;
        pid->integral = user_pwr_clamp(pid->integral, pid->out_min, pid->out_max);
    }

    return out;
}

static void user_pwr_fast_control_loop(void)
{
    float vref;
    float error;
    float duty_ff;
    float duty;
    float duty_max = USER_PWR_DUTY_MAX;
    float input_limit_a = USER_PWR_INPUT_CURRENT_LIMIT_A;

    if ((g_user_status.state != USER_POWER_STATE_RISE) && (g_user_status.state != USER_POWER_STATE_RUN))
    {
        UserPowerPwm_ApplyDuty(USER_POWER_TOPOLOGY_NA, USER_PWR_DUTY_MIN, &g_user_status);
        g_control_duty = USER_PWR_DUTY_MIN;
        return;
    }

    vref = g_voltage_ref_v;
    user_pwr_select_topology(vref);

    vref = user_pwr_clamp(vref, 0.0f, g_user_config.target_voltage_v > 0.0f ? 33.0f : 0.0f);

    if (g_user_status.state == USER_POWER_STATE_RISE)
    {
        float target_duty_need = USER_PWR_RISE_DUTY_MAX;

        if (g_user_status.vin_v > 0.5f)
        {
            if (g_user_status.topology == USER_POWER_TOPOLOGY_BUCK)
            {
                target_duty_need = (vref / g_user_status.vin_v) + USER_PWR_RISE_DUTY_MARGIN;
            }
            else if (vref > g_user_status.vin_v)
            {
                target_duty_need = 1.0f - (g_user_status.vin_v / user_pwr_clamp(vref, 1.0f, 60.0f)) + USER_PWR_RISE_DUTY_MARGIN;
            }
            else
            {
                target_duty_need = USER_PWR_RISE_DUTY_START;
            }
        }

        duty_max = USER_PWR_RISE_DUTY_START + ((float)g_softstart_tick * USER_PWR_RISE_DUTY_STEP);
        duty_max = user_pwr_clamp(duty_max,
                                  USER_PWR_RISE_DUTY_START,
                                  user_pwr_clamp(target_duty_need, USER_PWR_RISE_DUTY_START, USER_PWR_RISE_DUTY_MAX));
        input_limit_a *= 0.6f;
    }

    error = vref - g_user_status.vout_v;

    if (g_user_status.vin_v < 0.5f)
    {
        g_control_duty = USER_PWR_DUTY_MIN;
        UserPowerPwm_ApplyDuty(USER_POWER_TOPOLOGY_NA, USER_PWR_DUTY_MIN, &g_user_status);
        return;
    }

    if (g_user_status.topology == USER_POWER_TOPOLOGY_BUCK)
    {
        duty_ff = vref / g_user_status.vin_v;
    }
    else if (g_user_status.topology == USER_POWER_TOPOLOGY_BOOST)
    {
        duty_ff = 1.0f - (g_user_status.vin_v / user_pwr_clamp(vref, 1.0f, 60.0f));
    }
    else
    {
        if (vref > g_user_status.vin_v)
        {
            duty_ff = 1.0f - (g_user_status.vin_v / user_pwr_clamp(vref, 1.0f, 60.0f));
        }
        else
        {
            duty_ff = USER_PWR_DUTY_MIN;
        }
    }

    if (++g_voltage_loop_divider >= USER_PWR_CONTROL_DIVIDER_TICKS)
    {
        g_voltage_loop_divider = 0U;
        g_user_config.voltage_pid.integral += g_user_config.voltage_pid.ki * error;
        g_user_config.voltage_pid.integral = user_pwr_clamp(g_user_config.voltage_pid.integral, -0.2f, 0.2f);
        g_user_config.voltage_pid.prev_error = error;
    }

    duty = duty_ff + (g_user_config.voltage_pid.kp * error) + g_user_config.voltage_pid.integral;

    if ((g_user_status.iin_a > input_limit_a) || (g_user_status.iout_a > g_user_config.target_current_a))
    {
        duty -= 0.02f;
        g_user_config.voltage_pid.integral *= 0.95f;
    }

    if (g_user_status.vin_v < USER_PWR_INPUT_DROOP_FOLDBACK_V)
    {
        duty -= 0.03f;
        g_user_config.voltage_pid.integral *= 0.9f;
    }

    g_control_duty = user_pwr_clamp(duty, USER_PWR_DUTY_MIN, duty_max);

    g_user_status.current_ref_a = g_user_config.target_current_a;
    g_user_status.duty_cmd = g_control_duty;
    g_user_status.regulation_mode = USER_POWER_MODE_CV;
    UserPowerPwm_ApplyDuty(g_user_status.topology, g_control_duty, &g_user_status);
}

void UserPower_Init(volatile uint16_t *adc_dma_buffer)
{
    g_adc_result = adc_dma_buffer;
    g_save_pending = 0U;
    g_softstart_tick = 0U;
    g_voltage_loop_divider = 0U;
    g_fast_state_divider = 0U;
    g_measurement_ready = 0U;
    g_aux_measurement_ready = 0U;
    g_aux_sample_tick = 0U;
    g_background_1ms_tick = 0U;
    g_iin_zero_v = USER_PWR_CURRENT_ZERO_V;
    g_iout_zero_v = USER_PWR_CURRENT_ZERO_V;
    g_voltage_ref_v = 0.0f;

    user_pwr_set_defaults();

    (void)HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);
    (void)HAL_ADCEx_Calibration_Start(&hadc2, ADC_SINGLE_ENDED);
    (void)HAL_ADCEx_Calibration_Start(&hadc5, ADC_SINGLE_ENDED);

    (void)HAL_ADC_Start_DMA(&hadc1, (uint32_t *)g_adc_result, USER_POWER_ADC_CHANNEL_COUNT);
    (void)HAL_HRTIM_WaveformCountStart_IT(&hhrtim1, HRTIM_TIMERID_TIMER_A);
    (void)HAL_HRTIM_WaveformCountStart(&hhrtim1, HRTIM_TIMERID_TIMER_D);
    (void)HAL_TIM_Base_Start_IT(&htim2);
    (void)HAL_TIM_Base_Start_IT(&htim3);
    (void)HAL_TIM_Base_Start_IT(&htim4);
    (void)HAL_TIM_PWM_Start(&htim8, TIM_CHANNEL_3);

    (void)UserPowerStore_Init();
    UserPowerStore_Load(&g_user_config);
    user_pwr_apply_fan_value(g_user_config.fan_set_value);

    g_user_config.voltage_pid.kp = USER_PWR_VOLTAGE_KP;
    g_user_config.voltage_pid.ki = USER_PWR_VOLTAGE_KI;
    g_user_config.current_pid.kp = USER_PWR_CURRENT_KP;
    g_user_config.current_pid.ki = USER_PWR_CURRENT_KI;
    user_pwr_control_reset();

    UserPowerPwm_Init(&g_user_status);
    UserTvlcom_Init();
}

void UserPower_FastLoop(void)
{
    user_pwr_update_measurements();

    if (++g_fast_state_divider >= 1000U)
    {
        g_fast_state_divider = 0U;
        UserPower_5msTask();
    }

    user_pwr_protection_fast_check();

    if (g_user_status.state == USER_POWER_STATE_ERR)
    {
        return;
    }

    user_pwr_fast_control_loop();
}

void UserPower_1msTask(void)
{
    UserTvlcom_1msTask();
}

void UserPower_5msTask(void)
{
    if (g_user_status.state == USER_POWER_STATE_INIT)
    {
        g_user_status.state = USER_POWER_STATE_WAIT;
    }

    if ((g_user_status.state == USER_POWER_STATE_ERR) &&
        (g_user_config.power_enabled != 0U) &&
        (user_pwr_has_only_input_fault() != 0U) &&
        (user_pwr_input_ready() != 0U))
    {
        g_user_status.state = USER_POWER_STATE_WAIT;
        g_user_status.fault_mask = 0U;
        g_softstart_tick = 0U;
        user_pwr_control_reset();
        user_pwr_seed_voltage_ref(g_user_status.vout_v);
    }

    if (g_user_config.power_enabled == 0U)
    {
        if (g_user_status.state != USER_POWER_STATE_ERR)
        {
            g_user_status.state = USER_POWER_STATE_WAIT;
            g_user_status.topology = USER_POWER_TOPOLOGY_NA;
            g_softstart_tick = 0U;
            user_pwr_seed_voltage_ref(0.0f);
            UserPowerPwm_Stop(&g_user_status);
        }
        return;
    }

    if (g_user_status.state == USER_POWER_STATE_WAIT)
    {
        if (user_pwr_input_ready() == 0U)
        {
            UserPowerPwm_Stop(&g_user_status);
            return;
        }

        g_user_status.state = USER_POWER_STATE_RISE;
        g_softstart_tick = 0U;
        g_user_status.fault_mask = 0U;
        user_pwr_control_reset();
        user_pwr_seed_voltage_ref(g_user_status.vout_v);
        UserPowerPwm_Start();
        return;
    }

    if (g_user_status.state == USER_POWER_STATE_RISE)
    {
        user_pwr_slew_voltage_ref();
        g_softstart_tick++;
        if (user_pwr_voltage_ref_at_target() != 0U)
        {
            g_user_status.state = USER_POWER_STATE_RUN;
        }
        return;
    }

    if (g_user_status.state == USER_POWER_STATE_RUN)
    {
        user_pwr_slew_voltage_ref();
    }
}

void UserPower_BackgroundTask(void)
{
    uint32_t now = HAL_GetTick();

    UserTvlcom_BackgroundTask();

    if ((now - g_background_1ms_tick) >= 1U)
    {
        g_background_1ms_tick = now;
        UserPower_1msTask();
    }

    if ((now - g_aux_sample_tick) >= 100U)
    {
        g_aux_sample_tick = now;
        user_pwr_update_aux_measurements();
    }

    if (g_save_pending != 0U)
    {
        g_save_pending = 0U;
        UserPowerStore_Save(&g_user_config);
    }
}

void UserPower_GetStatus(user_power_status_t *out_status)
{
    if (out_status != NULL)
    {
        *out_status = g_user_status;
    }
}

void UserPower_GetConfig(user_power_config_t *out_config)
{
    if (out_config != NULL)
    {
        *out_config = g_user_config;
    }
}

void UserPower_SetVoltageLimitMv(uint32_t value_mv)
{
    g_user_config.target_voltage_v = user_pwr_clamp((float)value_mv / 1000.0f, 0.0f, 33.0f);
    if ((g_user_status.state == USER_POWER_STATE_RISE) ||
        (g_user_status.state == USER_POWER_STATE_RUN))
    {
        user_pwr_seed_voltage_ref(g_user_status.vout_v);
    }
    g_user_config.voltage_pid.prev_error = 0.0f;
    g_voltage_loop_divider = USER_PWR_CONTROL_DIVIDER_TICKS;
}

void UserPower_SetCurrentLimitMa(uint32_t value_ma)
{
    g_user_config.target_current_a = user_pwr_clamp((float)value_ma / 1000.0f, 0.0f, 10.0f);
}

void UserPower_SetOvpMv(uint32_t value_mv)
{
    g_user_config.ovp_v = user_pwr_clamp((float)value_mv / 1000.0f, 1.0f, 33.0f);
}

void UserPower_SetOcpMa(uint32_t value_ma)
{
    g_user_config.ocp_a = user_pwr_clamp((float)value_ma / 1000.0f, 0.1f, 12.0f);
}

void UserPower_SetOtpMc(uint32_t value_mc)
{
    g_user_config.otp_c = user_pwr_clamp((float)value_mc / 1000.0f, 20.0f, 120.0f);
}

void UserPower_SetFanValue(uint32_t value)
{
    user_pwr_apply_fan_value(value);
}

void UserPower_SetPowerState(uint8_t enabled)
{
    uint8_t was_enabled = g_user_config.power_enabled;

    g_user_config.power_enabled = enabled ? 1U : 0U;
    if (g_user_config.power_enabled == 0U)
    {
        g_user_status.state = USER_POWER_STATE_WAIT;
        g_user_status.fault_mask = 0U;
        g_softstart_tick = 0U;
        user_pwr_control_reset();
        user_pwr_seed_voltage_ref(0.0f);
        UserPowerPwm_Stop(&g_user_status);
    }
    else if (was_enabled == 0U)
    {
        g_user_status.state = USER_POWER_STATE_WAIT;
        g_user_status.fault_mask = 0U;
        g_softstart_tick = 0U;
        user_pwr_control_reset();
        user_pwr_seed_voltage_ref(g_user_status.vout_v);
    }
}

void UserPower_RequestSave(void)
{
    g_save_pending = 1U;
}

