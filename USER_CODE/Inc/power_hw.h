//
// Created by UF4 on 2026/4/26.
//

#ifndef UF4DIGITALPOWER_POWER_HW_H
#define UF4DIGITALPOWER_POWER_HW_H

#include "hrtim.h"

/* ===== 功率桥映射 ===== */
#define BUCK_TIMER      HRTIM_TIMERINDEX_TIMER_A
#define BOOST_TIMER     HRTIM_TIMERINDEX_TIMER_D

#define BUCK_OUT_L      HRTIM_OUTPUT_TA1
#define BUCK_OUT_H      HRTIM_OUTPUT_TA2

#define BOOST_OUT_L     HRTIM_OUTPUT_TD1
#define BOOST_OUT_H     HRTIM_OUTPUT_TD2

/* ===== PWM控制 ===== */
static inline void PWM_Start_All(void)
{
    HAL_HRTIM_WaveformOutputStart(&hhrtim1,
        BUCK_OUT_L | BUCK_OUT_H |
        BOOST_OUT_L | BOOST_OUT_H);
}

static inline void PWM_Stop_All(void)
{
    HAL_HRTIM_WaveformOutputStop(&hhrtim1,
        BUCK_OUT_L | BUCK_OUT_H |
        BOOST_OUT_L | BOOST_OUT_H);
}

static inline void BUCK_SetDuty(uint16_t duty)
{
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, BUCK_TIMER,
        HRTIM_COMPAREUNIT_1, duty);
}

static inline void BOOST_SetDuty(uint16_t duty)
{
    __HAL_HRTIM_SETCOMPARE(&hhrtim1, BOOST_TIMER,
        HRTIM_COMPAREUNIT_1, duty);
}

#endif
