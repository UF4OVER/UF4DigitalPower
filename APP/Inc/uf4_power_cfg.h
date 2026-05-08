/**
 * @file    : uf4_power_cfg.h
 * @brief   :
 * @author  : UF4
 * @date    : 2026/5/8 21:09
 * @version : CLion
 * @project : UF4DigitalPower
 * @details : 
 * TODO: 请填写详细说明
 */

#ifndef UF4DIGITALPOWER_UF4_POWER_CFG_H
#define UF4DIGITALPOWER_UF4_POWER_CFG_H

#ifdef __cplusplus
extern "C" {
#endif

/* Exported types ------------------------------------------------------------*/

#define CCMRAM __attribute__((section("ccmram")))

#define ADC_MAX_VALUE 8190.0F				   // ADC最大值
#define REF_3V3 3.2806F						   // VREF参考电压
#define TS_CAL1 *((__IO uint16_t *)0x1FFF75A8) // 内部温度传感器在30度和VREF为3V时的校准数据
#define TS_CAL2 *((__IO uint16_t *)0x1FFF75CA) // 内部温度传感器在130度和VREF为3V时的校准数据
#define TS_CAL1_TEMP 30.0F
#define TS_CAL2_TEMP 130.0F

#define MIN_BUKC_DUTY 100	  // BUCK最小占空比
#define MAX_BUCK_DUTY 28200	  // BUCK最大占空比94%
#define MAX_BUCK_DUTY1 24000  // MIX模式下 BUCK固定占空比80%
#define MIN_BOOST_DUTY 100	  // BOOST最小占空比
#define MIN_BOOST_DUTY1 1800  // BOOST最小占空6%
#define MAX_BOOST_DUTY 19500  // BOOST工作模式下最大占空比65%
#define MAX_BOOST_DUTY1 28200 // BOOST最大占空比94%

#define CAL_VOUT_K 4099 // 输出电压矫正K值
#define CAL_VOUT_B 1	// 输出电压矫正B值
#define CAL_IOUT_K 4095 // 输出电流矫正K值
#define CAL_IOUT_B 1	// 输出电流矫正B值

    /***************故障类型*****************/
#define F_NOERR 0x0000		 // 无故障
#define F_SW_VIN_UVP 0x0001	 // 输入欠压
#define F_SW_VIN_OVP 0x0002	 // 输入过压
#define F_SW_VOUT_UVP 0x0004 // 输出欠压
#define F_SW_VOUT_OVP 0x0008 // 输出过压
#define F_SW_IOUT_OCP 0x0010 // 输出过流
#define F_SW_SHORT 0x0020	 // 输出短路
#define F_OTP 0x0040		 // 温度过高

/* Exported constants --------------------------------------------------------*/
/* Exported macro ------------------------------------------------------------*/
/* Exported function prototypes ----------------------------------------------*/

#ifdef __cplusplus
}
#endif

#endif /* UF4DIGITALPOWER_UF4_POWER_CFG_H */