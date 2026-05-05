/* USER_Code CODE BEGIN Header */
/**
  ******************************************************************************
  * @file         stm32g4xx_hal_msp.c
  * @brief        This file provides code for the MSP Initialization
  *               and de-Initialization codes.
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
/* USER_Code CODE END Header */

/* Includes ------------------------------------------------------------------*/
#include "main.h"
/* USER_Code CODE BEGIN Includes */

/* USER_Code CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER_Code CODE BEGIN TD */

/* USER_Code CODE END TD */

/* Private define ------------------------------------------------------------*/
/* USER_Code CODE BEGIN Define */

/* USER_Code CODE END Define */

/* Private macro -------------------------------------------------------------*/
/* USER_Code CODE BEGIN Macro */

/* USER_Code CODE END Macro */

/* Private variables ---------------------------------------------------------*/
/* USER_Code CODE BEGIN PV */

/* USER_Code CODE END PV */

/* Private function prototypes -----------------------------------------------*/
/* USER_Code CODE BEGIN PFP */

/* USER_Code CODE END PFP */

/* External functions --------------------------------------------------------*/
/* USER_Code CODE BEGIN ExternalFunctions */

/* USER_Code CODE END ExternalFunctions */

/* USER_Code CODE BEGIN 0 */

/* USER_Code CODE END 0 */
/**
  * Initializes the Global MSP.
  */
void HAL_MspInit(void)
{

  /* USER_Code CODE BEGIN MspInit 0 */

  /* USER_Code CODE END MspInit 0 */

  __HAL_RCC_SYSCFG_CLK_ENABLE();
  __HAL_RCC_PWR_CLK_ENABLE();

  /* System interrupt init*/

  /** Disable the internal Pull-Up in Dead Battery pins of UCPD peripheral
  */
  HAL_PWREx_DisableUCPDDeadBattery();

  /* USER_Code CODE BEGIN MspInit 1 */

  /* USER_Code CODE END MspInit 1 */
}

/* USER_Code CODE BEGIN 1 */

/* USER_Code CODE END 1 */
