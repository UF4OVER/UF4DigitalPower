#include "app_power.h"

#include "app_tvlcom.h"
#include "app_w25qxx.h"
#include "adc.h"
#include "hrtim.h"
#include "spi.h"
#include "tim.h"

#include <math.h>
#include <string.h>

#define POWER_APP_VREF              3.3F
#define POWER_APP_ADC_MAX           4095.0F
#define POWER_APP_ADC1_MAX          8190.0F
#define POWER_APP_VOLTAGE_DIVIDER   (75.0F / 4.7F)
#define POWER_APP_SHUNT_OHM         0.005F
#define POWER_APP_CURRENT_GAIN      62.0F
#define POWER_APP_CURRENT_OFFSET_V  1.65F
#define POWER_APP_PWM_PERIOD        30000U
#define POWER_APP_BUCK_MIN_COMPARE  260U
#define POWER_APP_BOOST_MIN_COMPARE 260U
#define POWER_APP_BUCK_FIXED_MIX    24000U
#define POWER_APP_BUCK_FIXED_BOOST  28200U
#define POWER_APP_STORAGE_ADDR      0x000000U
#define POWER_APP_STORAGE_MAGIC     0x44505752UL
#define POWER_APP_STORAGE_VERSION   1U

typedef struct
{
    uint32_t magic;
    uint16_t version;
    uint16_t reserved;
    power_app_config_t config;
    uint32_t crc;
} power_app_storage_t;

volatile uint16_t ADC1_RESULT[POWER_APP_ADC_CHANNEL_COUNT] = {0U};

static power_app_config_t g_config;
static power_app_status_t g_status;
static uint8_t g_save_pending = 0U;
static uint16_t g_softstart_ticks = 0U;
static uint16_t g_fault_release_ticks = 0U;
static uint8_t g_voltage_loop_divider = 0U;
static uint16_t g_led_pattern_ticks = 0U;
static uint8_t g_led_pattern_index = 0U;
static uint32_t g_report_fast_ticks = 0U;

static float app_clampf(float value, float min_value, float max_value)
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

static uint16_t app_crc16(const uint8_t *data, uint16_t length)
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

static float app_filter(float prev, float input, float alpha)
{
    return prev + alpha * (input - prev);
}

static float app_adc_to_voltage(uint16_t adc)
{
    return ((float)adc * POWER_APP_VREF / POWER_APP_ADC1_MAX) * POWER_APP_VOLTAGE_DIVIDER;
}

static float app_adc_to_current(uint16_t adc)
{
    float sensor_v = ((float)adc * POWER_APP_VREF) / POWER_APP_ADC1_MAX;
    return (sensor_v - POWER_APP_CURRENT_OFFSET_V) / (POWER_APP_SHUNT_OHM * POWER_APP_CURRENT_GAIN);
}

static float app_board_temperature_c(void)
{
    uint32_t adc_raw = 0U;
    float voltage;
    float ratio;

    (void)HAL_ADC_Start(&hadc2);
    (void)HAL_ADC_PollForConversion(&hadc2, 2U);
    adc_raw = HAL_ADC_GetValue(&hadc2);
    voltage = ((float)adc_raw * POWER_APP_VREF) / POWER_APP_ADC_MAX;
    voltage = app_clampf(voltage, 0.05F, 3.25F);
    ratio = (POWER_APP_VREF / voltage) - 1.0F;
    ratio = app_clampf(ratio, 0.01F, 1000.0F);
    return (1.0F / ((1.0F / 298.15F) + logf((10000.0F * ratio) / 10000.0F) / 3950.0F)) - 273.15F;
}

static float app_core_temperature_c(void)
{
    float temp30 = 30.0F;
    float temp130 = 130.0F;
    float cal30 = (float)(*(__IO uint16_t *)0x1FFF75A8U);
    float cal130 = (float)(*(__IO uint16_t *)0x1FFF75CAU);
    float adc_raw;

    (void)HAL_ADC_Start(&hadc5);
    (void)HAL_ADC_PollForConversion(&hadc5, 2U);
    adc_raw = (float)HAL_ADC_GetValue(&hadc5);

    return (((adc_raw - cal30) * (temp130 - temp30)) / (cal130 - cal30)) + temp30;
}

