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

- 当前实现已重构为**单向 CV/CC Buck-Boost 控制器**：
  - 只允许正向输出电流，输入/输出电流反馈统一按单向处理；
  - 主控制环为**电压 PI + 模式前馈**，直接输出占空比目标；
  - 恒流控制通过**下拉有效电压参考 `limited_vref`** 实现，不再直接对占空比做硬切换；
  - 占空比输出带**上升/下降斜率限制**，用于抑制轻载与切模时的啸叫。
- 运行模式输入：`DF.BBFlag`（Buck / Boost / Mix），分别采用不同前馈与占空比映射。
- 保护边界：占空比最终受 `MIN/MAX` 与软启动阶段 `BUCKMaxDuty/BoostMaxDuty` 双重限制。

#### 4.1 `BuckBoostVILoopCtlPID()` 占空比映射（BUCK / BOOST / MIX）

本节只描述当前代码中的**实际映射过程**。

1. 公共计算（进入模式分支之前）

- 采样量先经过快速一阶滤波，得到 `vin / vout / iin / iout`
- `soft_vref` 以斜坡方式逼近 `SET_Value.Vout`
- 当 `iout > SET_Value.Iout` 时，CC 管理器缓慢下拉 `limited_vref`；电流回落后再平滑释放
- 电压环输出：`duty = duty_ff + KP * (limited_vref - vout) + integral`
- 轻载过压与输入掉压时会自动回退积分和占空比
- 最终占空比还会经过**slew-rate limiter**，避免磁性器件被低频包络激励
- 输入欠压时直接回最小占空比并清空控制器内部状态

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

- 模式切换时（`DF.BBModeChange`）会衰减积分项并重贴前馈，避免 Buck/Boost/Mix 切换瞬间过冲。
- 控制核心统一在一个快速环里运行，PWM 寄存器每次中断都会刷新。
- 软启动阶段除了状态机抬升 `BUCKMaxDuty/BoostMaxDuty` 外，环路层还有 `soft_vref + duty_slew` 双重约束，降低启动鸣叫与冲击。

### 5) BUCK/BOOST/MIX 模式切换

模式判断函数：`BBMode()`。

- 仍根据 `Vout_ref` 与 `Vin` 比值切换 Buck / Boost / Mix。
- 在原有迟滞基础上新增**连续多次判定确认**，避免临界点来回跳模引起啸叫。
- 模式变化置位 `DF.BBModeChange`，环路端检测后衰减积分，降低切换过冲。

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
- 上电初始化会优先保留已读取且合法的 Flash 参数，仅在越界时回退默认值。
