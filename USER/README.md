# USER 模块重构说明

本目录承载数字电源业务逻辑，遵循 STM32 HAL 风格命名，和 `APP` 层通过兼容接口衔接。

## 当前阶段

- 已迁移主控制逻辑到 `USER/Src/user_power.c`
- 已拆分 PWM 驱动到 `USER/Src/user_power_pwm.c`
- 已拆分 SPI Flash 参数存储到 `USER/Src/user_power_store.c`
- 当前默认实现：单向 Buck/Boost/Mix 控制骨架
- 预留双向电流检测（采样已保留正负方向换算），双向功率流策略后续补充
- USB CDC + TVLCOM 保持可用（`USB_Device` 直接对接 `USER`）

## 文件职责

- `Inc/user_power.h`: USER 电源控制总入口
- `Inc/user_power_cfg.h`: 采样、控制、保护默认参数
- `Inc/user_power_pwm.h`: HRTIM PWM 控制接口
- `Inc/user_power_store.h`: W25Q 参数存储接口
- `Src/user_power.c`: 状态机、采样换算、PI 控制、故障处理、慢任务
- `Src/user_power_pwm.c`: A/D 定时器占空比映射与输出启停
- `Src/user_power_store.c`: 参数读取/保存与 CRC 校验

## 与工程关系

工程已移除 `APP` 目录，业务代码集中在 `USER`，`Core/Src/main.c` 与 `USB_Device/App/usbd_cdc_if.c` 直接调用 `USER` 接口。

