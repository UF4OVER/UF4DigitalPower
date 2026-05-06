设计一个基于 STM32 的数字电源控制系统（C语言，HAL库），用于同步 Buck/Boost 功率拓扑，要求高实时性与模块化结构。

系统参数：

PWM频率：200kHz
输出范围：0.5–33V，0–10A
控制结构：电压环 + 电流环（双闭环 PID）

采样与量化：

电压采样（输入/输出相同方式）：
电压经 1/10 分压进入 ADC
实际 0–33V → ADC 0–3.3V
需要软件还原真实电压值
电流采样：
分流电阻：8mΩ
运放增益：20
中点偏置：1.65V
电流范围：±10A → ADC范围约 1.65V ±1.6V（≈0.05V–3.25V）
需进行零点校准与双向电流换算

控制逻辑：

外环（电压环）：
输入：Vref 与 Vout
输出：Iref
内环（电流环）：
输入：Iref 与 Iout
输出：PWM占空比
控制周期：
使用定时器中断（200kHz同步或其整数分频）执行控制算法

PWM与拓扑映射：

使用定时器A输出4路PWM控制同步开关：
A1 → L1（低边1）
A2 → H1（高边1）
D1 → L2（低边2）
D2 → H2（高边2）
支持互补输出与死区控制（Dead Time）

软件设计要求：

ADC + DMA 连续采样（电压、电流）
提供滤波（如一阶低通或滑动平均）
PID控制器支持： 限幅 Anti-windup

保护机制：

过压（>33V）
过流（>10A）
欠压
故障时关闭PWM

使用spi对flash进行数据存储，保存PID参数和系统状态，以便在重启后恢复。
使用TVLCOM_V2_FULL进行串口通信，提供实时数据监控和参数调整接口。上位机使用python，python端定义了与TVLCOM协议对应的常量和数据结构，确保通信的一致性和可靠性。
## TVLCOM 常量（与 Python 一一对应）

### 1) 命令字

```python
class TVL_Command(IntEnum):
    ACK = 0x00      # 设备应答
    READ = 0x01     # 读取
    WRITE = 0x02    # 写入
    NACK = 0xFF     # 错误应答
```

### 2) TLV 类型与数据ID（本项目约定：Type 直接使用 DataType 值）

```python
class TVL_DataType(IntEnum):
    INPUT_VOLTAGE = 10          # mV,  只读
    INPUT_CURRENT = 11          # mA,  只读
    OUTPUT_VOLTAGE = 12         # mV,  只读
    OUTPUT_CURRENT = 13         # mA,  只读
    CORE_TEMPERATURE = 14       # mC,  只读
    BOARD_TEMPERATURE = 15      # mC,  只读

    SET_VOLTAGE_LIMIT = 17      # mV,  读写
    SET_CURRENT_LIMIT = 18      # mA,  读写

    CC_CV_MODE = 20             # 0:CC,1:CV, 只读
    POWER_STATE = 21            # 0:OFF,1:ON, 读写
    FAULT_STATE = 22            # bitmask, 只读

    STATE_MACHINE_FLAG_BITS = 23  # INIT/WAIT/RISE/RUN/ERR, 只读
    STATE_MACHINE_STATE = 24      # NA/BUCK/BOOST/MIX, 只读

    INPUT_VOLTAGE_RAW = 25      # uint32, 只读
    INPUT_CURRENT_RAW = 26      # uint32, 只读
    OUTPUT_VOLTAGE_RAW = 27     # uint32, 只读
    OUTPUT_CURRENT_RAW = 28     # uint32, 只读

    OTP_VALUE = 29              # mC, 只读
    OTP_SET_VALUE = 30          # mC, 读写
    OVP_VALUE = 31              # mV, 只读
    OVP_SET_VALUE = 32          # mV, 读写
    OCP_VALUE = 33              # mA, 只读
    OCP_SET_VALUE = 34          # mA, 读写

    FAN_SPEED = 38              # RPM,只读
    FAN_SET_VALUE = 39          # RPM,读写
```

### 3) 故障码与状态机枚举

