# F4CP 数字电源上位机

F4CP 是 UF4 数字电源项目的桌面上位机，用来连接、控制、监控和升级 `UF4DigitalPower` 四开关 Buck-Boost 数字电源。它把串口通信、实时曲线、参数配置、保护阈值、固件升级和 DAPLink 烧录整合到一个图形界面里，让这块电源板可以像一台可调实验电源一样使用和调试。

QQ 交流群：871340927

立创开源广场：[https://oshwhub.com/uf4over/shu-zi-dian-yuan](https://oshwhub.com/uf4over/shu-zi-dian-yuan)

[QA和一些说明](docs/description.md)

## 项目组成

F4CP 数字电源项目分为两个部分：

1. [上位机软件 F4CP](https://github.com/UF4OVER/UF4DigitalPower)
2. [下位机固件 UF4DigitalPower](https://github.com/UF4OVER/UF4DigitalPower_Firmware)

下位机固件、硬件结构、控制环路、Buck/Mix/Boost 模式、保护逻辑和 C 代码说明请移步[下位机固件 UF4DigitalPower](https://github.com/UF4OVER/UF4DigitalPower_Firmware)

## 实物简介

这套项目面向一块基于 `STM32G474CBT6` 的四开关同步整流 Buck-Boost 数字电源控制板：

- 输入范围：`5V - 40V`
- 输出范围：`0.5V - 40V`
- 电流能力：目标 `0 - 10A`
- 功率拓扑：四开关同步整流 Buck-Boost
- 通信方式：USB CDC / UART，协议为 `UF4COM V3`
- 板载调试：STM32F103 DAPLink，可配合上位机完成固件烧录

实物图：

![F4CP power board front](https://img.hepi.ng/v2/NCb81Dz.jpeg)
![F4CP power board side](https://img.hepi.ng/v2/VqxCobD.jpeg)
![F4CP power board test](https://img.hepi.ng/v2/3x1zBgu.jpeg)
![F4CP power board load test](https://img.hepi.ng/v2/NemKAHw.jpeg)

## 上位机界面

F4CP 提供数字电源控制、实时状态、波形显示和固件管理界面。

![F4CP main UI](https://img.hepi.ng/v2/Lh206dl.png)
![F4CP power UI](https://img.hepi.ng/v2/mSwzYPx.png)

## 主要功能

- 连接 USB CDC / 串口设备
- 设置输出电压、电流限制、OVP、OCP、OTP 等参数
- 开启和关闭输出
- 实时读取 `VIN / IIN / VOUT / IOUT`、温度、风扇、模式和故障状态
- 显示实时曲线和运行状态
- 通过 `UF4COM V3` 执行 `READ / WRITE / REPORT / STREAM`
- 管理固件版本、下载推荐版本和测试版本
- 调用 DAPLink / pyOCD 执行固件烧录和复位
- 保留通用协议调试入口，方便开发和排查通信问题

## 软件结构

```text
F4CP/
├─ app/
│  ├─ controllers/     页面控制器
│  ├─ core/            数据中心、常量和基础对象
│  ├─ protocol/        UF4COM 协议编解码
│  ├─ session/         串口、电源设备、DAPLink 会话
│  ├─ widgets/         PyQt 页面和控件
│  └─ window/          主窗口和导航
├─ config/
├─ Resources/
├─ script/
├─ tests/
├─ start.py
└─ pyproject.toml
```

## 技术栈

- Python 3.11
- PyQt5
- qfluentwidgets
- pyqtgraph
- pyOCD
- uv

## 快速启动

```powershell
git clone https://github.com/UF4OVER/UF4DigitalPower
git submodule update --init --recursive
uv sync
uv run python start.py
```

## 相关链接

- 通信协议：`UF4COM V3`
- 下位机固件：`UF4DigitalPower`
- DAPLink 固件：`DAPLink_STM32F103XB`

## 参考资料

- [UF4COM V3](https://github.com/UF4OVER/UF4COM)
- [DAPLink](https://github.com/UF4OVER/DAPLINK_STM32F103XB)
- [Synchronous Rectification Buck-Boost Digital Power Supply Based on STM32](https://github.com/zeruns/Synchronous-Rectification-Buck-Boost-Digital-Power-Supply-Based-on-STM32)
- [TI Multimode control for a four-switch buck-boost converter](https://www.ti.com/lit/an/slyt765/slyt765.pdf)
- [ST Buck-boost converter using the STM32F334 Discovery kit](https://www.st.com/resource/en/application_note/an4449-buckboost-converter-using-the-stm32f334-discovery-kit-stmicroelectronics.pdf)

> 注意：数字电源涉及高电压、大电流和储能器件。由于焊接水平和实际硬件差异，作者不对使用本项目造成的任何直接或间接损失负责。测试和使用前请做好限流、保险、散热、绝缘和应急断电措施。
