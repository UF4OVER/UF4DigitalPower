#include "../Inc/user_power_pwm.h"

#include "../Inc/user_power_cfg.h"

#include "hrtim.h"

#define USER_PWR_PWM_PERIOD        26000U
#define USER_PWR_BUCK_MIN_COMPARE  260U
#define USER_PWR_BOOST_MIN_COMPARE 260U
#define USER_PWR_BOOST_FIXED_BUCK  1560U
#define USER_PWR_BUCK_FIXED_MIX    20800U
#define USER_PWR_BUCK_FIXED_BOOST  24440U

static uint8_t g_synchronous_enabled = 0U;

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

void UserPowerPwm_Init(user_power_status_t *status)
{
    UserPowerPwm_Stop(status);
}

void UserPowerPwm_Start(void)
{
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_1, USER_PWR_PWM_PERIOD);
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_3, USER_PWR_PWM_PERIOD / 2U);
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_D, HRTIM_COMPAREUNIT_1, USER_PWR_PWM_PERIOD);

    g_synchronous_enabled = 1U;
    (void)HAL_HRTIM_WaveformOutputStart(&hhrtim1, HRTIM_OUTPUT_TA1 | HRTIM_OUTPUT_TA2);
    (void)HAL_HRTIM_WaveformOutputStart(&hhrtim1, HRTIM_OUTPUT_TD1 | HRTIM_OUTPUT_TD2);
}

void UserPowerPwm_SetSynchronous(uint8_t enabled)
{
    g_synchronous_enabled = enabled ? 1U : 0U;
}

void UserPowerPwm_Stop(user_power_status_t *status)
{
    (void)HAL_HRTIM_WaveformOutputStop(&hhrtim1, HRTIM_OUTPUT_TA1 | HRTIM_OUTPUT_TA2);
    (void)HAL_HRTIM_WaveformOutputStop(&hhrtim1, HRTIM_OUTPUT_TD1 | HRTIM_OUTPUT_TD2);

    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_1, USER_PWR_PWM_PERIOD);
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_D, HRTIM_COMPAREUNIT_1, USER_PWR_PWM_PERIOD);
    g_synchronous_enabled = 0U;

    if (status != NULL)
    {
        status->pwm_a_compare = USER_PWR_PWM_PERIOD;
        status->pwm_d_compare = USER_PWR_PWM_PERIOD;
    }
}

void UserPowerPwm_ApplyDuty(user_power_topology_t topology, float duty, user_power_status_t *status)
{
    uint16_t compare_a;
    uint16_t compare_d;

    duty = user_pwr_clamp(duty, USER_PWR_DUTY_MIN, USER_PWR_DUTY_MAX);

    switch (topology)
    {
    case USER_POWER_TOPOLOGY_BUCK:
        compare_a = (uint16_t)(USER_PWR_PWM_PERIOD * (1.0f - duty));
        compare_a = (uint16_t)user_pwr_clamp((float)compare_a,
                                             (float)(USER_PWR_PWM_PERIOD - (USER_PWR_PWM_PERIOD * 0.94f)),
                                             (float)(USER_PWR_PWM_PERIOD - USER_PWR_BUCK_MIN_COMPARE));
        compare_d = USER_PWR_BOOST_FIXED_BUCK;
        break;
    case USER_POWER_TOPOLOGY_BOOST:
        compare_a = (uint16_t)(USER_PWR_PWM_PERIOD - USER_PWR_BUCK_FIXED_BOOST);
        compare_d = (uint16_t)(USER_PWR_PWM_PERIOD * duty);
        compare_d = (uint16_t)user_pwr_clamp((float)compare_d, (float)USER_PWR_BOOST_MIN_COMPARE, USER_PWR_PWM_PERIOD * 0.94f);
        break;
    case USER_POWER_TOPOLOGY_MIX:
        compare_a = (uint16_t)(USER_PWR_PWM_PERIOD - USER_PWR_BUCK_FIXED_MIX);
        compare_d = (uint16_t)(USER_PWR_PWM_PERIOD * duty);
        compare_d = (uint16_t)user_pwr_clamp((float)compare_d, (float)USER_PWR_BOOST_MIN_COMPARE, USER_PWR_PWM_PERIOD * 0.94f);
        break;
    default:
        compare_a = USER_PWR_PWM_PERIOD;
        compare_d = USER_PWR_PWM_PERIOD;
        break;
    }

    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_1, compare_a);
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_A, HRTIM_COMPAREUNIT_3, compare_a / 2U);
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, HRTIM_TIMERINDEX_TIMER_D, HRTIM_COMPAREUNIT_1, compare_d);

    if (status != NULL)
    {
        status->pwm_a_compare = compare_a;
        status->pwm_d_compare = compare_d;
    }
}

