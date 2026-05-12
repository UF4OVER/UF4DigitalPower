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

void PID_Init(void)
{
    VErr0 = 0;
    VErr1 = 0;
    VErr2 = 0;
    u0 = 0;
    u1 = 0;
    i0 = 0;
    IErr0 = 0;
}

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

#define UF4_VLOOP_DIVIDER 50U
#define UF4_VLOOP_KP 0.70F
#define UF4_VLOOP_KI 0.0030F
#define UF4_VLOOP_IREF_MIN 0.0F
#define UF4_ILIMIT_MARGIN 0.02F

#define UF4_ILOOP_KP 0.018F
#define UF4_ILOOP_KI 0.00012F
#define UF4_ILOOP_INTEGRAL_MIN (-0.25F)
#define UF4_ILOOP_INTEGRAL_MAX 0.25F

#define UF4_DUTY_MIN ((float)MIN_BUKC_DUTY / (float)PERIOD)
#define UF4_DUTY_MAX ((float)MAX_BUCK_DUTY / (float)PERIOD)
#define UF4_BOOST_DUTY_MAX ((float)MAX_BOOST_DUTY / (float)PERIOD)

static float uf4_clampf(float value, float min_value, float max_value)
{
    if (value < min_value)
        return min_value;
    if (value > max_value)
        return max_value;
    return value;
}

static void UF4_UpdatePwmCompare(void)
{
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_1, PERIOD - CtrValue.BuckDuty);
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_3,
                           __HAL_HRTIM_GETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_1) >> 1);
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_D, HRTIM_COMPAREUNIT_1, CtrValue.BoostDuty);
}

/**
 * @brief BuckBoost 双环控制函数。
 *
 * 控制结构：
 *   电压外环：Vref - Vout -> PI -> Iref
 *   电流内环：Iref - Iout -> PI -> duty_delta
 *   前馈：根据 BUCK/BOOST/MIX 模式计算基础 duty，电流内环只负责在前馈基础上修正占空比。
 *
 * 在 stm32g4xx_it.c 文件中的 HRTIM1_TIMD_IRQHandler 中断函数里调用此函数。
 */
