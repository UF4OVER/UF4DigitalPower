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

#define UF4_VLOOP_KP 0.025F
#define UF4_VLOOP_KI 0.00008F
#define UF4_VLOOP_DIVIDER 50U
#define UF4_VLOOP_INTEGRAL_MIN (-0.2F)
#define UF4_VLOOP_INTEGRAL_MAX 0.2F
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

/**
 * @brief BuckBoost电压电流环路控制PID函数。
 * 该函数用于实现BuckBoost电压电流环路控制的PID算法。
 * 在stm32g4xx_it.c文件中的HRTIM1_TIMD_IRQHandler中断函数里调用此函数。
 */
CCMRAM void BuckBoostVILoopCtlPID(void)
{
    static int32_t I_Integral = 0; // 电流环路积分量
    static float v_integral = 0.0F;
    static uint16_t v_loop_divider = 0U;
    static uint16_t previous_mode = NA;

    if ((DF.OUTPUT_Flag == 0U) || (DF.PWMENFlag == 0U) || (DF.SMFlag == Init) || (DF.SMFlag == Wait) || (DF.SMFlag == Err))
    {
        CVCC_Mode = CV;
        I_Integral = 0;
        v_integral = 0.0F;
        v_loop_divider = 0U;
        previous_mode = DF.BBFlag;
        i0 = 0;
        IErr0 = 0;
        IErr1 = 0;
        CtrValue.BuckDuty = MIN_BUKC_DUTY;
        CtrValue.BoostDuty = MIN_BOOST_DUTY;
        __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_1, PERIOD - CtrValue.BuckDuty);
        __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_D, HRTIM_COMPAREUNIT_1, CtrValue.BoostDuty);
        return;
    }

    if (++v_loop_divider < UF4_VLOOP_DIVIDER)
    {
        __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_1, PERIOD - CtrValue.BuckDuty);
        __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_3, __HAL_HRTIM_GETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_1) >> 1);
        __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_D, HRTIM_COMPAREUNIT_1, CtrValue.BoostDuty);
        return;
    }
    v_loop_divider = 0U;

    float vin = UF4_AdcToVoltage(ADC1_RESULT[0]);
    float vout = UF4_AdcToVoltage((ADC1_RESULT[2] * CAL_VOUT_K >> 12) + CAL_VOUT_B);
    float iout = UF4_AdcToOutputCurrent((ADC1_RESULT[3] * CAL_IOUT_K >> 12) + CAL_IOUT_B);
    float target = SET_Value.Vout;
    float error;
    float duty_ff;
    float duty;
    float duty_max = UF4_DUTY_MAX;

    if (DF.SMFlag == Rise)
    {
        const float rise_limit = (float)CtrValue.BUCKMaxDuty / (float)PERIOD;
        duty_max = uf4_clampf(rise_limit, UF4_DUTY_MIN, UF4_DUTY_MAX);
    }

    if ((DF.BBModeChange != 0U) || (previous_mode != DF.BBFlag))
    {
        v_integral = 0.0F;
        v_loop_divider = 0U;
        DF.BBModeChange = 0;
        previous_mode = DF.BBFlag;
    }

    if (vin < 0.5F)
    {
        CtrValue.BuckDuty = MIN_BUKC_DUTY;
        CtrValue.BoostDuty = MIN_BOOST_DUTY;
        goto update_pwm;
    }

    CtrValue.Vout_ref = (int32_t)UF4_VoltageToAdc(target);
    VErr0 = CtrValue.Vout_ref - (int32_t)((ADC1_RESULT[2] * CAL_VOUT_K >> 12) + CAL_VOUT_B);
    error = target - vout;

    v_integral += UF4_VLOOP_KI * error;
    v_integral = uf4_clampf(v_integral, UF4_VLOOP_INTEGRAL_MIN, UF4_VLOOP_INTEGRAL_MAX);

    CVCC_Mode = CV;
    if ((SET_Value.Iout > 0.001F) && (iout > SET_Value.Iout))
    {
        CVCC_Mode = CC;
        v_integral -= 0.01F;
        v_integral = uf4_clampf(v_integral, UF4_VLOOP_INTEGRAL_MIN, UF4_VLOOP_INTEGRAL_MAX);
    }

    switch (DF.BBFlag)
    {
    case Buck:
        duty_ff = target / vin;
        duty = duty_ff + (UF4_VLOOP_KP * error) + v_integral;
        duty = uf4_clampf(duty, UF4_DUTY_MIN, duty_max);
        CtrValue.BuckDuty = (int16_t)(duty * (float)PERIOD + 0.5F);
        CtrValue.BoostDuty = MIN_BOOST_DUTY1;
        break;

    case Boost:
        duty_ff = 1.0F - (vin / uf4_clampf(target, 1.0F, MAX_OUTPUT_VOLTAGE));
        duty = duty_ff + (UF4_VLOOP_KP * error) + v_integral;
        duty = uf4_clampf(duty, UF4_DUTY_MIN, UF4_BOOST_DUTY_MAX);
        CtrValue.BuckDuty = MAX_BUCK_DUTY;
        CtrValue.BoostDuty = (int16_t)(duty * (float)PERIOD + 0.5F);
        break;

    case Mix:
        duty_ff = (target > vin) ? (1.0F - (vin / uf4_clampf(target, 1.0F, MAX_OUTPUT_VOLTAGE))) : UF4_DUTY_MIN;
        duty = duty_ff + (UF4_VLOOP_KP * error) + v_integral;
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

update_pwm:
    // 更新对应寄存器
    // buck占空比
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_1, PERIOD - CtrValue.BuckDuty);
    // ADC触发采样点，buck占空比的一半，右移1位为除以2
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_3, __HAL_HRTIM_GETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_1) >> 1);
    // Boost占空比
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_D, HRTIM_COMPAREUNIT_1, CtrValue.BoostDuty);
}