```python
class TVL_FaultCode(IntEnum):
    NO_ERROR = 0x0000
    INPUT_UNDER_VOLTAGE = 0x0001
    INPUT_OVER_VOLTAGE = 0x0002
    OUTPUT_UNDER_VOLTAGE = 0x0004
    OUTPUT_OVER_VOLTAGE = 0x0008
    OUTPUT_OVER_CURRENT = 0x0010
    OUTPUT_SHORT_CIRCUIT = 0x0020
    OVER_TEMPERATURE_PROTECTION = 0x0040

class TVL_StateMachineFlagBits(IntEnum):
    INIT = 0b0001
    WAIT = 0b0010
    RISE = 0b0100
    RUN = 0b1000
    ERR = 0b1111

class TVL_StateMachineFlag(IntEnum):
    NA = 0
    BUCK = 1
    BOOST = 2
    MIX = 3
```

你的项目建议这样分：

HRTIM A：输入边 MOS PWM
HRTIM D：输出端 MOS PWM
ADC：由 HRTIM 同步触发采样
ADC 中断：做采样换算、短路/过流/电压环/电流环、更新 PWM
HRTIM Fault / 比较器中断：最快关断 PWM
while(1)：状态机、通信、按键、参数更新、故障复位

你这个参数里有几个关键换算：

电压采样：
V_real = V_adc * 13.3

ADC 0~3.3V 对应实际：
0~43.89V
所以 44V 已经非常接近 ADC 满量程，硬件上余量很小

0.5V 短路阈值：
ADC 电压 = 0.5 / 13.3 = 0.03759V
12bit ADC count ≈ 47

电流采样：
INA240 输出 = 1.65V + I * 0.008Ω * 20
INA240 输出 = 1.65V + I * 0.16

    I = (V_adc - 1.65) / 0.16
    I = (V_adc - 1.65) * 6.25

可测电流范围约：
-10.31A ~ +10.31A
推荐执行结构
HRTIM 200kHz 周期开始
↓
HRTIM 触发 ADC 采样
↓
ADC 转换完成中断
↓
读取 Vin / Vout / Iin / Iout / Vbus
↓
换算真实电压电流
↓
快速保护判断
↓
状态机判断：IDLE / SOFT_START / RUN / FAULT
↓
根据输入输出关系判断 Buck / Boost / BuckBoost
↓
计算输入边 HRTIMA 占空比
↓
计算输出边 HRTIMD 占空比
↓
写入 HRTIM Compare 寄存器
数字电源伪代码
// file: g474_digital_power_pseudocode.c

#include <stdbool.h>
#include <stdint.h>

#define ADC_REF_VOLTAGE                 3.3f
#define ADC_MAX_COUNT                   4095.0f

#define PWM_FREQUENCY_HZ                183300.0f
#define PWM_PERIOD_US                   5.455f

#define VOLTAGE_SCALE                   13.3f

#define CURRENT_SENSE_RESISTOR_OHM      0.008f
#define CURRENT_AMP_GAIN                20.0f
#define CURRENT_ZERO_VOLTAGE            1.65f
#define CURRENT_SCALE                   (CURRENT_SENSE_RESISTOR_OHM * CURRENT_AMP_GAIN)

#define INPUT_VOLTAGE_MIN               0.0f
#define INPUT_VOLTAGE_MAX               44.0f

#define OUTPUT_VOLTAGE_MIN              0.5f
#define OUTPUT_VOLTAGE_MAX              44.0f
#define OUTPUT_SHORT_VOLTAGE            0.5f

#define ADC_OUTPUT_SHORT_COUNT          47U

#define DUTY_MIN                        0.02f
#define DUTY_MAX                        0.95f
#define DUTY_BOOTSTRAP_MIN              0.05f

#define SOFT_START_STEP                 0.002f

#define VOLTAGE_KP                      0.03f
#define VOLTAGE_KI                      0.0005f

#define CURRENT_KP                      0.02f
#define CURRENT_KI                      0.0003f