static void app_pwm_stop(void)
{
    HAL_HRTIM_WaveformOutputStop(&hhrtim1, HRTIM_OUTPUT_TA1 | HRTIM_OUTPUT_TA2);
    HAL_HRTIM_WaveformOutputStop(&hhrtim1, HRTIM_OUTPUT_TD1 | HRTIM_OUTPUT_TD2);
    g_status.pwm_a_compare = POWER_APP_PWM_PERIOD;
    g_status.pwm_d_compare = POWER_APP_BOOST_MIN_COMPARE;
}

static void app_pwm_start(void)
{
    HAL_HRTIM_WaveformOutputStart(&hhrtim1, HRTIM_OUTPUT_TA1 | HRTIM_OUTPUT_TA2);
    HAL_HRTIM_WaveformOutputStart(&hhrtim1, HRTIM_OUTPUT_TD1 | HRTIM_OUTPUT_TD2);
}

static void app_pwm_apply(uint16_t compare_a, uint16_t compare_d)
{
    g_status.pwm_a_compare = compare_a;
    g_status.pwm_d_compare = compare_d;
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_1, compare_a);
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_3, compare_a / 2U);
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_D, HRTIM_COMPAREUNIT_1, compare_d);
}

static void app_pid_reset(power_app_pid_t *pid)
{
    pid->integral = 0.0F;
    pid->prev_error = 0.0F;
    pid->prev_measurement = 0.0F;
}

static float app_pid_step(power_app_pid_t *pid, float setpoint, float measurement, float dt)
{
    float error = setpoint - measurement;
    float derivative = (measurement - pid->prev_measurement) / dt;
    float output;

    pid->integral += pid->ki * error * dt;
    pid->integral = app_clampf(pid->integral, pid->out_min, pid->out_max);

    output = (pid->kp * error) + pid->integral - (pid->kd * derivative);
    output = app_clampf(output, pid->out_min, pid->out_max);

    if ((output == pid->out_max && error > 0.0F) || (output == pid->out_min && error < 0.0F))
    {
        pid->integral -= pid->ki * error * dt;
        pid->integral = app_clampf(pid->integral, pid->out_min, pid->out_max);
    }

    pid->prev_error = error;
    pid->prev_measurement = measurement;
    return output;
}

static void app_set_defaults(void)
{
    memset(&g_status, 0, sizeof(g_status));
    memset(&g_config, 0, sizeof(g_config));

    g_config.target_voltage_v = 12.0F;
    g_config.target_current_a = 3.0F;
    g_config.otp_c = 80.0F;
    g_config.ovp_v = 33.0F;
    g_config.ocp_a = 10.0F;
    g_config.input_uvp_v = 6.0F;
    g_config.input_ovp_v = 36.0F;
    g_config.power_enabled = 0U;

    g_config.voltage_pid.kp = 0.6F;
    g_config.voltage_pid.ki = 35.0F;
    g_config.voltage_pid.kd = 0.0F;
    g_config.voltage_pid.out_min = -10.0F;
    g_config.voltage_pid.out_max = 10.0F;

    g_config.current_pid.kp = 0.08F;
    g_config.current_pid.ki = 8.0F;
    g_config.current_pid.kd = 0.0F;
    g_config.current_pid.out_min = 0.02F;
    g_config.current_pid.out_max = 0.94F;

    app_pid_reset(&g_config.voltage_pid);
    app_pid_reset(&g_config.current_pid);

    g_status.state = POWER_APP_STATE_INIT;
    g_status.topology = POWER_APP_TOPOLOGY_NA;
    g_status.regulation_mode = POWER_APP_MODE_CV;
}

