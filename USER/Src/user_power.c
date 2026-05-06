#include "../Inc/user_power.h"

#include "../Inc/user_power_cfg.h"
#include "../Inc/user_power_pwm.h"
#include "../Inc/user_power_store.h"
#include "../Inc/user_tvlcom.h"

#include "adc.h"
#include "hrtim.h"
#include "tim.h"

#include <string.h>

static user_power_config_t g_user_config;
static user_power_status_t g_user_status;
static volatile uint16_t *g_adc_result = NULL;
static uint8_t g_save_pending = 0U;
static uint16_t g_softstart_tick = 0U;
static uint16_t g_voltage_loop_divider = 0U;
static float g_iin_zero_v = USER_PWR_CURRENT_ZERO_V;
static float g_iout_zero_v = USER_PWR_CURRENT_ZERO_V;

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

    user_pwr_pid_reset(&g_user_config.voltage_pid);
    user_pwr_pid_reset(&g_user_config.current_pid);

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

    if (g_adc_result == NULL)
    {
        return;
    }

    /* CubeMX ADC1 DMA order: [0]=VIN, [1]=IIN, [2]=VOUT, [3]=IOUT */
    g_user_status.raw_adc[0] = g_adc_result[0];
    g_user_status.raw_adc[1] = g_adc_result[1];
    g_user_status.raw_adc[2] = g_adc_result[2];
    g_user_status.raw_adc[3] = g_adc_result[3];

    g_user_status.vin_v = user_pwr_lpf(g_user_status.vin_v, user_pwr_adc_to_voltage(g_adc_result[0]));
    g_user_status.vout_v = user_pwr_lpf(g_user_status.vout_v, user_pwr_adc_to_voltage(g_adc_result[2]));

    iin_sensor_v = user_pwr_adc_to_sensor_voltage(g_adc_result[1]);
    iout_sensor_v = user_pwr_adc_to_sensor_voltage(g_adc_result[3]);

    /* Track current-sense zero when output is disabled to suppress false full-scale current. */
    if (g_user_config.power_enabled == 0U)
    {
        g_iin_zero_v = g_iin_zero_v + 0.02f * (iin_sensor_v - g_iin_zero_v);
        g_iout_zero_v = g_iout_zero_v + 0.02f * (iout_sensor_v - g_iout_zero_v);
    }

    iin = user_pwr_sensor_voltage_to_current(iin_sensor_v, g_iin_zero_v);
    iout = user_pwr_sensor_voltage_to_current(iout_sensor_v, g_iout_zero_v);

    g_user_status.iin_a = user_pwr_lpf(g_user_status.iin_a, user_pwr_clamp(iin, -12.0f, 12.0f));
    g_user_status.iout_a = user_pwr_lpf(g_user_status.iout_a, user_pwr_clamp(iout, -12.0f, 12.0f));
}

