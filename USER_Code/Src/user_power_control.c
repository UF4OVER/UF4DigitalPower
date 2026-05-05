#include "user_power_control.h"

#include "bsp_power_board.h"

#define USER_POWER_CAL_VOUT_K 4099L
#define USER_POWER_CAL_VOUT_B 1L
#define USER_POWER_CAL_IOUT_K 4095L
#define USER_POWER_CAL_IOUT_B 1L

#define USER_POWER_BUCK_PID_B0 5271L
#define USER_POWER_BUCK_PID_B1 (-10363L)
#define USER_POWER_BUCK_PID_B2 5093L
#define USER_POWER_BOOST_PID_B0 8044L
#define USER_POWER_BOOST_PID_B1 (-15813L)
#define USER_POWER_BOOST_PID_B2 7772L
#define USER_POWER_ILOOP_KP 6L
#define USER_POWER_ILOOP_KI 3L
#define USER_POWER_ILOOP_KD 1L

static user_power_sample_t g_sample;
static user_power_setpoint_t g_setpoint;
static user_power_mode_t g_mode = USER_POWER_MODE_NA;
static user_power_regulation_t g_regulation = USER_POWER_REG_CV;
static int32_t g_v_err0;
static int32_t g_v_err1;
static int32_t g_v_err2;
static int32_t g_v_out0;
static int32_t g_v_out1;
static int32_t g_i_err0;
static int32_t g_i_err1;
static int32_t g_i_integral;

static uint32_t user_power_filter(uint32_t sum, uint32_t value, uint32_t *average)
{
    sum = sum + value - (sum >> 3);
    *average = sum >> 3;
    return sum;
}

static int32_t user_power_voltage_to_adc(float voltage_v)
{
    return (int32_t)((voltage_v / BSP_POWER_VOLTAGE_DIVIDER_RATIO / BSP_POWER_VREF) *
                    BSP_POWER_ADC_MAX_VALUE);
}

static int32_t user_power_current_to_adc(float current_a)
{
    return (int32_t)(((current_a * BSP_POWER_CURRENT_SHUNT_OHM * BSP_POWER_CURRENT_GAIN) +
                      BSP_POWER_CURRENT_ZERO_V) /
                     BSP_POWER_VREF * BSP_POWER_ADC_MAX_VALUE);
}

static void user_power_reset_loop(void)
{
    g_v_err0 = 0;
    g_v_err1 = 0;
    g_v_err2 = 0;
    g_v_out0 = 0;
    g_v_out1 = 0;
    g_i_err0 = 0;
    g_i_err1 = 0;
    g_i_integral = 0;
}

void UserPower_Init(void)
{
    g_setpoint.set_vout_v = 5.0F;
    g_setpoint.set_iout_a = 10.0F;
    g_setpoint.ovp_v = 50.0F;
    g_setpoint.ocp_a = 10.5F;
    g_setpoint.otp_c = 80.0F;
    g_setpoint.output_enable = 0U;
    g_mode = USER_POWER_MODE_NA;
    g_regulation = USER_POWER_REG_CV;
    user_power_reset_loop();
    BSP_PowerBoard_Init();
}