static void app_storage_load(void)
{
    power_app_storage_t image;
    uint16_t crc;

    if (AppW25Qxx_Read(POWER_APP_STORAGE_ADDR, (uint8_t *)&image, sizeof(image)) != HAL_OK)
    {
        return;
    }

    crc = app_crc16((const uint8_t *)&image, (uint16_t)(sizeof(image) - sizeof(image.crc)));
    if ((image.magic != POWER_APP_STORAGE_MAGIC) ||
        (image.version != POWER_APP_STORAGE_VERSION) ||
        (crc != (uint16_t)image.crc))
    {
        return;
    }

    g_config = image.config;
    app_pid_reset(&g_config.voltage_pid);
    app_pid_reset(&g_config.current_pid);
}

static void app_storage_save(void)
{
    power_app_storage_t image;

    image.magic = POWER_APP_STORAGE_MAGIC;
    image.version = POWER_APP_STORAGE_VERSION;
    image.reserved = 0U;
    image.config = g_config;
    image.config.voltage_pid.integral = 0.0F;
    image.config.voltage_pid.prev_error = 0.0F;
    image.config.voltage_pid.prev_measurement = 0.0F;
    image.config.current_pid.integral = 0.0F;
    image.config.current_pid.prev_error = 0.0F;
    image.config.current_pid.prev_measurement = 0.0F;
    image.crc = app_crc16((const uint8_t *)&image, (uint16_t)(sizeof(image) - sizeof(image.crc)));

    if (AppW25Qxx_EraseSector(POWER_APP_STORAGE_ADDR) == HAL_OK)
    {
        (void)AppW25Qxx_Write(POWER_APP_STORAGE_ADDR, (const uint8_t *)&image, sizeof(image));
    }
}

static void app_update_measurements(void)
{
    g_status.raw_adc[0] = ADC1_RESULT[2];
    g_status.raw_adc[1] = ADC1_RESULT[3];
    g_status.raw_adc[2] = ADC1_RESULT[0];
    g_status.raw_adc[3] = ADC1_RESULT[1];

    g_status.vin_v = app_filter(g_status.vin_v, app_adc_to_voltage(ADC1_RESULT[2]), 0.15F);
    g_status.iin_a = app_filter(g_status.iin_a, app_adc_to_current(ADC1_RESULT[3]), 0.15F);
    g_status.vout_v = app_filter(g_status.vout_v, app_adc_to_voltage(ADC1_RESULT[0]), 0.15F);
    g_status.iout_a = app_filter(g_status.iout_a, app_adc_to_current(ADC1_RESULT[1]), 0.15F);
}

static void app_update_topology(void)
{
    float vout_set = g_config.target_voltage_v;
    float vin = g_status.vin_v;

    switch (g_status.topology)
    {
    case POWER_APP_TOPOLOGY_NA:
        if (vout_set < vin * 0.8F)
        {
            g_status.topology = POWER_APP_TOPOLOGY_BUCK;
        }
        else if (vout_set > vin * 1.2F)
        {
            g_status.topology = POWER_APP_TOPOLOGY_BOOST;
        }
        else
        {
            g_status.topology = POWER_APP_TOPOLOGY_MIX;
        }
        break;
    case POWER_APP_TOPOLOGY_BUCK:
        if (vout_set > vin * 1.2F)
        {
            g_status.topology = POWER_APP_TOPOLOGY_BOOST;
        }
        else if (vout_set > vin * 0.85F)
        {
            g_status.topology = POWER_APP_TOPOLOGY_MIX;
        }
        break;
    case POWER_APP_TOPOLOGY_BOOST:
        if (vout_set < vin * 0.8F)
        {
            g_status.topology = POWER_APP_TOPOLOGY_BUCK;
        }
        else if (vout_set < vin * 1.15F)
        {
            g_status.topology = POWER_APP_TOPOLOGY_MIX;
        }
        break;
    case POWER_APP_TOPOLOGY_MIX:
        if (vout_set < vin * 0.8F)
        {
            g_status.topology = POWER_APP_TOPOLOGY_BUCK;
        }
        else if (vout_set > vin * 1.2F)
        {
            g_status.topology = POWER_APP_TOPOLOGY_BOOST;
        }
        break;
    default:
        g_status.topology = POWER_APP_TOPOLOGY_NA;
        break;
    }
}

