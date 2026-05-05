/* USER_Code CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
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
#include "adc.h"
#include "dma.h"
#include "hrtim.h"
#include "spi.h"
#include "tim.h"
#include "usart.h"
#include "usb_device.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER_Code CODE BEGIN Includes */
#include "app_power.h"
/* USER_Code CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER_Code CODE BEGIN PTD */

/* USER_Code CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER_Code CODE BEGIN PD */

/* USER_Code CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER_Code CODE BEGIN PM */

/* USER_Code CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER_Code CODE BEGIN PV */
static volatile uint32_t g_tick_1ms = 0U;
/* USER_Code CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER_Code CODE BEGIN PFP */
static void PowerControl_StartRuntime(void);
/* USER_Code CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER_Code CODE BEGIN 0 */
static void PowerControl_StartRuntime(void)
{
  PowerApp_Init();
}

/* USER_Code CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER_Code CODE BEGIN 1 */

  /* USER_Code CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER_Code CODE BEGIN Init */

  /* USER_Code CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER_Code CODE BEGIN SysInit */

  /* USER_Code CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_HRTIM1_Init();
  MX_ADC1_Init();
  MX_ADC2_Init();
  MX_ADC5_Init();
  MX_SPI3_Init();
  MX_TIM4_Init();
  MX_USB_Device_Init();
  MX_TIM2_Init();
  MX_TIM3_Init();
  MX_TIM8_Init();
  MX_USART1_UART_Init();
  MX_USART3_UART_Init();
  MX_TIM6_Init();
  MX_TIM7_Init();
  MX_TIM16_Init();
  MX_TIM17_Init();
  /* USER_Code CODE BEGIN 2 */

  PowerControl_StartRuntime();

  /* USER_Code CODE END 2 */

  /* Infinite loop */
  /* USER_Code CODE BEGIN WHILE */
  while (1)
  {
    /* USER_Code CODE END WHILE */

    /* USER_Code CODE BEGIN 3 */
    /* Keep non-time-critical work in foreground loop. */
    PowerApp_BackgroundTask();
    HAL_Delay(1);
  }
  /* USER_Code CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1_BOOST);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI48|RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.HSI48State = RCC_HSI48_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = RCC_PLLM_DIV5;
  RCC_OscInitStruct.PLL.PLLN = 68;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = RCC_PLLQ_DIV6;
  RCC_OscInitStruct.PLL.PLLR = RCC_PLLR_DIV2;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_4) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER_Code CODE BEGIN 4 */
void HAL_HRTIM_RepetitionEventCallback(HRTIM_HandleTypeDef *hhrtim, uint32_t TimerIdx)
{
  if ((hhrtim == &hhrtim1) && (TimerIdx == HRTIM_TIMERINDEX_TIMER_A))
  {
    PowerApp_FastLoop();
  }
}

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
  if (htim->Instance == TIM2)
  {
    g_tick_1ms++;
    if ((g_tick_1ms % 1000U) == 0U)
    {
      HAL_GPIO_TogglePin(LED1_GPIO_Port, LED1_Pin);
    }
    PowerApp_1msTask();
  }
  else if (htim->Instance == TIM3)
  {
    PowerApp_5msTask();
  }
  else if (htim->Instance == TIM4)
  {
    PowerApp_CommTask();
  }
}

/* USER_Code CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER_Code CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER_Code CODE END Error_Handler_Debug */
}

#ifdef  USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER_Code CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER_Code CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
