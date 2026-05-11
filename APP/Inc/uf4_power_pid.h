/**
 * @file    : uf4_power_pid.h
 * @brief   : TODO: 请填写模块功能简介
 * @author  : UF4
 * @date    : 2026/5/8 21:29
 * @version : CLion
 * @project : UF4DigitalPower
 * @details : 
 * TODO: 请填写详细说明
 */

#ifndef UF4DIGITALPOWER_UF4_POWER_PID_H
#define UF4DIGITALPOWER_UF4_POWER_PID_H

#ifdef __cplusplus
extern "C" {
#endif

/* Exported types ------------------------------------------------------------*/

//一个开关周期数字量
#define PERIOD 30000

/* Exported constants --------------------------------------------------------*/
/* Exported macro ------------------------------------------------------------*/
/* Exported function prototypes ----------------------------------------------*/

void PID_Init(void);
void BuckBoostVILoopCtlIsr(void);
void BuckBoostVILoopCtlPID(void);

#ifdef __cplusplus
}
#endif

#endif /* UF4DIGITALPOWER_UF4_POWER_PID_H */