static void app_apply_control(float duty)
{
    uint16_t compare_a;
    uint16_t compare_d;

    duty = app_clampf(duty, g_config.current_pid.out_min, g_config.current_pid.out_max);
    g_status.duty_cmd = duty;

    switch (g_status.topology)
    {
    case POWER_APP_TOPOLOGY_BUCK:
        compare_a = (uint16_t)(POWER_APP_PWM_PERIOD * (1.0F - duty));
        compare_a = (uint16_t)app_clampf((float)compare_a,
                                         (float)(POWER_APP_PWM_PERIOD - (POWER_APP_PWM_PERIOD * 0.94F)),
                                         (float)(POWER_APP_PWM_PERIOD - POWER_APP_BUCK_MIN_COMPARE));
        compare_d = POWER_APP_BOOST_MIN_COMPARE;
        break;
    case POWER_APP_TOPOLOGY_BOOST:
        compare_a = (uint16_t)(POWER_APP_PWM_PERIOD - POWER_APP_BUCK_FIXED_BOOST);
        compare_d = (uint16_t)(POWER_APP_PWM_PERIOD * duty);
        compare_d = (uint16_t)app_clampf((float)compare_d, (float)POWER_APP_BOOST_MIN_COMPARE, POWER_APP_PWM_PERIOD * 0.94F);
        break;
    case POWER_APP_TOPOLOGY_MIX:
        compare_a = (uint16_t)(POWER_APP_PWM_PERIOD - POWER_APP_BUCK_FIXED_MIX);
        compare_d = (uint16_t)(POWER_APP_PWM_PERIOD * duty);
        compare_d = (uint16_t)app_clampf((float)compare_d, (float)POWER_APP_BOOST_MIN_COMPARE, POWER_APP_PWM_PERIOD * 0.94F);
        break;
    default:
        compare_a = POWER_APP_PWM_PERIOD;
        compare_d = POWER_APP_BOOST_MIN_COMPARE;
        break;
    }

    app_pwm_apply(compare_a, compare_d);
}

static void app_handle_faults(void)
{
    uint16_t fault = 0U;

    if (g_config.power_enabled == 0U)
    {
        g_status.fault_mask = 0U;
        if (g_status.state != POWER_APP_STATE_ERR)
        {
            return;
        }
    }

    if ((g_status.state != POWER_APP_STATE_RISE) && (g_status.state != POWER_APP_STATE_RUN) && (g_status.state != POWER_APP_STATE_ERR))
    {
        return;
    }

    if (g_status.vin_v < g_config.input_uvp_v)
    {
        fault |= POWER_APP_FAULT_INPUT_UNDER_VOLTAGE;
    }
    if (g_status.vin_v > g_config.input_ovp_v)
    {
        fault |= POWER_APP_FAULT_INPUT_OVER_VOLTAGE;
    }
    if ((g_status.state == POWER_APP_STATE_RUN) && (g_status.vout_v < 0.2F * g_config.target_voltage_v) && (g_status.iout_a > (g_config.ocp_a * 0.8F)))
    {
        fault |= POWER_APP_FAULT_OUTPUT_SHORT;
    }
    if (g_status.vout_v > g_config.ovp_v)
    {
        fault |= POWER_APP_FAULT_OUTPUT_OVER_VOLTAGE;
    }
    if (fabsf(g_status.iout_a) > g_config.ocp_a)
    {
        fault |= POWER_APP_FAULT_OUTPUT_OVER_CURRENT;
    }
    if (g_status.board_temp_c > g_config.otp_c)
    {
        fault |= POWER_APP_FAULT_OVER_TEMPERATURE;
    }

    if (fault != 0U)
    {
        g_status.fault_mask = fault;
        g_status.state = POWER_APP_STATE_ERR;
        app_pwm_stop();
    }
    else if (g_status.state == POWER_APP_STATE_ERR)
    {
        g_status.fault_mask = 0U;
    }
}

