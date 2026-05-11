/**
 * @file    : uf4_power_pid.c
 * @brief   : TODO: 请填写模块功能简介
 * @author  : UF4
 * @date    : 2026/5/8 21:29
 * @version : CLion
 * @project : UF4DigitalPower
 * @details :
 * TODO: 请填写详细说明
 */

#include "hrtim.h"
#include "uf4_power_pid.h"
#include "uf4_power_main.h"


/*
 * 定义一个宏 CCMRAM，用于将函数或变量指定到CCM RAM段。
 * 使用此宏的声明将会被编译器放置在CCM（Cacheable Memory）RAM区域中。
 * 这对于需要快速访问且不被系统缓存机制影响的变量或函数非常有用。
 */
#define CCMRAM __attribute__((section("ccmram")))

volatile int32_t VErr0 = 0, VErr1 = 0, VErr2 = 0; // 电压误差
volatile int32_t IErr0 = 0, IErr1 = 0;            // 电流误差
volatile int32_t u0 = 0, u1 = 0;                  // 电压环输出量
volatile int32_t i0 = 0, i1 = 0;                  // 电流环输出量
volatile _CVCC_Mode CVCC_Mode = CV;               // 恒流恒压模式标志位
volatile float UF4_DebugLoopImeas = 0.0F;         // 环路实际使用的电流反馈
volatile float UF4_DebugLoopIref = 0.0F;          // 电流内环参考
volatile float UF4_DebugLoopIrefV = 0.0F;         // 电压外环输出的电流参考

#define UF4_ISR_PRESCALE 8U
#define UF4_CONTROL_DIVIDER 8U
#define UF4_MEAS_ALPHA_V 0.18F
#define UF4_MEAS_ALPHA_I 0.22F
#define UF4_VLOOP_KP 0.080F
#define UF4_VLOOP_KI 0.00040F
#define UF4_VLOOP_INTEGRAL_MIN (-0.25F)
#define UF4_VLOOP_INTEGRAL_MAX 0.25F
#define UF4_CC_KP 1.10F
#define UF4_CC_KI 0.018F
#define UF4_CC_ENTER_MARGIN_A 0.08F
#define UF4_CC_EXIT_MARGIN_A 0.15F
#define UF4_CC_RECOVER_STEP_V 0.08F
#define UF4_CC_VREF_RISE_STEP_V 0.05F
#define UF4_CC_VREF_FALL_STEP_V 0.20F
#define UF4_CC_RELEASE_MARGIN_V 0.03F
#define UF4_ILIMIT_DISABLED_EPS 0.001F
#define UF4_SOFTSTART_STEP_V 0.04F
#define UF4_REF_FALL_STEP_V 0.08F
#define UF4_INPUT_FOLDBACK_LIMIT_A 8.5F
#define UF4_INPUT_FOLDBACK_GAIN 0.010F
#define UF4_INPUT_DROOP_MARGIN_V 1.0F
#define UF4_INPUT_DROOP_GAIN 0.020F
#define UF4_LIGHT_LOAD_CURRENT_A 0.10F
#define UF4_LIGHT_LOAD_OVERVOLTAGE_MARGIN 0.08F
#define UF4_DUTY_SLEW_UP 0.0100F
#define UF4_DUTY_SLEW_DOWN 0.0150F
#define UF4_DUTY_SLEW_UP_RISE 0.0060F
#define UF4_DUTY_MIN ((float)MIN_BUKC_DUTY / (float)PERIOD)
#define UF4_DUTY_MAX ((float)MAX_BUCK_DUTY / (float)PERIOD)
#define UF4_BOOST_DUTY_MAX ((float)MAX_BOOST_DUTY / (float)PERIOD)

typedef struct
{
    float vin;
    float vout;
    float iin;
    float iout;
    float soft_vref;
    float limited_vref;
    float duty_target;
    float duty_applied;
    float v_integral;
    float cc_integral;
    uint16_t control_divider;
    uint8_t measurement_ready;
    uint8_t current_limit_active;
    uint8_t control_seeded;
    uint8_t previous_mode;
} UF4_ControlState;