#define OUTPUT_OVP_MARGIN               1.0f
#define INPUT_UVP_LIMIT                 3.0f
#define CURRENT_LIMIT_POSITIVE          8.0f
#define CURRENT_LIMIT_NEGATIVE          -8.0f

typedef enum {
POWER_IDLE,
POWER_SOFT_START,
POWER_RUN,
POWER_FAULT
} PowerState;

typedef enum {
POWER_MODE_BUCK,
POWER_MODE_BOOST,
POWER_MODE_BUCK_BOOST
} PowerMode;

typedef struct {
uint16_t vin_count;
uint16_t vout_count;
uint16_t iin_count;
uint16_t iout_count;
} AdcRaw;

typedef struct {
float vin;
float vout;
float iin;
float iout;
} PowerSample;

typedef struct {
float vout_target;
float vout_ref;

    float voltage_integral;
    float current_integral;

    float duty_input_pwm_a;
    float duty_output_pwm_d;
} PowerControl;

typedef struct {
bool input_under_voltage;
bool output_over_voltage;
bool output_short;
bool positive_over_current;
bool negative_over_current;
bool hardware_fault;
} FaultFlags;

static volatile PowerState power_state = POWER_IDLE;
static volatile AdcRaw adc_raw;
static volatile PowerSample sample;
static volatile PowerControl control;
static volatile FaultFlags fault_flags;

static float adc_count_to_voltage(uint16_t count)
{
return ((float)count * ADC_REF_VOLTAGE) / ADC_MAX_COUNT;
}

static float voltage_adc_to_real(uint16_t count)
{
return adc_count_to_voltage(count) * VOLTAGE_SCALE;
}

static float current_adc_to_real(uint16_t count)
{
float adc_voltage = adc_count_to_voltage(count);

    return (adc_voltage - CURRENT_ZERO_VOLTAGE) / CURRENT_SCALE;
}

static float clamp(float value, float min_value, float max_value)
{
if (value < min_value) {
return min_value;
}

    if (value > max_value) {
        return max_value;
    }

    return value;
}

static bool has_fault(void)
{
return fault_flags.input_under_voltage ||
fault_flags.output_over_voltage ||
fault_flags.output_short ||
fault_flags.positive_over_current ||
fault_flags.negative_over_current ||
fault_flags.hardware_fault;
}

static void clear_faults(void)
{
fault_flags.input_under_voltage = false;
fault_flags.output_over_voltage = false;
fault_flags.output_short = false;
fault_flags.positive_over_current = false;
fault_flags.negative_over_current = false;
fault_flags.hardware_fault = false;
}

static void read_adc_samples(void)
{
adc_raw.vin_count = adc_read_vin_channel();
adc_raw.vout_count = adc_read_vout_channel();
adc_raw.iin_count = adc_read_iin_channel();
adc_raw.iout_count = adc_read_iout_channel();

    sample.vin = voltage_adc_to_real(adc_raw.vin_count);
    sample.vout = voltage_adc_to_real(adc_raw.vout_count);
    sample.iin = current_adc_to_real(adc_raw.iin_count);
    sample.iout = current_adc_to_real(adc_raw.iout_count);
}

static void fast_fault_check(void)
{
if (sample.vin < INPUT_UVP_LIMIT) {
fault_flags.input_under_voltage = true;
}

    if (sample.vout > control.vout_target + OUTPUT_OVP_MARGIN) {
        fault_flags.output_over_voltage = true;
    }

    if (sample.vout < OUTPUT_SHORT_VOLTAGE && power_state == POWER_RUN) {
        fault_flags.output_short = true;
    }

    if (sample.iout > CURRENT_LIMIT_POSITIVE) {
        fault_flags.positive_over_current = true;
    }

    if (sample.iout < CURRENT_LIMIT_NEGATIVE) {
        fault_flags.negative_over_current = true;
    }
}

static PowerMode select_power_mode(void)
{
if (control.vout_ref < sample.vin - 1.0f) {
return POWER_MODE_BUCK;
}

    if (control.vout_ref > sample.vin + 1.0f) {
        return POWER_MODE_BOOST;
    }

    return POWER_MODE_BUCK_BOOST;
}