CCMRAM void BuckBoostVILoopCtlPID(void)
{
    static float v_integral = 0.0F;      // 电压外环积分，单位 A
    static float i_integral = 0.0F;      // 电流内环积分，单位 duty
    static float current_ref = 0.0F;     // 外环输出给内环的电流参考，单位 A
    static uint16_t v_loop_divider = 0U;
    static uint16_t previous_mode = NA;

    if ((DF.OUTPUT_Flag == 0U) || (DF.PWMENFlag == 0U) || (DF.SMFlag == Init) || (DF.SMFlag == Wait) || (DF.SMFlag == Err))
    {
        CVCC_Mode = CV;
        v_integral = 0.0F;
        i_integral = 0.0F;
        current_ref = 0.0F;
        v_loop_divider = 0U;
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
        CtrValue.BuckDuty = MIN_BUKC_DUTY;
        CtrValue.BoostDuty = MIN_BOOST_DUTY;
        UF4_UpdatePwmCompare();
        return;
    }

    float vin = UF4_AdcToVoltage(ADC1_RESULT[0]);
    float vout = UF4_AdcToVoltage((ADC1_RESULT[2] * CAL_VOUT_K >> 12) + CAL_VOUT_B);
    float iout = UF4_AdcToOutputCurrent((ADC1_RESULT[3] * CAL_IOUT_K >> 12) + CAL_IOUT_B);
    float target = SET_Value.Vout;
    float ilimit = uf4_clampf(SET_Value.Iout, 0.0F, MAX_OUTPUT_CURRENT);
    float duty_ff = 0.0F;
    float duty_delta;
    float duty;
    float duty_max = UF4_DUTY_MAX;

    if (DF.SMFlag == Rise)
    {
        const float rise_limit = (float)CtrValue.BUCKMaxDuty / (float)PERIOD;
        duty_max = uf4_clampf(rise_limit, UF4_DUTY_MIN, UF4_DUTY_MAX);
    }

    if ((DF.BBModeChange != 0U) || (previous_mode != DF.BBFlag))
    {
        i_integral = 0.0F;
        v_loop_divider = 0U;
        DF.BBModeChange = 0;
        previous_mode = DF.BBFlag;
    }

    if (vin < 0.5F)
    {
        CtrValue.BuckDuty = MIN_BUKC_DUTY;
        CtrValue.BoostDuty = MIN_BOOST_DUTY;
        UF4_UpdatePwmCompare();
        return;
    }

    CtrValue.Vout_ref = (int32_t)UF4_VoltageToAdc(target);
    CtrValue.Iout_ref = (int32_t)UF4_CurrentToAdc(ilimit);
    VErr0 = CtrValue.Vout_ref - (int32_t)((ADC1_RESULT[2] * CAL_VOUT_K >> 12) + CAL_VOUT_B);

    if (++v_loop_divider >= UF4_VLOOP_DIVIDER)
    {
        const float v_error = target - vout;
        const float current_margin = (ilimit > UF4_ILIMIT_MARGIN) ? UF4_ILIMIT_MARGIN : 0.0F;
        const float iref_max = uf4_clampf(ilimit - current_margin, UF4_VLOOP_IREF_MIN, MAX_OUTPUT_CURRENT);

        v_loop_divider = 0U;
        v_integral += UF4_VLOOP_KI * v_error;
        v_integral = uf4_clampf(v_integral, UF4_VLOOP_IREF_MIN, iref_max);
        current_ref = (UF4_VLOOP_KP * v_error) + v_integral;
        current_ref = uf4_clampf(current_ref, UF4_VLOOP_IREF_MIN, iref_max);

        u0 = UF4_FloatToMilli(current_ref);
        u1 = UF4_FloatToMilli(v_integral);
    }

    if (ilimit <= 0.001F)
    {
        current_ref = 0.0F;
        v_integral = 0.0F;
    }

    CVCC_Mode = (current_ref >= (ilimit - 0.05F)) ? CC : CV;
    CtrValue.I_Limit = (int32_t)UF4_CurrentToAdc(current_ref);
    CtrValue.Ilimitout = UF4_FloatToMilli(current_ref);

    IErr0 = UF4_FloatToMilli(current_ref - iout);
    duty_delta = (UF4_ILOOP_KP * (current_ref - iout)) + i_integral;
    i_integral += UF4_ILOOP_KI * (current_ref - iout);
    i_integral = uf4_clampf(i_integral, UF4_ILOOP_INTEGRAL_MIN, UF4_ILOOP_INTEGRAL_MAX);
    i0 = UF4_FloatToMilli(duty_delta);
    i1 = UF4_FloatToMilli(i_integral);

    switch (DF.BBFlag)
    {
    case Buck:
        duty_ff = target / vin;
        duty = duty_ff + duty_delta;
        duty = uf4_clampf(duty, UF4_DUTY_MIN, duty_max);
        CtrValue.BuckDuty = (int16_t)(duty * (float)PERIOD + 0.5F);
        CtrValue.BoostDuty = MIN_BOOST_DUTY1;
        break;

    case Boost:
        duty_ff = 1.0F - (vin / uf4_clampf(target, 1.0F, MAX_OUTPUT_VOLTAGE));
        duty = duty_ff + duty_delta;
        duty = uf4_clampf(duty, UF4_DUTY_MIN, UF4_BOOST_DUTY_MAX);
        CtrValue.BuckDuty = MAX_BUCK_DUTY;
        CtrValue.BoostDuty = (int16_t)(duty * (float)PERIOD + 0.5F);
        break;

    case Mix:
        duty_ff = (target > vin) ? (1.0F - (vin / uf4_clampf(target, 1.0F, MAX_OUTPUT_VOLTAGE))) : UF4_DUTY_MIN;
        duty = duty_ff + duty_delta;
        duty = uf4_clampf(duty, UF4_DUTY_MIN, UF4_BOOST_DUTY_MAX);
        CtrValue.BuckDuty = MAX_BUCK_DUTY1;
        CtrValue.BoostDuty = (int16_t)(duty * (float)PERIOD + 0.5F);
        break;

    default:
        CtrValue.BuckDuty = MIN_BUKC_DUTY;
        CtrValue.BoostDuty = MIN_BOOST_DUTY;
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

    UF4_UpdatePwmCompare();
}