static UF4_ControlState g_ctrl = {0};

static float uf4_clampf(float value, float min_value, float max_value)
{
    if (value < min_value)
        return min_value;
    if (value > max_value)
        return max_value;
    return value;
}

static float uf4_lpf(float prev, float input, float alpha)
{
    return prev + alpha * (input - prev);
}

static uint32_t UF4_GetCalibratedVoutAdc(void)
{
    const uint32_t raw = (uint32_t)ADC1_RESULT[2];
    return (uint32_t)(((raw * (uint32_t)CAL_VOUT_K) >> 12) + (uint32_t)CAL_VOUT_B);
}

static uint32_t UF4_GetCalibratedIoutAdc(void)
{
    const uint32_t raw = (uint32_t)ADC1_RESULT[3];
    return (uint32_t)(((raw * (uint32_t)CAL_IOUT_K) >> 12) + (uint32_t)CAL_IOUT_B);
}

static void UF4_UpdateFilteredMeasurements(void)
{
    const float vin_raw = UF4_AdcToInputVoltage(ADC1_RESULT[0]);
    const float iin_raw = UF4_AdcToInputCurrent(ADC1_RESULT[1]);
    const float vout_raw = UF4_AdcToOutputVoltage(UF4_GetCalibratedVoutAdc());
    const float iout_raw = UF4_AdcToOutputCurrent(UF4_GetCalibratedIoutAdc());

    if (g_ctrl.measurement_ready == 0U)
    {
        g_ctrl.vin = vin_raw;
        g_ctrl.iin = iin_raw;
        g_ctrl.vout = vout_raw;
        g_ctrl.iout = iout_raw;
        g_ctrl.measurement_ready = 1U;
        return;
    }

    g_ctrl.vin = uf4_lpf(g_ctrl.vin, vin_raw, UF4_MEAS_ALPHA_V);
    g_ctrl.iin = uf4_lpf(g_ctrl.iin, iin_raw, UF4_MEAS_ALPHA_I);
    g_ctrl.vout = uf4_lpf(g_ctrl.vout, vout_raw, UF4_MEAS_ALPHA_V);
    g_ctrl.iout = uf4_lpf(g_ctrl.iout, iout_raw, UF4_MEAS_ALPHA_I);
}

static void UF4_UpdatePwmCompare(void)
{
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_1, PERIOD - CtrValue.BuckDuty);
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_3, __HAL_HRTIM_GETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_1) >> 1);
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_D, HRTIM_COMPAREUNIT_1, CtrValue.BoostDuty);
}

static void UF4_ResetLoopState(void)
{
    g_ctrl.soft_vref = 0.0F;
    g_ctrl.limited_vref = 0.0F;
    g_ctrl.duty_target = UF4_DUTY_MIN;
    g_ctrl.duty_applied = UF4_DUTY_MIN;
    g_ctrl.v_integral = 0.0F;
    g_ctrl.cc_integral = 0.0F;
    g_ctrl.control_divider = 0U;
    g_ctrl.measurement_ready = 0U;
    g_ctrl.current_limit_active = 0U;
    g_ctrl.control_seeded = 0U;
    g_ctrl.previous_mode = DF.BBFlag;
    VErr0 = 0;
    VErr1 = 0;
    VErr2 = 0;
    IErr0 = 0;
    IErr1 = 0;
    u0 = 0;
    u1 = 0;
    i0 = 0;
    i1 = 0;
    CtrValue.I_Limit = 0;
    CtrValue.Ilimitout = 0;
    UF4_DebugLoopImeas = 0.0F;
    UF4_DebugLoopIref = 0.0F;
    UF4_DebugLoopIrefV = 0.0F;
    CVCC_Mode = CV;
}

static void UF4_ApplyMinimumDuty(void)
{
    CtrValue.BuckDuty = MIN_BUKC_DUTY;
    CtrValue.BoostDuty = MIN_BOOST_DUTY;
}