static void soft_start_update(void)
{
if (control.vout_ref < control.vout_target) {
control.vout_ref += SOFT_START_STEP;

        if (control.vout_ref > control.vout_target) {
            control.vout_ref = control.vout_target;
        }
    }
}

static float voltage_loop_calculate_current_ref(void)
{
float error;
float current_ref;

    error = control.vout_ref - sample.vout;

    control.voltage_integral += VOLTAGE_KI * error;
    control.voltage_integral = clamp(
        control.voltage_integral,
        CURRENT_LIMIT_NEGATIVE,
        CURRENT_LIMIT_POSITIVE
    );

    current_ref = VOLTAGE_KP * error + control.voltage_integral;

    return clamp(current_ref, CURRENT_LIMIT_NEGATIVE, CURRENT_LIMIT_POSITIVE);
}

static float current_loop_calculate_duty_delta(float current_ref)
{
float error;
float duty_delta;

    error = current_ref - sample.iout;

    control.current_integral += CURRENT_KI * error;
    control.current_integral = clamp(control.current_integral, -0.5f, 0.5f);

    duty_delta = CURRENT_KP * error + control.current_integral;

    return clamp(duty_delta, -0.5f, 0.5f);
}

static void calculate_pwm_duty(void)
{
PowerMode mode;
float current_ref;
float duty_delta;
float buck_base_duty;
float boost_base_duty;

    mode = select_power_mode();
    current_ref = voltage_loop_calculate_current_ref();
    duty_delta = current_loop_calculate_duty_delta(current_ref);

    if (sample.vin <= 0.1f) {
        control.duty_input_pwm_a = 0.0f;
        control.duty_output_pwm_d = 0.0f;
        return;
    }

    buck_base_duty = control.vout_ref / sample.vin;
    boost_base_duty = 1.0f - (sample.vin / control.vout_ref);

    buck_base_duty = clamp(buck_base_duty, DUTY_MIN, DUTY_MAX);
    boost_base_duty = clamp(boost_base_duty, DUTY_MIN, DUTY_MAX);

    switch (mode) {
        case POWER_MODE_BUCK:
            control.duty_input_pwm_a = clamp(buck_base_duty + duty_delta, DUTY_MIN, DUTY_MAX);
            control.duty_output_pwm_d = DUTY_BOOTSTRAP_MIN;
            break;

        case POWER_MODE_BOOST:
            control.duty_input_pwm_a = DUTY_BOOTSTRAP_MIN;
            control.duty_output_pwm_d = clamp(boost_base_duty + duty_delta, DUTY_MIN, DUTY_MAX);
            break;

        case POWER_MODE_BUCK_BOOST:
            control.duty_input_pwm_a = clamp(0.5f + duty_delta, DUTY_MIN, DUTY_MAX);
            control.duty_output_pwm_d = clamp(0.5f - duty_delta, DUTY_MIN, DUTY_MAX);
            break;

        default:
            control.duty_input_pwm_a = 0.0f;
            control.duty_output_pwm_d = 0.0f;
            break;
    }
}

static void apply_pwm_outputs(void)
{
hrtim_a_set_duty(control.duty_input_pwm_a);
hrtim_d_set_duty(control.duty_output_pwm_d);
}

static void shutdown_pwm_outputs(void)
{
control.duty_input_pwm_a = 0.0f;
control.duty_output_pwm_d = 0.0f;

    hrtim_a_set_duty(0.0f);
    hrtim_d_set_duty(0.0f);

    hrtim_a_disable_output();
    hrtim_d_disable_output();
}

void system_init(void)
{
disable_interrupts();

    clock_init();
    gpio_init();
    adc_init();
    comparator_init();

    hrtim_init_183k3();
    hrtim_a_pwm_init();
    hrtim_d_pwm_init();

    hrtim_adc_trigger_init();
    hrtim_fault_input_init();

    control.vout_target = 12.0f;
    control.vout_ref = 0.0f;
    control.voltage_integral = 0.0f;
    control.current_integral = 0.0f;
    control.duty_input_pwm_a = 0.0f;
    control.duty_output_pwm_d = 0.0f;

    clear_faults();
    shutdown_pwm_outputs();

    enable_interrupts();
}

