# UF4DigitalPower

本项目是基于 STM32G474 的数字电源控制固件，目标输出范围为 `0.5-44V`、`0-10A`，支持 BUCK / BOOST / MIX 模式切换、软启动、故障保护、Flash 参数存储和 TVLCOM 上位机通信。

## 控制逻辑总览

以下逻辑以当前代码实现为准（主要位于 `APP/Src/uf4_power_main.c`、`APP/Src/uf4_power_pid.c`、`APP/Src/uf4_tvlcom.c`）。

### 1) 采样与物理量换算

- 采样来源：`ADC1_RESULT[4]`，对应 `Vin/Iin/Vout/Iout`。
- 采样滤波：`ADCSample()` 中使用滑动平均（等效一阶 IIR）更新 `SADC.*Avg`。
- 电压换算：`UF4_AdcToVoltage()`，将 ADC 码值按 `ADC_REF_VOLTAGE` 与分压比还原真实电压。
- 电流基础换算：`UF4_AdcToCurrent()`，以电流采样中点偏置 `CURRENT_ADC_ZERO_V` 为零点做双向换算。
- 输入/输出电流方向修正：
  - `UF4_AdcToInputCurrent()`
  - `UF4_AdcToOutputCurrent()`
  两者均做方向统一并限制下限为 `0`，避免上位机读到负电流后被显示层压成 `0`。
- 实时物理量更新：`ADC_calculate()` 周期性更新全局 `VIN/VOUT/IIN/IOUT`。

### 2) 状态机与启动流程

状态机入口：`StateM()`（5ms 节拍）。主状态：

- `Init`：参数初始化（`ValInit()`），然后进入 `Wait`。
- `Wait`：等待输出使能与输入电压就绪，稳定延时后进入 `Rise`。
- `Rise`：软启动流程（`SSInit -> SSWait -> SSRun`）。
- `Run`：正常运行，若输入掉线则退回 `Wait`。
- `Err`：故障锁定，关闭 PWM，等待故障清除后回 `Wait`。

`UF4_InputReady()` 使用输入电压阈值 `MIN_INPUT_START_VOLTAGE` 判定系统是否允许启动/维持运行。

### 3) 输出开关与设定更新行为

- 输出开关：`UF4_PowerSetOutputEnabled()`
  - 关闭输出：立即停 PWM，状态机回 `Wait`。
  - 开启输出：触发 `UF4_PowerRestartOutput()`，重新走软启动。
- 参数生效：`UF4_PowerApplySetpoints()`
  - 对 `SET_Value.Vout/Iout` 做范围钳位。
  - 生成 `CtrValue.Vout_SETref` 与 `CtrValue.Iout_ref`。
- 上位机在线改 `Vout/Iout`：`handle_write()` 仅调用 `UF4_PowerApplySetpoints()`，不再重启输出，避免运行中从零重新起跳。

### 4) 环路控制（核心）

环路函数：`BuckBoostVILoopCtlPID()`（HRTIM 中断调用）。

- 当前实现为**主电压环 + 电流限幅判定**：
  - 电压误差：`error = target - vout`
  - 电压环：`KP + KI`（含积分限幅）计算占空比修正
  - 电流限制：当 `iout > SET_Value.Iout` 时切 `CC` 标志，并对积分项执行回退抑制
- 运行模式输入：`DF.BBFlag`（Buck / Boost / Mix），分别采用不同前馈与占空比映射。
- 保护边界：占空比最终受 `MIN/MAX` 与软启动阶段 `BUCKMaxDuty/BoostMaxDuty` 双重限制。

#### 4.1 `BuckBoostVILoopCtlPID()` 占空比映射（BUCK / BOOST / MIX）

本节只描述当前代码中的**实际映射过程**。

1. 公共计算（进入模式分支之前）

- 采样量：
  - `vin = UF4_AdcToVoltage(ADC1_RESULT[0])`
  - `vout = UF4_AdcToVoltage(...)`
  - `iout = UF4_AdcToOutputCurrent(...)`
- 目标值：`target = SET_Value.Vout`
- 误差：`error = target - vout`
- 积分：`v_integral += UF4_VLOOP_KI * error`，并限幅到 `UF4_VLOOP_INTEGRAL_MIN ~ UF4_VLOOP_INTEGRAL_MAX`
- CC 判定：当 `SET_Value.Iout > 0.001` 且 `iout > SET_Value.Iout`，置 `CVCC_Mode = CC`，并让 `v_integral` 额外回退 `0.01`
- 软启动限制：
  - 正常运行 `duty_max = UF4_DUTY_MAX`
  - `Rise` 阶段 `duty_max = clamp(BUCKMaxDuty/PERIOD, UF4_DUTY_MIN, UF4_DUTY_MAX)`
- 输入欠压保护：若 `vin < 0.5V`，直接置最小占空比并返回，不执行后续映射。

2. BUCK 模式映射（`DF.BBFlag == Buck`）