static void UF4_UpdateSoftReference(float target_v)
{
    if (g_ctrl.soft_vref < target_v)
    {
        g_ctrl.soft_vref += UF4_SOFTSTART_STEP_V;
        if (g_ctrl.soft_vref > target_v)
            g_ctrl.soft_vref = target_v;
    }
    else if (g_ctrl.soft_vref > target_v)
    {
        g_ctrl.soft_vref -= UF4_REF_FALL_STEP_V;
        if (g_ctrl.soft_vref < target_v)
            g_ctrl.soft_vref = target_v;
    }
}

static float UF4_GetDutyFeedForward(float vin, float vref)
{
    const float safe_vref = uf4_clampf(vref, 1.0F, MAX_OUTPUT_VOLTAGE);

    if (vin < 0.5F)
        return UF4_DUTY_MIN;

    switch (DF.BBFlag)
    {
    case Buck:
        return uf4_clampf(vref / vin, UF4_DUTY_MIN, UF4_DUTY_MAX);
    case Boost:
        return uf4_clampf(1.0F - (vin / safe_vref), UF4_DUTY_MIN, UF4_BOOST_DUTY_MAX);
    case Mix:
        if (vref > vin)
            return uf4_clampf(1.0F - (vin / safe_vref), UF4_DUTY_MIN, UF4_BOOST_DUTY_MAX);
        return UF4_DUTY_MIN;
    default:
        return UF4_DUTY_MIN;
    }
}

static float UF4_GetDutyMax(void)
{
    float duty_max;

    switch (DF.BBFlag)
    {
    case Buck:
        duty_max = (float)CtrValue.BUCKMaxDuty / (float)PERIOD;
        return uf4_clampf(duty_max, UF4_DUTY_MIN, UF4_DUTY_MAX);
    case Boost:
    case Mix:
        duty_max = (float)CtrValue.BoostMaxDuty / (float)PERIOD;
        return uf4_clampf(duty_max, UF4_DUTY_MIN, UF4_BOOST_DUTY_MAX);
    default:
        return UF4_DUTY_MIN;
    }
}

static float UF4_RunCurrentSupervisor(float current_limit)
{
    if (current_limit <= UF4_ILIMIT_DISABLED_EPS)
    {
        g_ctrl.cc_integral = 0.0F;
        g_ctrl.current_limit_active = 0U;
        return g_ctrl.soft_vref;
    }

    if ((g_ctrl.limited_vref < 0.0F) || (g_ctrl.limited_vref > g_ctrl.soft_vref))
        g_ctrl.limited_vref = g_ctrl.soft_vref;

    if (g_ctrl.iout > (current_limit + UF4_CC_ENTER_MARGIN_A))
    {
        g_ctrl.current_limit_active = 1U;
        g_ctrl.limited_vref -= UF4_CC_VREF_FALL_STEP_V;
    }
    else
    {
        g_ctrl.cc_integral = 0.0F;
        g_ctrl.current_limit_active = 0U;
        g_ctrl.limited_vref += UF4_CC_RECOVER_STEP_V;
    }

    if (g_ctrl.limited_vref < 0.0F)
        g_ctrl.limited_vref = 0.0F;
    if (g_ctrl.limited_vref > g_ctrl.soft_vref)
        g_ctrl.limited_vref = g_ctrl.soft_vref;

    return g_ctrl.limited_vref;
}

