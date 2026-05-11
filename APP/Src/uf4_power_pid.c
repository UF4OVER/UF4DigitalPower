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

extern volatile uint16_t ADC1_RESULT[4];          // ADC1通道1~4采样结果
volatile int32_t VErr0 = 0, VErr1 = 0, VErr2 = 0; // 电压误差
volatile int32_t IErr0 = 0, IErr1 = 0;            // 电流误差
volatile int32_t u0 = 0, u1 = 0;                  // 电压环输出量
volatile int32_t i0 = 0, i1 = 0;                  // 电流环输出量
volatile _CVCC_Mode CVCC_Mode = CV;               // 恒流恒压模式标志位
volatile float UF4_DebugLoopImeas = 0.0F;         // 环路实际使用的电流反馈
volatile float UF4_DebugLoopIref = 0.0F;          // 电流内环参考
volatile float UF4_DebugLoopIrefV = 0.0F;         // 电压外环输出的电流参考

// 环路的参数buck输出-恒压-PID型补偿器
#define BUCKPIDb0 5271
#define BUCKPIDb1 -10363
#define BUCKPIDb2 5093
// 环路的参数BOOST输出-恒压-PID型补偿器
#define BOOSTPIDb0 8044
#define BOOSTPIDb1 -15813
#define BOOSTPIDb2 7772

#define ILOOP_KP 6 // 电流环PID补偿器P值
#define ILOOP_KI 3 // 电流环PID补偿器I值
#define ILOOP_KD 1 // 电流环PID补偿器D值

#define UF4_VLOOP_KP 0.50F
#define UF4_VLOOP_KI 0.002F
#define UF4_VLOOP_DIVIDER 50U
#define UF4_ILOOP_DIVIDER 8U
#define UF4_ILOOP_KP 0.010F
#define UF4_ILOOP_KI 0.00002F
#define UF4_ILOOP_INTEGRAL_MIN (-0.20F)
#define UF4_ILOOP_INTEGRAL_MAX 0.20F
#define UF4_CC_EPS 0.02F
#define UF4_ILIMIT_DISABLED_EPS 0.001F
#define UF4_LIGHT_LOAD_OVERVOLTAGE_MARGIN 0.05F
#define UF4_DUTY_MIN ((float)MIN_BUKC_DUTY / (float)PERIOD)
#define UF4_DUTY_MAX ((float)MAX_BUCK_DUTY / (float)PERIOD)
#define UF4_BOOST_DUTY_MAX ((float)MAX_BOOST_DUTY / (float)PERIOD)

static float v_int = 0.0F;
static float i_int = 0.0F;
static float iref_v = 0.0F;
static float iref = 0.0F;
static uint16_t v_loop_divider = 0U;
static uint16_t i_loop_divider = 0U;
static uint16_t previous_mode = NA;

static float uf4_clampf(float value, float min_value, float max_value)
{
    if (value < min_value)
        return min_value;
    if (value > max_value)
        return max_value;
    return value;
}

static uint32_t UF4_GetCalibratedVoutAdc(void)
{
    return (uint32_t)((ADC1_RESULT[2] * CAL_VOUT_K >> 12) + CAL_VOUT_B);
}

static uint32_t UF4_GetCalibratedIoutAdc(void)
{
    return (uint32_t)((ADC1_RESULT[3] * CAL_IOUT_K >> 12) + CAL_IOUT_B);
}

static void UF4_UpdatePwmCompare(void)
{
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_1, PERIOD - CtrValue.BuckDuty);
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_3, __HAL_HRTIM_GETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_1) >> 1);
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_D, HRTIM_COMPAREUNIT_1, CtrValue.BoostDuty);
}

static void UF4_ResetLoopState(void)
{
    v_int = 0.0F;
    i_int = 0.0F;
    iref_v = 0.0F;
    iref = 0.0F;
    v_loop_divider = 0U;
    i_loop_divider = 0U;
    previous_mode = DF.BBFlag;
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
}

static void UF4_ApplyMinimumDuty(void)
{
    CtrValue.BuckDuty = MIN_BUKC_DUTY;
    CtrValue.BoostDuty = MIN_BOOST_DUTY;
}

