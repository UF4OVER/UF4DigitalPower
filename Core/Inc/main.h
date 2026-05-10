/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.h
  * @brief          : Header for main.c file.
  *                   This file contains the common defines of the application.
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32g4xx_hal.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Exported types ------------------------------------------------------------*/
/* USER CODE BEGIN ET */

/* USER CODE END ET */

/* Exported constants --------------------------------------------------------*/
/* USER CODE BEGIN EC */

/* USER CODE END EC */

/* Exported macro ------------------------------------------------------------*/
/* USER CODE BEGIN EM */

/* USER CODE END EM */

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

/* USER CODE BEGIN EFP */

/* USER CODE END EFP */

/* Private defines -----------------------------------------------------------*/
#define ADC_VIN_Pin GPIO_PIN_0
#define ADC_VIN_GPIO_Port GPIOA
#define ADC_IIN_Pin GPIO_PIN_1
#define ADC_IIN_GPIO_Port GPIOA
#define ADC_VOUT_Pin GPIO_PIN_2
#define ADC_VOUT_GPIO_Port GPIOA
#define ADC_IOUT_Pin GPIO_PIN_3
#define ADC_IOUT_GPIO_Port GPIOA
#define ADC_TEMP_Pin GPIO_PIN_4
#define ADC_TEMP_GPIO_Port GPIOA
#define PWM_L2_Pin GPIO_PIN_14
#define PWM_L2_GPIO_Port GPIOB
#define PWM_H2_Pin GPIO_PIN_15
#define PWM_H2_GPIO_Port GPIOB
#define PWM_L1_Pin GPIO_PIN_8
#define PWM_L1_GPIO_Port GPIOA
#define PWM_H1_Pin GPIO_PIN_9
#define PWM_H1_GPIO_Port GPIOA
#define SPI3_CS_Pin GPIO_PIN_15
#define SPI3_CS_GPIO_Port GPIOA
#define LED4_Pin GPIO_PIN_2
#define LED4_GPIO_Port GPIOD
#define LED3_Pin GPIO_PIN_3
#define LED3_GPIO_Port GPIOB
#define LED2_Pin GPIO_PIN_4
#define LED2_GPIO_Port GPIOB
#define LED1_Pin GPIO_PIN_5
#define LED1_GPIO_Port GPIOB
#define DIV_SW_Pin GPIO_PIN_7
#define DIV_SW_GPIO_Port GPIOB
#define FAN_PWM_Pin GPIO_PIN_9
#define FAN_PWM_GPIO_Port GPIOB

/* USER CODE BEGIN Private defines */
#define LED_G_Pin LED1_Pin
#define LED_G_GPIO_Port LED1_GPIO_Port
#define LED_R_Pin LED2_Pin
#define LED_R_GPIO_Port LED2_GPIO_Port
#define BUZZER_Pin LED4_Pin
#define BUZZER_GPIO_Port LED4_GPIO_Port

/* USER CODE END Private defines */

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