static float UF4_RunVoltageLoop(float vin, float vref, float duty_ff, float duty_min, float duty_max)
{
    float integral_candidate;
    float duty;
    const float error = vref - g_ctrl.vout;

    VErr2 = VErr1;
    VErr1 = VErr0;
    VErr0 = UF4_FloatToMilli(error);

    if (vref <= 0.01F)
    {
        g_ctrl.v_integral = 0.0F;
        u1 = u0;
        u0 = 0;
        return duty_min;
    }

    integral_candidate = g_ctrl.v_integral + (UF4_VLOOP_KI * error);
    integral_candidate = uf4_clampf(integral_candidate, UF4_VLOOP_INTEGRAL_MIN, UF4_VLOOP_INTEGRAL_MAX);

    duty = duty_ff + (UF4_VLOOP_KP * error) + integral_candidate;

    if (g_ctrl.iin > UF4_INPUT_FOLDBACK_LIMIT_A)
    {
        duty -= (g_ctrl.iin - UF4_INPUT_FOLDBACK_LIMIT_A) * UF4_INPUT_FOLDBACK_GAIN;
        integral_candidate *= 0.985F;
    }

    if (vin < (MIN_INPUT_START_VOLTAGE + UF4_INPUT_DROOP_MARGIN_V))
    {
        duty -= ((MIN_INPUT_START_VOLTAGE + UF4_INPUT_DROOP_MARGIN_V) - vin) * UF4_INPUT_DROOP_GAIN;
        integral_candidate *= 0.97F;
    }

    if ((g_ctrl.iout < UF4_LIGHT_LOAD_CURRENT_A) &&
        (g_ctrl.vout > (vref + UF4_LIGHT_LOAD_OVERVOLTAGE_MARGIN)))
    {
        if (duty > duty_ff)
            duty = duty_ff;
        integral_candidate *= 0.92F;
    }

    duty = uf4_clampf(duty, duty_min, duty_max);

    if (((duty >= duty_max) && (error > 0.0F)) || ((duty <= duty_min) && (error < 0.0F)))
        integral_candidate = g_ctrl.v_integral;

    g_ctrl.v_integral = integral_candidate;
    u1 = u0;
    u0 = UF4_FloatToMilli(duty);

    return duty;
}

static float UF4_ApplyDutySlew(float duty_target, float duty_max)
{
    float delta;
    float max_up = (DF.SMFlag == Rise) ? UF4_DUTY_SLEW_UP_RISE : UF4_DUTY_SLEW_UP;

    delta = duty_target - g_ctrl.duty_applied;
    if (delta > max_up)
        delta = max_up;
    else if (delta < -UF4_DUTY_SLEW_DOWN)
        delta = -UF4_DUTY_SLEW_DOWN;

    g_ctrl.duty_applied += delta;
    g_ctrl.duty_applied = uf4_clampf(g_ctrl.duty_applied, UF4_DUTY_MIN, duty_max);
    return g_ctrl.duty_applied;
}

static void UF4_ApplyDutyByMode(float duty_cmd)
{
    const int16_t duty_counts = (int16_t)(duty_cmd * (float)PERIOD + 0.5F);

    switch (DF.BBFlag)
    {
    case Buck:
        CtrValue.BuckDuty = duty_counts;
        CtrValue.BoostDuty = MIN_BOOST_DUTY1;
        break;

    case Boost:
        CtrValue.BuckDuty = MAX_BUCK_DUTY;
        CtrValue.BoostDuty = duty_counts;
        break;

    case Mix:
        CtrValue.BuckDuty = MAX_BUCK_DUTY1;
        CtrValue.BoostDuty = duty_counts;
        break;

    default:
        UF4_ApplyMinimumDuty();
        break;
    }

    if (CtrValue.BuckDuty > CtrValue.BUCKMaxDuty)
        CtrValue.BuckDuty = CtrValue.BUCKMaxDuty;
    if (CtrValue.BuckDuty < MIN_BUKC_DUTY)
        CtrValue.BuckDuty = MIN_BUKC_DUTY;
    if (CtrValue.BoostDuty > CtrValue.BoostMaxDuty)
        CtrValue.BoostDuty = CtrValue.BoostMaxDuty;
    if (CtrValue.BoostDuty < MIN_BOOST_DUTY)
        CtrValue.BoostDuty = MIN_BOOST_DUTY;
}

void PID_Init(void)
{
    UF4_ResetLoopState();
}

CCMRAM void BuckBoostVILoopCtlIsr(void)
{
    static uint8_t isr_prescaler = 0U;

    if (++isr_prescaler < UF4_ISR_PRESCALE)
        return;

    isr_prescaler = 0U;
    BuckBoostVILoopCtlPID();
}