static void user_pwr_select_topology(void)
{
    float vin = g_user_status.vin_v;
    float vref = g_user_config.target_voltage_v;

    if (vref < (vin - 1.0f))
    {
        g_user_status.topology = USER_POWER_TOPOLOGY_BUCK;
    }
    else if (vref > (vin + 1.0f))
    {
        g_user_status.topology = USER_POWER_TOPOLOGY_BOOST;
    }
    else
    {
        g_user_status.topology = USER_POWER_TOPOLOGY_MIX;
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
        return;
    }

    if (g_user_status.vin_v < g_user_config.input_uvp_v)
    {
        user_pwr_set_fault(USER_POWER_FAULT_INPUT_UNDER_VOLTAGE);
        return;
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
    float iref;
    float duty_base;
    float duty_delta;
    float duty;

    if ((g_user_status.state != USER_POWER_STATE_RISE) && (g_user_status.state != USER_POWER_STATE_RUN))
    {
        UserPowerPwm_ApplyDuty(USER_POWER_TOPOLOGY_NA, USER_PWR_DUTY_MIN, &g_user_status);
        return;
    }

    user_pwr_select_topology();

    vref = g_user_config.target_voltage_v;
    if (g_user_status.state == USER_POWER_STATE_RISE)
    {
        float soft_v = (float)g_softstart_tick * USER_PWR_SOFTSTART_STEP_V;
        if (soft_v < vref)
        {
            vref = soft_v;
        }
    }

    if (++g_voltage_loop_divider >= 10U)
    {
        g_voltage_loop_divider = 0U;
        g_user_status.current_ref_a = user_pwr_pi_step(&g_user_config.voltage_pid, vref, g_user_status.vout_v);
    }

    iref = user_pwr_clamp(g_user_status.current_ref_a, 0.0f, g_user_config.target_current_a);
    duty_delta = user_pwr_pi_step(&g_user_config.current_pid, iref, g_user_status.iout_a);

    if (g_user_status.vin_v < 0.5f)
    {
        UserPowerPwm_ApplyDuty(USER_POWER_TOPOLOGY_NA, USER_PWR_DUTY_MIN, &g_user_status);
        return;
    }

    if (g_user_status.topology == USER_POWER_TOPOLOGY_BUCK)
    {
        duty_base = vref / g_user_status.vin_v;
    }
    else if (g_user_status.topology == USER_POWER_TOPOLOGY_BOOST)
    {
        duty_base = 1.0f - (g_user_status.vin_v / user_pwr_clamp(vref, 1.0f, 60.0f));
    }
    else
    {
        duty_base = 0.5f;
    }

    duty = user_pwr_clamp(duty_base + (duty_delta - 0.5f), USER_PWR_DUTY_MIN, USER_PWR_DUTY_MAX);
    g_user_status.duty_cmd = duty;
    g_user_status.regulation_mode = (iref >= (g_user_config.target_current_a - 0.05f)) ? USER_POWER_MODE_CC : USER_POWER_MODE_CV;
    UserPowerPwm_ApplyDuty(g_user_status.topology, duty, &g_user_status);
}

void UserPower_Init(volatile uint16_t *adc_dma_buffer)
{
    g_adc_result = adc_dma_buffer;
    g_save_pending = 0U;
    g_softstart_tick = 0U;
    g_voltage_loop_divider = 0U;
    g_iin_zero_v = USER_PWR_CURRENT_ZERO_V;
    g_iout_zero_v = USER_PWR_CURRENT_ZERO_V;

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

    user_pwr_pid_reset(&g_user_config.voltage_pid);
    user_pwr_pid_reset(&g_user_config.current_pid);

    UserPowerPwm_Init(&g_user_status);
    UserTvlcom_Init();
}

void UserPower_FastLoop(void)
{
    user_pwr_update_measurements();
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

    if (g_user_config.power_enabled == 0U)
    {
        if (g_user_status.state != USER_POWER_STATE_ERR)
        {
            g_user_status.state = USER_POWER_STATE_WAIT;
            g_user_status.topology = USER_POWER_TOPOLOGY_NA;
            g_softstart_tick = 0U;
            UserPowerPwm_Stop(&g_user_status);
        }
        return;
    }

    if (g_user_status.state == USER_POWER_STATE_WAIT)
    {
        g_user_status.state = USER_POWER_STATE_RISE;
        g_softstart_tick = 0U;
        g_user_status.fault_mask = 0U;
        user_pwr_pid_reset(&g_user_config.voltage_pid);
        user_pwr_pid_reset(&g_user_config.current_pid);
        UserPowerPwm_Start();
        return;
    }

    if (g_user_status.state == USER_POWER_STATE_RISE)
    {
        g_softstart_tick++;
        if (((float)g_softstart_tick * USER_PWR_SOFTSTART_STEP_V) >= g_user_config.target_voltage_v)
        {
            g_user_status.state = USER_POWER_STATE_RUN;
        }
    }
}

void UserPower_BackgroundTask(void)
{
    UserTvlcom_BackgroundTask();

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

void UserPower_SetPowerState(uint8_t enabled)
{
    g_user_config.power_enabled = enabled ? 1U : 0U;
    if ((g_user_config.power_enabled == 0U) && (g_user_status.state == USER_POWER_STATE_ERR))
    {
        g_user_status.state = USER_POWER_STATE_WAIT;
        g_user_status.fault_mask = 0U;
    }
}

void UserPower_RequestSave(void)
{
    g_save_pending = 1U;
}