int main(void)
{
system_init();

    while (true) {
        switch (power_state) {
            case POWER_IDLE:
                shutdown_pwm_outputs();

                if (start_command_received() && !has_fault()) {
                    control.vout_ref = 0.0f;
                    control.voltage_integral = 0.0f;
                    control.current_integral = 0.0f;

                    hrtim_a_enable_output();
                    hrtim_d_enable_output();

                    power_state = POWER_SOFT_START;
                }
                break;

            case POWER_SOFT_START:
                if (has_fault()) {
                    power_state = POWER_FAULT;
                }

                if (control.vout_ref >= control.vout_target) {
                    power_state = POWER_RUN;
                }
                break;

            case POWER_RUN:
                if (has_fault()) {
                    power_state = POWER_FAULT;
                }

                if (stop_command_received()) {
                    power_state = POWER_IDLE;
                }
                break;

            case POWER_FAULT:
                shutdown_pwm_outputs();
                fault_report_task();

                if (fault_reset_command_received()) {
                    clear_faults();
                    power_state = POWER_IDLE;
                }
                break;

            default:
                power_state = POWER_FAULT;
                break;
        }

        communication_task();
        key_scan_task();
        display_task();
        parameter_update_task();
    }
}

void hrtim_master_period_interrupt_handler(void)
{
hrtim_clear_master_period_flag();

    adc_trigger_injected_conversion();
}

void adc_injected_conversion_complete_interrupt_handler(void)
{
adc_clear_injected_conversion_flag();

    read_adc_samples();
    fast_fault_check();

    if (has_fault()) {
        power_state = POWER_FAULT;
        shutdown_pwm_outputs();
        return;
    }

    if (power_state == POWER_SOFT_START) {
        soft_start_update();
        calculate_pwm_duty();
        apply_pwm_outputs();
        return;
    }

    if (power_state == POWER_RUN) {
        calculate_pwm_duty();
        apply_pwm_outputs();
        return;
    }

    shutdown_pwm_outputs();
}

void hrtim_fault_interrupt_handler(void)
{
hrtim_clear_fault_flag();

    fault_flags.hardware_fault = true;
    power_state = POWER_FAULT;

    shutdown_pwm_outputs();
}
你这个硬件特别要注意的点

第一，44V 输入/输出对应 ADC 已经接近 3.3V 满量程：

44V / 13.3 = 3.308V

这会超过 3.3V 一点点。实际硬件建议把分压倍率提高一点，比如 14 倍、15 倍，留 OVP 和采样误差余量。

第二，0.5V 短路阈值 ADC count 只有约 47，很低：

0.5V / 13.3 = 37.6mV
12bit ADC ≈ 47 count

所以 0.5V 以下短路判断建议加条件：

只有在 RUN 状态，并且 PWM 已经启动一段时间后，才判断输出短路

否则软启动初期输出本来就低于 0.5V，会误报短路。

第三，INA240 双向电流检测建议这样判断方向：

ADC 电压 > 1.65V：正向电流
ADC 电压 < 1.65V：反向电流

I = (ADC电压 - 1.65) / 0.16

第四，183.3kHz 控制频率很高，不要在 ADC 中断里做通信、打印、Flash、复杂浮点日志。ADC 中断只做：

采样
保护
PI/限流
PWM 更新

其它都放 while(1)。

最终建议

你的代码结构应该是：

main.c
main()
system_init()
while(1) 慢任务

power_control.c
状态机
软启动
电压环
电流环
模式判断

power_adc.c
ADC 原始值读取
电压/电流换算

power_fault.c
短路
过压
过流
HRTIM Fault 关断

power_pwm.c
HRTIMA 输入边 PWM
HRTIMD 输出端 PWM
占空比更新

核心一句：

HRTIM 负责固定节拍，ADC 中断负责闭环控制，Fault 中断负责保命，while(1) 只做慢任务。