static float UF4_GetCurrentFeedback(float vin, float vout)
{
    const float iin = UF4_AdcToInputCurrent(ADC1_RESULT[1]);
    const float iout = UF4_AdcToOutputCurrent(UF4_GetCalibratedIoutAdc());

    if (DF.BBFlag == Buck)
    {
        float iin_as_output = iin;

        if (vout > 1.0F)
            iin_as_output = iin * vin / vout;

        return (iout > iin_as_output) ? iout : iin_as_output;
    }

    return iin;
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

static float UF4_RunVoltageLoop(float vref, float vout, float ilimit)
{
    float iref_cmd;
    const float error = vref - vout;

    if (ilimit <= UF4_ILIMIT_DISABLED_EPS)
    {
        v_int = 0.0F;
        u0 = 0;
        return 0.0F;
    }

    v_int += UF4_VLOOP_KI * error;
    v_int = uf4_clampf(v_int, 0.0F, ilimit);

    iref_cmd = (UF4_VLOOP_KP * error) + v_int;
    iref_cmd = uf4_clampf(iref_cmd, 0.0F, MAX_OUTPUT_CURRENT);
    u0 = UF4_FloatToMilli(iref_cmd);

    return iref_cmd;
}

static float UF4_RunCurrentLoop(float current_ref, float current_meas, float duty_ff, float duty_min, float duty_max, float zero_current_duty)
{
    float duty;
    const float error = current_ref - current_meas;

    IErr1 = IErr0;
    IErr0 = UF4_FloatToMilli(error);

    if (current_ref <= UF4_ILIMIT_DISABLED_EPS)
    {
        i_int = 0.0F;
        i1 = i0;
        duty = uf4_clampf(zero_current_duty, duty_min, duty_max);
        i0 = (int32_t)(duty * (float)PERIOD + 0.5F);
        CtrValue.Ilimitout = i0;
        return duty;
    }

    i_int += UF4_ILOOP_KI * error;
    i_int = uf4_clampf(i_int, UF4_ILOOP_INTEGRAL_MIN, UF4_ILOOP_INTEGRAL_MAX);

    duty = duty_ff + (UF4_ILOOP_KP * error) + i_int;
    duty = uf4_clampf(duty, duty_min, duty_max);

    i1 = i0;
    i0 = (int32_t)(duty * (float)PERIOD + 0.5F);
    CtrValue.Ilimitout = i0;

    return duty;
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

/**
 * @brief BuckBoost电压电流环路控制PID函数。
 * 该函数用于实现BuckBoost电压电流环路控制的PID算法。
 * 在stm32g4xx_it.c文件中的HRTIM1_TIMD_IRQHandler中断函数里调用此函数。
 */
CCMRAM void BuckBoostVILoopCtlPID(void)
{
    const float target = SET_Value.Vout;
    const float ilimit = (SET_Value.Iout > UF4_ILIMIT_DISABLED_EPS) ? SET_Value.Iout : 0.0F;
    const uint32_t vout_adc = UF4_GetCalibratedVoutAdc();
    float vin;
    float vout;
    float imeas;
    float duty_ff;
    float duty_max;
    float duty_cmd;
    float zero_current_duty;

    if ((DF.OUTPUT_Flag == 0U) || (DF.PWMENFlag == 0U) || (DF.SMFlag == Init) || (DF.SMFlag == Wait) || (DF.SMFlag == Err))
    {
        CVCC_Mode = CV;
        UF4_ResetLoopState();
        UF4_ApplyMinimumDuty();
        UF4_UpdatePwmCompare();
        return;
    }

    /*
     * HRTIM中断频率很高，完整浮点双环每次都跑会挤占USB/5ms状态机。
     * 先按分频运行内环，未到分频点时保持上一拍占空比。
     */
    if (++i_loop_divider < UF4_ILOOP_DIVIDER)
    {
        UF4_UpdatePwmCompare();
        return;
    }
    i_loop_divider = 0U;

    if ((DF.BBModeChange != 0U) || (previous_mode != DF.BBFlag))
    {
        i_int *= 0.2F;
        DF.BBModeChange = 0;
        previous_mode = DF.BBFlag;
    }

    vin = UF4_AdcToVoltage(ADC1_RESULT[0]);
    vout = UF4_AdcToVoltage(vout_adc);

    CtrValue.Vout_ref = (int32_t)UF4_VoltageToAdc(target);
    CtrValue.I_Limit = (int32_t)UF4_CurrentToAdc(ilimit);
    VErr2 = VErr1;
    VErr1 = VErr0;
    VErr0 = CtrValue.Vout_ref - (int32_t)vout_adc;

    if (vin < MIN_INPUT_START_VOLTAGE)
    {
        v_int = 0.0F;
        i_int = 0.0F;
        iref_v = 0.0F;
        iref = 0.0F;
        UF4_DebugLoopImeas = 0.0F;
        UF4_DebugLoopIref = 0.0F;
        UF4_DebugLoopIrefV = iref_v;
        UF4_ApplyMinimumDuty();
        UF4_UpdatePwmCompare();
        return;
    }

    if (++v_loop_divider >= UF4_VLOOP_DIVIDER)
    {
        v_loop_divider = 0U;
        iref_v = UF4_RunVoltageLoop(target, vout, ilimit);
    }

    iref = (iref_v < ilimit) ? iref_v : ilimit;
    CVCC_Mode = (iref_v >= (ilimit - UF4_CC_EPS)) ? CC : CV;

    imeas = UF4_GetCurrentFeedback(vin, vout);
    UF4_DebugLoopImeas = imeas;
    UF4_DebugLoopIref = iref;
    UF4_DebugLoopIrefV = iref_v;

    duty_ff = UF4_GetDutyFeedForward(vin, target);
    duty_max = UF4_GetDutyMax();

    zero_current_duty = UF4_DUTY_MIN;
    if ((ilimit > UF4_ILIMIT_DISABLED_EPS) && (vout < (target + UF4_LIGHT_LOAD_OVERVOLTAGE_MARGIN)))
        zero_current_duty = duty_ff;

    duty_cmd = UF4_RunCurrentLoop(iref, imeas, duty_ff, UF4_DUTY_MIN, duty_max, zero_current_duty);

    UF4_ApplyDutyByMode(duty_cmd);
    UF4_UpdatePwmCompare();
}