/**
 * @brief BuckBoost电压电流环路控制PID函数。
 * 该函数用于实现BuckBoost电压电流环路控制的PID算法。
 * 在stm32g4xx_it.c文件中的HRTIM1_TIMD_IRQHandler中断函数里调用此函数。
 */
CCMRAM void BuckBoostVILoopCtlPID(void)
{
    const float target = SET_Value.Vout;
    const float ilimit = uf4_clampf(SET_Value.Iout, 0.0F, MAX_OUTPUT_CURRENT);
    float control_vref;
    float duty_ff;
    float duty_max;
    float duty_cmd;

    if ((DF.OUTPUT_Flag == 0U) || (DF.PWMENFlag == 0U) || (DF.SMFlag == Init) || (DF.SMFlag == Wait) || (DF.SMFlag == Err))
    {
        UF4_ResetLoopState();
        UF4_ApplyMinimumDuty();
        UF4_UpdatePwmCompare();
        return;
    }

    UF4_UpdateFilteredMeasurements();

    if (g_ctrl.control_seeded == 0U)
    {
        g_ctrl.soft_vref = g_ctrl.vout;
        g_ctrl.limited_vref = g_ctrl.vout;
        g_ctrl.duty_target = UF4_DUTY_MIN;
        g_ctrl.duty_applied = UF4_DUTY_MIN;
        g_ctrl.previous_mode = DF.BBFlag;
        g_ctrl.control_seeded = 1U;
    }

    if (++g_ctrl.control_divider < UF4_CONTROL_DIVIDER)
    {
        UF4_UpdatePwmCompare();
        return;
    }
    g_ctrl.control_divider = 0U;

    if (g_ctrl.vin < MIN_INPUT_START_VOLTAGE)
    {
        g_ctrl.v_integral = 0.0F;
        g_ctrl.cc_integral = 0.0F;
        g_ctrl.duty_target = UF4_DUTY_MIN;
        g_ctrl.duty_applied = UF4_DUTY_MIN;
        CtrValue.Vout_ref = 0;
        CtrValue.I_Limit = (int32_t)UF4_CurrentToAdc(ilimit);
        UF4_DebugLoopImeas = 0.0F;
        UF4_DebugLoopIref = ilimit;
        UF4_DebugLoopIrefV = 0.0F;
        UF4_ApplyMinimumDuty();
        UF4_UpdatePwmCompare();
        return;
    }

    UF4_UpdateSoftReference(target);
    control_vref = UF4_RunCurrentSupervisor(ilimit);

    CtrValue.Vout_ref = (int32_t)UF4_VoltageToAdc(control_vref);
    CtrValue.I_Limit = (int32_t)UF4_CurrentToAdc(ilimit);

    if ((DF.BBModeChange != 0U) || (g_ctrl.previous_mode != DF.BBFlag))
    {
        g_ctrl.v_integral *= 0.35F;
        g_ctrl.cc_integral = 0.0F;
        g_ctrl.previous_mode = DF.BBFlag;
        DF.BBModeChange = 0U;
    }

    CVCC_Mode = (g_ctrl.current_limit_active != 0U) ? CC : CV;
    UF4_DebugLoopImeas = g_ctrl.iout;
    UF4_DebugLoopIref = ilimit;
    UF4_DebugLoopIrefV = control_vref;

    duty_ff = UF4_GetDutyFeedForward(g_ctrl.vin, control_vref);
    duty_max = UF4_GetDutyMax();
    duty_cmd = UF4_RunVoltageLoop(g_ctrl.vin, control_vref, duty_ff, UF4_DUTY_MIN, duty_max);
    duty_cmd = UF4_ApplyDutySlew(duty_cmd, duty_max);

    i1 = i0;
    i0 = (int32_t)(control_vref * 1000.0F + 0.5F);
    CtrValue.Ilimitout = (int32_t)(duty_cmd * (float)PERIOD + 0.5F);
    UF4_ApplyDutyByMode(duty_cmd);
    UF4_UpdatePwmCompare();
}