void UserPower_FastLoop(void)
{
    int32_t vout_raw;
    int32_t iout_raw;
    int32_t v_ref;
    int32_t i_ref;
    int32_t i_out;
    int32_t buck_duty;
    int32_t boost_duty;

    g_sample.raw_vin = BSP_PowerBoard_GetRawAdc(0U);
    g_sample.raw_iin = BSP_PowerBoard_GetRawAdc(1U);
    g_sample.raw_vout = BSP_PowerBoard_GetRawAdc(2U);
    g_sample.raw_iout = BSP_PowerBoard_GetRawAdc(3U);

    vout_raw = (((int32_t)g_sample.raw_vout * USER_POWER_CAL_VOUT_K) >> 12) + USER_POWER_CAL_VOUT_B;
    iout_raw = (((int32_t)g_sample.raw_iout * USER_POWER_CAL_IOUT_K) >> 12) + USER_POWER_CAL_IOUT_B;
    v_ref = user_power_voltage_to_adc(g_setpoint.set_vout_v);
    i_ref = user_power_current_to_adc(g_setpoint.set_iout_a);

    g_i_err0 = i_ref - iout_raw;
    i_out = g_i_integral + g_i_err0 * USER_POWER_ILOOP_KP +
            (g_i_err0 - g_i_err1) * USER_POWER_ILOOP_KD;
    g_i_integral += g_i_err0 * USER_POWER_ILOOP_KI;
    if (g_i_integral > (int32_t)BSP_POWER_ADC_MAX_VALUE)
    {
        g_i_integral = (int32_t)BSP_POWER_ADC_MAX_VALUE;
    }

    v_ref += i_out;
    g_regulation = USER_POWER_REG_CC;
    if (v_ref > user_power_voltage_to_adc(g_setpoint.set_vout_v))
    {
        v_ref = user_power_voltage_to_adc(g_setpoint.set_vout_v);
        g_regulation = USER_POWER_REG_CV;
    }
    if (v_ref < 0)
    {
        v_ref = 0;
    }

    if (g_sample.avg_vout < g_sample.avg_vin * 8U / 10U)
    {
        g_mode = USER_POWER_MODE_BUCK;
    }
    else if (g_sample.avg_vout > g_sample.avg_vin * 12U / 10U)
    {
        g_mode = USER_POWER_MODE_BOOST;
    }
    else
    {
        g_mode = USER_POWER_MODE_MIX;
    }

    g_v_err0 = v_ref - vout_raw;
    switch (g_mode)
    {
    case USER_POWER_MODE_BUCK:
        g_v_out0 = g_v_out1 + g_v_err0 * USER_POWER_BUCK_PID_B0 +
                   g_v_err1 * USER_POWER_BUCK_PID_B1 +
                   g_v_err2 * USER_POWER_BUCK_PID_B2;
        boost_duty = BSP_POWER_MIN_BOOST_FIXED_DUTY;
        buck_duty = (g_v_out0 >> 8) * 3L;
        break;
    case USER_POWER_MODE_BOOST:
        g_v_out0 = g_v_out1 + g_v_err0 * USER_POWER_BOOST_PID_B0 +
                   g_v_err1 * USER_POWER_BOOST_PID_B1 +
                   g_v_err2 * USER_POWER_BOOST_PID_B2;
        buck_duty = BSP_POWER_MAX_BUCK_DUTY;
        boost_duty = (g_v_out0 >> 8) * 3L;
        break;
    case USER_POWER_MODE_MIX:
        g_v_out0 = g_v_out1 + g_v_err0 * USER_POWER_BOOST_PID_B0 +
                   g_v_err1 * USER_POWER_BOOST_PID_B1 +
                   g_v_err2 * USER_POWER_BOOST_PID_B2;
        buck_duty = BSP_POWER_MAX_BUCK_MIX_DUTY;
        boost_duty = (g_v_out0 >> 8) * 3L;
        break;
    default:
        g_v_out0 = 0;
        buck_duty = BSP_POWER_MIN_BUCK_DUTY;
        boost_duty = BSP_POWER_MIN_BOOST_DUTY;
        break;
    }

    g_v_err2 = g_v_err1;
    g_v_err1 = g_v_err0;
    g_v_out1 = g_v_out0;
    g_i_err1 = g_i_err0;

    if (buck_duty < (int32_t)BSP_POWER_MIN_BUCK_DUTY)
    {
        buck_duty = BSP_POWER_MIN_BUCK_DUTY;
    }
    if (buck_duty > (int32_t)BSP_POWER_MAX_BUCK_DUTY)
    {
        buck_duty = BSP_POWER_MAX_BUCK_DUTY;
    }
    if (boost_duty < (int32_t)BSP_POWER_MIN_BOOST_DUTY)
    {
        boost_duty = BSP_POWER_MIN_BOOST_DUTY;
    }
    if (boost_duty > (int32_t)BSP_POWER_MAX_BOOST_DUTY)
    {
        boost_duty = BSP_POWER_MAX_BOOST_DUTY;
    }

    if (g_setpoint.output_enable == 0U)
    {
        buck_duty = BSP_POWER_MIN_BUCK_DUTY;
        boost_duty = BSP_POWER_MIN_BOOST_DUTY;
    }

    BSP_PowerBoard_SetBuckCompare((uint16_t)(BSP_POWER_HRTIM_PERIOD - buck_duty));
    BSP_PowerBoard_SetAdcTriggerCompare((uint16_t)((BSP_POWER_HRTIM_PERIOD - buck_duty) >> 1));
    BSP_PowerBoard_SetBoostCompare((uint16_t)boost_duty);
}

void UserPower_5msTask(void)
{
    static uint32_t vin_sum;
    static uint32_t iin_sum;
    static uint32_t vout_sum;
    static uint32_t iout_sum;

    vin_sum = user_power_filter(vin_sum, g_sample.raw_vin, &g_sample.avg_vin);
    iin_sum = user_power_filter(iin_sum, g_sample.raw_iin, &g_sample.avg_iin);
    vout_sum = user_power_filter(vout_sum, g_sample.raw_vout, &g_sample.avg_vout);
    iout_sum = user_power_filter(iout_sum, g_sample.raw_iout, &g_sample.avg_iout);

    g_sample.vin_v = BSP_PowerBoard_AdcToVoltage((uint16_t)g_sample.avg_vin);
    g_sample.iin_a = BSP_PowerBoard_AdcToCurrent((uint16_t)g_sample.avg_iin);
    g_sample.vout_v = BSP_PowerBoard_AdcToVoltage((uint16_t)g_sample.avg_vout);
    g_sample.iout_a = BSP_PowerBoard_AdcToCurrent((uint16_t)g_sample.avg_iout);
    g_sample.board_temp_c = BSP_PowerBoard_ReadBoardTemperatureC();
    g_sample.cpu_temp_c = BSP_PowerBoard_ReadCpuTemperatureC();

    if ((g_sample.vout_v > g_setpoint.ovp_v) ||
        (g_sample.iout_a > g_setpoint.ocp_a) ||
        (g_sample.board_temp_c > g_setpoint.otp_c))
    {
        g_setpoint.output_enable = 0U;
        BSP_PowerBoard_DisablePowerPwm();
        user_power_reset_loop();
    }
    else if (g_setpoint.output_enable != 0U)
    {
        BSP_PowerBoard_EnablePowerPwm();
    }
}

void UserPower_SetOutput(float voltage_v, float current_a, uint8_t enable)
{
    g_setpoint.set_vout_v = voltage_v;
    g_setpoint.set_iout_a = current_a;
    g_setpoint.output_enable = enable ? 1U : 0U;
    user_power_reset_loop();
}

const user_power_sample_t *UserPower_GetSample(void)
{
    return &g_sample;
}

const user_power_setpoint_t *UserPower_GetSetpoint(void)
{
    return &g_setpoint;
}

user_power_mode_t UserPower_GetMode(void)
{
    return g_mode;
}

user_power_regulation_t UserPower_GetRegulation(void)
{
    return g_regulation;
}