static void app_update_state_machine(void)
{
    if (g_status.state == POWER_APP_STATE_INIT)
    {
        g_status.state = POWER_APP_STATE_WAIT;
        return;
    }

    if (g_status.state == POWER_APP_STATE_ERR)
    {
        if ((g_status.fault_mask & POWER_APP_FAULT_OVER_TEMPERATURE) == 0U)
        {
            if (++g_fault_release_ticks >= 200U)
            {
                g_fault_release_ticks = 0U;
                g_status.fault_mask = 0U;
                g_status.state = POWER_APP_STATE_WAIT;
                g_status.topology = POWER_APP_TOPOLOGY_NA;
                app_pid_reset(&g_config.voltage_pid);
                app_pid_reset(&g_config.current_pid);
            }
        }
        return;
    }

    if (g_config.power_enabled == 0U)
    {
        g_status.state = POWER_APP_STATE_WAIT;
        g_softstart_ticks = 0U;
        app_pwm_stop();
        return;
    }

    if (g_status.state == POWER_APP_STATE_WAIT)
    {
        g_status.state = POWER_APP_STATE_RISE;
        g_softstart_ticks = 0U;
        app_pid_reset(&g_config.voltage_pid);
        app_pid_reset(&g_config.current_pid);
        app_pwm_start();
        return;
    }

    if (g_status.state == POWER_APP_STATE_RISE)
    {
        if (++g_softstart_ticks >= 100U)
        {
            g_status.state = POWER_APP_STATE_RUN;
        }
    }
}

static void app_update_fan(void)
{
    uint32_t pulse = 0U;

    if (g_status.board_temp_c >= 60.0F)
    {
        pulse = 1000U;
    }
    else if (g_status.board_temp_c >= 50.0F)
    {
        pulse = 800U;
    }
    else if (g_status.board_temp_c >= 45.0F)
    {
        pulse = 650U;
    }
    else if (g_status.board_temp_c >= 40.0F)
    {
        pulse = 500U;
    }
    else if (g_status.board_temp_c >= 35.0F)
    {
        pulse = 350U;
    }

    g_status.fan_speed = pulse;
    __HAL_TIM_SET_COMPARE(&htim8, TIM_CHANNEL_3, pulse);
}

static void app_set_led_pattern(uint8_t index)
{
    HAL_GPIO_WritePin(LED1_GPIO_Port, LED1_Pin, (index == 0U) ? GPIO_PIN_SET : GPIO_PIN_RESET);
    HAL_GPIO_WritePin(LED2_GPIO_Port, LED2_Pin, (index == 1U) ? GPIO_PIN_SET : GPIO_PIN_RESET);
    HAL_GPIO_WritePin(LED3_GPIO_Port, LED3_Pin, (index == 2U) ? GPIO_PIN_SET : GPIO_PIN_RESET);
    HAL_GPIO_WritePin(LED4_GPIO_Port, LED4_Pin, (index == 3U) ? GPIO_PIN_SET : GPIO_PIN_RESET);
}

void PowerApp_Init(void)
{
    app_set_defaults();
    app_set_led_pattern(0U);

    (void)HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);
    (void)HAL_ADCEx_Calibration_Start(&hadc2, ADC_SINGLE_ENDED);
    (void)HAL_ADCEx_Calibration_Start(&hadc5, ADC_SINGLE_ENDED);

    (void)HAL_ADC_Start_DMA(&hadc1, (uint32_t *)ADC1_RESULT, POWER_APP_ADC_CHANNEL_COUNT);
    (void)HAL_HRTIM_WaveformCountStart_IT(&hhrtim1, HRTIM_TIMERID_TIMER_A);
    (void)HAL_HRTIM_WaveformCountStart(&hhrtim1, HRTIM_TIMERID_TIMER_D);
    (void)HAL_TIM_Base_Start_IT(&htim2);
    (void)HAL_TIM_Base_Start_IT(&htim3);
    (void)HAL_TIM_Base_Start_IT(&htim4);
    (void)HAL_TIM_PWM_Start(&htim8, TIM_CHANNEL_3);

    (void)AppW25Qxx_Init();
    app_storage_load();
    app_pwm_stop();
    AppTvlcom_Init();
}