- 前馈：`duty_ff = target / vin`
- 控制量：`duty = duty_ff + UF4_VLOOP_KP * error + v_integral`
- 限幅：`duty = clamp(duty, UF4_DUTY_MIN, duty_max)`
- 占空比落地：
  - `BuckDuty = (int16_t)(duty * PERIOD + 0.5)`
  - `BoostDuty = MIN_BOOST_DUTY1`（BOOST 臂维持最小导通）

3. BOOST 模式映射（`DF.BBFlag == Boost`）

- 前馈：`duty_ff = 1 - vin / clamp(target, 1.0, MAX_OUTPUT_VOLTAGE)`
- 控制量：`duty = duty_ff + UF4_VLOOP_KP * error + v_integral`
- 限幅：`duty = clamp(duty, UF4_DUTY_MIN, UF4_BOOST_DUTY_MAX)`
- 占空比落地：
  - `BuckDuty = MAX_BUCK_DUTY`（Buck 臂固定在高占空比）
  - `BoostDuty = (int16_t)(duty * PERIOD + 0.5)`

4. MIX 模式映射（`DF.BBFlag == Mix`）

- 前馈：
  - 若 `target > vin`：`duty_ff = 1 - vin / clamp(target, 1.0, MAX_OUTPUT_VOLTAGE)`
  - 否则：`duty_ff = UF4_DUTY_MIN`
- 控制量：`duty = duty_ff + UF4_VLOOP_KP * error + v_integral`
- 限幅：`duty = clamp(duty, UF4_DUTY_MIN, UF4_BOOST_DUTY_MAX)`
- 占空比落地：
  - `BuckDuty = MAX_BUCK_DUTY1`
  - `BoostDuty = (int16_t)(duty * PERIOD + 0.5)`

5. 模式后统一硬限制（所有模式共用）

- `BuckDuty` 最终限制到 `[MIN_BUKC_DUTY, BUCKMaxDuty]`
- `BoostDuty` 最终限制到 `[MIN_BOOST_DUTY, BoostMaxDuty]`

6. 寄存器映射（PWM 输出）

- Buck 比较值：`CMPA1 = PERIOD - BuckDuty`
- Buck 采样触发点：`CMPA3 = CMPA1 / 2`
- Boost 比较值：`CMPD1 = BoostDuty`

7. 关键实现特性（便于调试）

- 模式切换时（`DF.BBModeChange`）会清 `v_integral`，避免 Buck/Boost/Mix 切换瞬间积分延续导致过冲。
- 电压环按分频执行（`UF4_VLOOP_DIVIDER`），但 PWM 寄存器每次中断都会刷新。
- 软启动阶段除了状态机抬升 `BUCKMaxDuty/BoostMaxDuty` 外，环路层还有 `duty_max` 约束，双层避免启动过冲。

### 5) BUCK/BOOST/MIX 模式切换

模式判断函数：`BBMode()`。

- 根据 `Vout_ref` 与 `Vin` 比值切换：
  - Buck：`Vout_ref < 0.8 * Vin`
  - Boost：`Vout_ref > 1.2 * Vin`
  - Mix：中间区间
- 含迟滞边界（0.8 / 0.85 / 1.15 / 1.2）抑制临界点抖动。
- 模式变化置位 `DF.BBModeChange`，环路端检测后清积分，降低切换过冲。

### 6) 保护策略

保护函数在 5ms 任务中执行：

- `OVP()`：输出过压保持计时后拉故障，停 PWM。
- `OCP()`：输出过流保持计时后拉故障，支持有限次数自动恢复。
- `ShortOff()`：短路判据（高电流+低电压）触发故障，并做重试限制。
- `OTP()`：过温触发故障，停 PWM。

故障状态统一由 `DF.ErrFlag` 与 `DF.SMFlag=Err` 管理。

### 7) 上位机通信与数据上报

通信入口：`UF4_TvlcomProcess()`，协议实现见 `APP/Src/uf4_tvlcom.c`。

- 读命令：`READ` 按 TLV type 回包。
- 写命令：`WRITE` 可改输出设定、开关、保护阈值、风扇值。
- 周期报告：`REPORT` 一次打包关键运行量。
- 电流上报：`INPUT_CURRENT` 和 `OUTPUT_CURRENT` 均按非负毫安值编码，避免负值导致上位机显示异常。

## 关键文件

- 控制主流程：`APP/Src/uf4_power_main.c`
- 环路控制：`APP/Src/uf4_power_pid.c`
- 控制头文件与共享结构：`APP/Inc/uf4_power_main.h`
- 通信协议实现：`APP/Src/uf4_tvlcom.c`
- 通信命令说明：`COMMUNICATION_COMMANDS.md`

## 参数存储

- 使用 W25Q64 存储输出设定与保护阈值：`Vout/Iout/OTP/OCP/OVP`。
- 相关函数：`Init_Flash()`、`Read_Flash()`、`Update_Flash()`。