void PowerApp_FastLoop(void)
{
    float vref_target = g_config.target_voltage_v;
    float vloop_dt = 50.0e-6F;
    float iloop_dt = 5.0e-6F;

    if (++g_report_fast_ticks >= 200000UL)
    {
        g_report_fast_ticks = 0UL;
        AppTvlcom_RequestReport();
        AppTvlcom_BackgroundTask();
    }

    app_update_measurements();
    app_update_topology();

    if ((g_status.state != POWER_APP_STATE_RISE) && (g_status.state != POWER_APP_STATE_RUN))
    {
        app_apply_control(0.02F);
        return;
    }

    if (++g_voltage_loop_divider >= 10U)
    {
        g_voltage_loop_divider = 0U;
        if (g_status.state == POWER_APP_STATE_RISE)
        {
            vref_target *= ((float)g_softstart_ticks / 100.0F);
        }

        g_status.current_ref_a = app_pid_step(&g_config.voltage_pid, vref_target, g_status.vout_v, vloop_dt);
    }

    g_status.current_ref_a = app_clampf(g_status.current_ref_a, -g_config.target_current_a, g_config.target_current_a);
    g_status.duty_cmd = app_pid_step(&g_config.current_pid, g_status.current_ref_a, g_status.iout_a, iloop_dt);
    g_status.regulation_mode = (fabsf(g_status.current_ref_a) >= (g_config.target_current_a - 0.05F)) ? POWER_APP_MODE_CC : POWER_APP_MODE_CV;
    app_apply_control(g_status.duty_cmd);
}

void PowerApp_1msTask(void)
{
    AppTvlcom_1msTask();

    g_led_pattern_ticks++;
    if (g_led_pattern_ticks >= 125U)
    {
        g_led_pattern_ticks = 0U;
        g_led_pattern_index = (uint8_t)((g_led_pattern_index + 1U) & 0x03U);
        app_set_led_pattern(g_led_pattern_index);
    }
}

void PowerApp_5msTask(void)
{
    g_status.board_temp_c = app_filter(g_status.board_temp_c, app_board_temperature_c(), 0.1F);
    g_status.core_temp_c = app_filter(g_status.core_temp_c, app_core_temperature_c(), 0.1F);
    app_update_state_machine();
    app_handle_faults();
    app_update_fan();
}

void PowerApp_CommTask(void)
{
    AppTvlcom_BackgroundTask();
}

void PowerApp_BackgroundTask(void)
{
    PowerApp_CommTask();

    if (g_save_pending != 0U)
    {
        g_save_pending = 0U;
        app_storage_save();
    }
}

void PowerApp_OnCommBytes(const uint8_t *data, uint16_t length)
{
    AppTvlcom_OnBytes(data, length);
}

void PowerApp_GetStatus(power_app_status_t *out_status)
{
    if (out_status != NULL)
    {
        *out_status = g_status;
    }
}

void PowerApp_GetConfig(power_app_config_t *out_config)
{
    if (out_config != NULL)
    {
        *out_config = g_config;
    }
}

void PowerApp_SetVoltageLimitMv(uint32_t value_mv)
{
    g_config.target_voltage_v = app_clampf((float)value_mv / 1000.0F, 0.0F, 33.0F);
}

void PowerApp_SetCurrentLimitMa(uint32_t value_ma)
{
    g_config.target_current_a = app_clampf((float)value_ma / 1000.0F, 0.0F, 10.0F);
}

void PowerApp_SetOvpMv(uint32_t value_mv)
{
    g_config.ovp_v = app_clampf((float)value_mv / 1000.0F, 1.0F, 33.0F);
}

void PowerApp_SetOcpMa(uint32_t value_ma)
{
    g_config.ocp_a = app_clampf((float)value_ma / 1000.0F, 0.1F, 12.0F);
}

void PowerApp_SetOtpMc(uint32_t value_mc)
{
    g_config.otp_c = app_clampf((float)value_mc / 1000.0F, 20.0F, 120.0F);
}

void PowerApp_SetPowerState(uint8_t enabled)
{
    g_config.power_enabled = enabled ? 1U : 0U;
}

void PowerApp_RequestSave(void)
{
    g_save_pending = 1U;
}
