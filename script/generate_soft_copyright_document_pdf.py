# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: generate_soft_copyright_document_pdf.py
#  @FileType: 生成脚本，用于产出图标、文档或版权材料
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

from pathlib import Path
import textwrap

from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "F4CP_软件设计说明书_软著文档.pdf"
TEXT_OUTPUT = ROOT / "docs" / "F4CP_软件设计说明书_软著文档.txt"
LINES_PER_PAGE = 32
TOTAL_PAGES = 36


MODULES = [
    ("启动与主窗口模块", "负责应用初始化、主窗口创建、导航页装配、标题栏通知和退出处理。"),
    ("配置管理模块", "负责资源路径、配置文件、主题选项、日志目录和版本信息的统一管理。"),
    ("串口通信模块", "负责串口扫描、连接、断开、收发缓冲、状态事件和异常信息投递。"),
    ("蓝牙通信模块", "负责蓝牙目标发现、连接状态维护和面向页面的传输接口适配。"),
    ("电源协议模块", "负责数字电源专用帧构造、CRC 校验、TLV 解析、读写命令和状态回读。"),
    ("电源控制页面", "负责输出电压、限流、电源开关、保护阈值和实时状态的图形化操作。"),
    ("实时曲线模块", "负责电压、电流、功率、效率、温度等通道的缓存、建模和显示。"),
    ("DAPLink 烧录模块", "负责调试器扫描、目标识别、CMSIS Pack 加载、固件下载和进度反馈。"),
    ("固件管理模块", "负责本地固件目录扫描、固件版本识别、文件校验和烧录文件选择。"),
    ("设备适配模块", "负责真实电源设备、模拟电源设备和后续设备类型的数据通道适配。"),
    ("通知与日志模块", "负责统一消息提示、标题栏提示、运行日志记录和错误信息展示。"),
    ("主题与资源模块", "负责图标、字体、QSS 样式、深浅色主题和资源文件加载。"),
]

FEATURES = [
    "支持 Windows 桌面环境下的数字电源设备图形化管理。",
    "支持串口设备自动扫描、端口选择、波特率配置和连接状态显示。",
    "支持原始串口数据的文本格式与十六进制格式收发。",
    "支持 TVLCOM V2 协议的 TLV 数据组包、解析和调试。",
    "支持数字电源输入电压、输入电流、输出电压和输出电流采集。",
    "支持核心温度、板载温度、功率、效率和故障状态的实时监测。",
    "支持输出电压限制、输出电流限制和输出开关状态设置。",
    "支持过压保护、过流保护、过温保护和风扇阈值参数设置。",
    "支持状态轮询、写入暂停、写入确认和回读刷新机制。",
    "支持电压、电流、功率、效率和温度数据的实时曲线展示。",
    "支持曲线时间窗口、自动坐标范围、平移、缩放和主题刷新。",
    "支持 DAPLink 探针扫描、目标芯片选择和连接参数设置。",
    "支持基于 pyOCD 的固件擦除、下载、校验和复位流程。",
    "支持本地 CMSIS Pack 设备支持包识别和目标过滤。",
    "支持应用主题、字体、资源路径、日志路径和配置文件管理。",
    "支持统一通知入口，使页面操作结果以弹窗和标题栏提示展示。",
]

ENV_LINES = [
    "开发语言为 Python，主要使用面向对象方式组织页面、会话和管理模块。",
    "图形界面采用 PySide6 构建，控件风格采用 qfluentwidgets。",
    "固件烧录能力依赖 pyOCD 与本地 CMSIS Pack 设备支持包。",
    "实时曲线显示使用自定义数据模型和 Qt 绘图控件实现。",
    "Windows 打包采用 cx_Freeze，输出桌面可执行程序及配套资源目录。",
    "软件运行时需要 USB 或串口驱动支持，用于连接数字电源设备。",
    "DAPLink 烧录功能需要 CMSIS-DAP 调试器和目标芯片支持包。",
    "测试环境包含 Windows 10/11、Python 3.10+ 和 UF4DigitalPower 硬件。",
]

SUPPLEMENT_LINES = [
    "设计说明：软件采用主窗口加业务页面的结构，方便用户按工作流程切换功能。",
    "设计说明：页面层只负责界面展示和用户交互，具体设备操作交由会话层完成。",
    "设计说明：会话层封装串口、蓝牙和烧录任务，降低页面代码与硬件细节的耦合。",
    "设计说明：协议层统一处理帧格式、数据长度、校验值和命令类型。",
    "设计说明：数据层维护实时采样值和历史曲线数据，供多个控件共享使用。",
    "设计说明：资源层集中保存主题、字体、图标、固件和芯片支持包。",
    "功能说明：软件在连接设备前提供端口扫描能力，减少用户手工输入错误。",
    "功能说明：软件在参数写入后执行状态回读，使界面显示更接近设备实际状态。",
    "功能说明：软件通过日志记录关键操作，便于复现调试步骤和定位异常。",
    "功能说明：软件通过通知组件展示操作结果，提升用户对运行状态的感知。",
    "开发说明：源码按照功能目录划分，便于开发人员维护和扩展。",
    "开发说明：测试用例覆盖配置、协议、页面、图表、通知和烧录等核心逻辑。",
    "运行说明：用户应在设备驱动安装完成后再连接串口或 DAPLink 调试器。",
    "运行说明：烧录功能依赖目标芯片支持包，目标信息应与实际硬件一致。",
    "维护说明：新增协议字段时应同步枚举、元数据、页面显示和自动化测试。",
    "维护说明：新增页面样式时应同步对象名称、样式枚举和 QSS 文件。",
]

FLOW_LINES = [
    "应用启动流程：加载配置 -> 初始化日志 -> 创建 QApplication -> 创建主窗口 -> 加载页面。",
    "串口连接流程：刷新端口 -> 选择端口 -> 创建会话 -> 打开串口 -> 投递状态事件。",
    "电源读流程：组装 READ 帧 -> 写入串口 -> 等待响应 -> 校验 CRC -> 解析 TLV。",
    "电源写流程：校验参数 -> 暂停轮询 -> 组装 WRITE 帧 -> 等待 ACK -> 触发回读。",
    "状态刷新流程：定时器触发 -> 请求状态 -> 更新卡片 -> 写入曲线 -> 显示故障。",
    "DAPLink 流程：扫描探针 -> 选择目标 -> 读取信息 -> 选择固件 -> 执行下载。",
    "烧录进度流程：启动后台任务 -> 接收 pyOCD 输出 -> 换算阶段进度 -> 更新进度条。",
    "配置保存流程：页面修改设置 -> 写入配置管理器 -> 保存文件 -> 刷新界面状态。",
]

TEST_LINES = [
    "配置模块测试验证路径注入、目录创建、配置读取和兼容代理对象。",
    "电源协议测试验证命令枚举和数据类型枚举与下位机头文件保持一致。",
    "电源轮询测试验证启动轮询、写入暂停、写入回读和定时恢复逻辑。",
    "页面测试验证电源输出参数暂存、连接模式切换和页面状态更新。",
    "DAPLink 测试验证目标预加载、进度解析、启动静默参数和事件投递。",
    "通知模块测试验证统一消息入口、不同级别提示和关闭确认信号。",
    "图表模块测试验证数据通道、曲线模型、模拟设备和仪表盘控件。",
    "串口调试测试重点覆盖输入解析、状态事件、错误事件和日志显示。",
]


def choose_font() -> QFont:
    candidates = ["Microsoft YaHei UI", "Microsoft YaHei", "SimSun", "Arial"]
    families = set(QFontDatabase().families())
    family = next((name for name in candidates if name in families), "Arial")
    font = QFont(family, 9)
    font.setStyleHint(QFont.SansSerif)
    return font


def wrap_line(line: str, width: int = 43) -> list[str]:
    if len(line) <= width:
        return [line]
    return textwrap.wrap(line, width=width, break_long_words=False, replace_whitespace=False) or [line]


def make_page(title: str, body: list[str]) -> list[str]:
    lines = [title]
    for item in body:
        lines.extend(wrap_line(item))
    while len(lines) < LINES_PER_PAGE:
        lines.append(SUPPLEMENT_LINES[(len(lines) - 1) % len(SUPPLEMENT_LINES)])
    return lines[:LINES_PER_PAGE]


def build_pages() -> list[list[str]]:
    pages: list[list[str]] = []

    pages.append(make_page("第一章 软件基本信息", [
        "软件名称：F4CP 数字电源上位机控制软件。",
        "软件简称：F4CP。",
        "软件类型：应用软件，属于工业控制和嵌入式设备调试类上位机软件。",
        "软件用途：用于 UF4DigitalPower 数字电源设备的监控、调试、参数配置和固件维护。",
        "运行平台：Windows 10 或 Windows 11 桌面操作系统。",
        "开发语言：Python。",
        "主要技术：PySide6、qfluentwidgets、pyOCD、PyOpenGL、cx_Freeze。",
        "软件界面：采用多页面导航结构，包含引导、串口、设备、烧录和设置页面。",
        "适用对象：数字电源研发人员、测试人员、嵌入式工程师和设备维护人员。",
        "开发目标：降低数字电源调试复杂度，提高状态观测、参数调整和固件维护效率。",
        "本文档性质：本文档为软著登记使用的软件设计说明书。",
        "本文档内容：描述软件组成、设计思想、功能规格、运行流程、测试情况和使用方法。",
    ]))

    pages.append(make_page("第二章 开发背景与目标", [
        "数字电源设备在研发和测试阶段需要频繁读取状态、调整输出参数并观察运行趋势。",
        "传统串口工具只能处理原始字节，不适合长期监控和结构化参数配置。",
        "本软件将设备通信、协议解析、参数编辑、曲线显示和固件烧录整合到统一界面。",
        "软件目标之一是为 UF4DigitalPower 提供稳定、直观的 Windows 上位机。",
        "软件目标之二是将电源协议封装为可维护的客户端对象，便于后续扩展。",
        "软件目标之三是提供可视化曲线，使电源状态变化能够被实时观察和分析。",
        "软件目标之四是集成 DAPLink 烧录能力，减少外部命令行工具切换。",
        "软件目标之五是通过日志、通知和错误提示提高设备调试过程的可追溯性。",
        "软件设计遵循模块化原则，将页面显示、设备会话、协议解析和数据模型分离。",
        "软件通过配置管理模块集中管理路径、主题、日志和版本相关信息。",
    ]))

    pages.append(make_page("第三章 总体结构", [
        "软件采用桌面 GUI 应用结构，由入口程序、页面层、会话层、协议层、数据层和资源层组成。",
        "入口程序 start.py 负责创建应用对象、主窗口、导航项和全局标题栏通知组件。",
        "页面层位于 app/widgets/pages，负责用户界面布局、按钮事件和数据展示。",
        "会话层位于 app/session，负责串口、蓝牙、电源协议和 DAPLink 烧录任务。",
        "协议层位于 app/protocol 以及 session_power.py，负责帧格式、TLV 结构和校验逻辑。",
        "数据层位于 app/core 和 app/widgets/chart，负责数据通道、环形缓存和曲线模型。",
        "管理层位于 app/manager，负责固件、样式、字体、更新和设备相关管理。",
        "资源层位于 Resources，保存图标、字体、主题样式、固件和 CMSIS Pack。",
        "测试目录 tests 保存单元测试与页面行为测试，辅助验证关键逻辑正确性。",
        "整体结构使通信逻辑可以独立测试，界面逻辑可以独立维护，资源文件可以独立替换。",
    ]))

    for idx, (name, desc) in enumerate(MODULES, start=1):
        related = [
            f"模块编号：M{idx:02d}。",
            f"模块名称：{name}。",
            f"模块职责：{desc}",
            "输入内容：来自用户操作、配置文件、串口数据、烧录任务或系统事件。",
            "输出内容：界面状态更新、设备控制命令、日志记录、通知消息或图表数据。",
            "异常处理：模块内部捕获常见错误，并通过日志和统一通知入口向用户反馈。",
            "协作关系：模块通过 Qt 信号、事件、对象方法和配置对象与其他模块协同。",
            "设计原则：保持界面、数据和通信职责分离，避免后台线程直接操作界面控件。",
        ]
        related.extend([f"功能说明：{feature}" for feature in FEATURES[(idx - 1) % len(FEATURES):][:8]])
        pages.append(make_page(f"第四章 模块设计 {idx:02d} - {name}", related))

    pages.append(make_page("第五章 通信协议设计", [
        "数字电源页面使用专用电源协议，不直接复用通用 TVLCOM V2 调试状态机。",
        "协议帧头为 0xAA 0x55，用于标识一帧电源协议数据的开始。",
        "长度字段采用小端格式，表示 CMD、SEQ 和 Payload 的总字节数。",
        "命令字段包含 ACK、READ、WRITE、REPORT 和 NACK 等类型。",
        "序号字段用于区分请求与响应，便于客户端等待指定命令的返回。",
        "载荷采用 TLV 列表结构，格式为 Type、Length、Value。",
        "校验字段采用 Modbus CRC16，小端存储，用于识别传输错误。",
        "读取操作按照数据类型列表组装请求，并在响应中解析实际数值。",
        "写入操作在发送前检查元数据访问权限，避免向只读字段写入。",
        "异常类型包括超时、CRC 错误、协议结构错误、NACK 错误和访问错误。",
        "协议元数据维护了数据类型、值长度、访问权限、单位和显示标签。",
    ]))

    pages.append(make_page("第六章 数据采集与曲线设计", [
        "数据采集由电源客户端按照固定周期读取设备状态。",
        "采集周期默认为 500 毫秒，兼顾实时性与串口通信压力。",
        "采集数据包含输入电压、输入电流、输出电压、输出电流、功率和效率。",
        "温度数据包含核心温度和板载温度，用于观察设备热状态。",
        "DataHub 负责通道注册和数据缓存，默认保存一定数量的历史点。",
        "ChartModel 从 DataHub 中读取指定通道数据，并生成图表快照。",
        "RealtimeChartWidget 负责渲染曲线、坐标信息、图例和鼠标交互。",
        "曲线支持时间窗口设置，使用户能够观察最近一段时间的趋势。",
        "曲线支持自动 Y 轴范围，使不同量纲数据可以动态适配显示区域。",
        "图表模块与设备模块解耦，后续可扩展到其他设备或其他数据通道。",
    ]))

    pages.append(make_page("第七章 DAPLink 烧录设计", [
        "烧录模块用于通过 DAPLink 或 CMSIS-DAP 调试器维护目标设备固件。",
        "软件启动后可预加载本地 CMSIS Pack 中的目标芯片信息。",
        "用户可以扫描探针，选择目标芯片、连接模式、频率和固件文件。",
        "烧录过程通过 pyOCD 执行，支持擦除、编程、校验和复位。",
        "烧录任务运行于后台流程，避免阻塞主界面操作。",
        "模块会解析 pyOCD 输出信息，将擦除和编程阶段换算为进度百分比。",
        "目标信息包括芯片型号、厂商、Flash 起始地址、Flash 大小和 RAM 大小。",
        "固件文件可以来自本地固件目录，也可以由用户通过文件选择器指定。",
        "烧录完成后软件恢复相关页面状态，并通过通知提示结果。",
        "出现探针缺失、目标不匹配、文件不存在或烧录失败时，日志区域显示详细信息。",
    ]))

    pages.append(make_page("第八章 功能规格", [f"功能规格 {i + 1:02d}：{line}" for i, line in enumerate(FEATURES)]))

    for i in range(3):
        body = []
        for j, line in enumerate(FEATURES):
            body.append(f"功能细化 {i + 1}.{j + 1:02d}：{line}")
            body.append("处理方式：界面接收用户操作后调用对应会话或管理对象完成处理。")
        pages.append(make_page(f"第八章 功能规格续 {i + 1}", body))

    pages.append(make_page("第九章 主要业务流程", [f"流程 {i + 1:02d}：{line}" for i, line in enumerate(FLOW_LINES)] + [
        "设备状态异常时，软件将故障码转换为中文故障名称后显示。",
        "用户修改输出参数后，软件会优先完成写入确认，再刷新实际设备状态。",
        "页面关闭时，软件会停止轮询任务并释放串口或后台烧录会话资源。",
        "日志记录流程贯穿启动、连接、读写、烧录、异常和退出阶段。",
    ]))

    pages.append(make_page("第十章 开发与运行环境", ENV_LINES + [
        "开发工具包含 PyCharm、Git、PowerShell 和 uv 包管理工具。",
        "源码采用模块化目录组织，便于按照功能定位和维护。",
        "运行环境包含操作系统、Python 运行库、Qt 运行库和必要设备驱动。",
        "打包产物包含可执行文件、主题资源、字体资源、固件资源和工具资源。",
        "软件支持普通 PC 作为上位机，通过 USB、串口或调试器与硬件连接。",
    ]))

    pages.append(make_page("第十一章 测试情况", [f"测试项 {i + 1:02d}：{line}" for i, line in enumerate(TEST_LINES)] + [
        "测试方法以 unittest 自动化测试和人工连接硬件调试相结合。",
        "测试重点覆盖协议一致性、状态轮询、页面交互、烧录流程和配置管理。",
        "测试结果用于发现通信异常、UI 状态不同步、资源路径错误等问题。",
        "通过测试后，软件能够完成主要设备连接、控制、监测和烧录流程。",
    ]))

    pages.append(make_page("第十二章 用户使用方法", [
        "用户启动软件后进入主窗口，左侧导航栏显示引导、串口、设备、烧录和设置页面。",
        "在串口页面点击刷新串口，选择目标端口和波特率后点击连接。",
        "连接成功后，用户可以输入原始数据并选择格式进行发送。",
        "在 TVLCOM 调试模式下，用户可以添加 TLV 行并生成协议载荷。",
        "在设备页面选择串口后连接电源设备，软件开始周期性读取状态。",
        "用户可查看输入电压、输出电压、电流、功率、效率、温度和故障信息。",
        "用户可填写输出电压和输出电流，点击应用输出完成参数下发。",
        "用户可填写 OVP、OCP、OTP 和风扇阈值，点击应用保护完成配置。",
        "实时曲线区域显示设备状态变化，用户可通过鼠标拖动、滚轮和双击调整视图。",
        "在烧录页面选择 DAPLink 探针、目标芯片和固件文件后启动下载。",
        "烧录过程中观察日志和进度条，完成后根据提示确认结果。",
        "在设置页面可切换主题、字体或其他应用配置。",
    ]))

    pages.append(make_page("第十三章 异常处理与安全措施", [
        "串口未发现时，连接按钮不会执行有效连接，并提示用户刷新或检查驱动。",
        "串口打开失败时，软件记录异常信息并恢复页面连接状态。",
        "协议响应超时时，电源客户端抛出超时异常并通过页面提示。",
        "CRC 校验失败时，软件丢弃错误帧，避免错误数据进入状态显示。",
        "收到 NACK 响应时，软件将其作为设备拒绝操作处理，并提示用户检查参数。",
        "写入参数时，软件检查数据访问权限，禁止对只读字段执行写入。",
        "烧录过程中探针断开或目标识别失败时，后台任务结束并记录日志。",
        "用户关闭软件时，软件尝试停止轮询和后台任务，释放通信资源。",
        "配置读取异常时，软件使用默认值保障基本界面可启动。",
        "通知系统以不同级别区分成功、警告、错误和普通信息。",
    ]))

    pages.append(make_page("第十四章 可维护性与扩展性", [
        "软件以页面、会话、协议、管理器和数据模型分层组织，便于定位问题。",
        "新增页面时，可在主窗口导航中注册页面并补充对应 QSS 样式。",
        "新增电源数据项时，需要同步协议枚举、元数据、状态字段和测试用例。",
        "新增设备类型时，可实现对应设备适配对象并注册所需数据通道。",
        "新增曲线通道时，可在 DataHub 中注册通道并在 ChartModel 中选择显示。",
        "新增固件目录或目标芯片时，可通过固件管理和 Pack 目录机制扩展。",
        "新增配置项时，优先使用现有配置管理器统一保存和读取。",
        "主题资源独立放置在 Resources/Theme/qss，方便独立调整界面样式。",
        "图标和图片资源独立放置在 Resources，减少界面代码与资源文件耦合。",
        "自动化测试覆盖关键逻辑，便于后续修改后进行回归验证。",
    ]))

    pages.append(make_page("第十五章 文档结论", [
        "F4CP 软件围绕数字电源设备的上位机控制需求进行设计和实现。",
        "软件提供设备连接、协议调试、状态监测、参数配置、实时曲线和固件烧录功能。",
        "软件采用 Python 和 PySide6 技术栈，适用于 Windows 桌面环境。",
        "软件通过模块化结构组织源码，便于功能维护和后续扩展。",
        "软件通过专用电源协议实现结构化数据读取和参数写入。",
        "软件通过 DAPLink 烧录模块提升固件维护效率。",
        "软件通过图表模块增强数字电源运行状态的可观察性。",
        "软件通过配置、日志和通知机制提高用户操作反馈和问题定位能力。",
        "本文档连续描述了软件内容、组成、设计、功能规格、开发情况、测试结果和使用方法。",
        "本文档可作为软件著作权登记提交的说明文档材料。",
    ]))

    while len(pages) < TOTAL_PAGES:
        idx = len(pages) + 1
        pages.append(make_page(f"附录 {idx:02d} 软件说明补充", [
            "本页用于补充说明软件在实际调试场景中的操作和维护要点。",
            "用户应先确认硬件供电、串口驱动、DAPLink 连接和固件文件路径正确。",
            "设备参数调整应结合硬件规格和负载条件执行，避免超过硬件允许范围。",
            "协议调试时应核对帧头、长度、命令、序号、TLV 数据和 CRC 校验。",
            "烧录前应确认目标芯片型号、连接模式、下载地址和固件文件匹配。",
            "运行日志可以辅助定位连接失败、协议超时、烧录失败和资源加载异常。",
            "配置文件保存了主题、字体和版本等信息，必要时可恢复默认配置。",
            "软件后续可扩展更多电池管理、网络通信、自动测试和数据导出能力。",
        ]))

    return pages[:TOTAL_PAGES]


def write_text_copy(pages: list[list[str]]) -> None:
    TEXT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with TEXT_OUTPUT.open("w", encoding="utf-8") as f:
        for page_no, lines in enumerate(pages, start=1):
            f.write(f"===== 第 {page_no:02d} 页 =====\n")
            for line in lines:
                f.write(line + "\n")
            f.write("\n")


def draw_pdf(pages: list[list[str]]) -> None:
    writer = QPdfWriter(str(OUTPUT))
    writer.setResolution(300)
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageOrientation(QPageLayout.Portrait)
    writer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Millimeter)
    writer.setTitle("F4CP 软件设计说明书")
    writer.setCreator("F4CP document PDF generator")

    painter = QPainter(writer)
    font = choose_font()
    width = writer.width()
    height = writer.height()
    margin_left = 54
    margin_right = 44
    margin_top = 48
    margin_bottom = 40
    line_height = (height - margin_top - margin_bottom - 34) / LINES_PER_PAGE
    usable_width = width - margin_left - margin_right

    for page_no, lines in enumerate(pages, start=1):
        if page_no > 1:
            writer.newPage()

        painter.setPen(QColor("#333333"))
        header_font = QFont(font)
        header_font.setPointSize(9)
        header_font.setBold(True)
        painter.setFont(header_font)
        painter.drawText(QRectF(margin_left, 24, usable_width, 22), "F4CP 数字电源上位机控制软件 - 软件设计说明书")

        painter.setPen(QColor("#666666"))
        painter.drawText(QRectF(margin_left, height - 30, usable_width, 18), f"第 {page_no:02d} 页 / 共 {len(pages):02d} 页，每页正文不少于 30 行")

        body_font = QFont(font)
        body_font.setPointSize(9)
        painter.setFont(body_font)
        for line_no, line in enumerate(lines, start=1):
            y = margin_top + (line_no - 1) * line_height
            if line_no == 1:
                title_font = QFont(font)
                title_font.setPointSize(10)
                title_font.setBold(True)
                painter.setFont(title_font)
                painter.setPen(QColor("#111111"))
            else:
                painter.setFont(body_font)
                painter.setPen(QColor("#111111"))
            painter.drawText(QRectF(margin_left, y, 42, line_height), f"{line_no:02d}")
            painter.drawText(QRectF(margin_left + 46, y, usable_width - 46, line_height), line)

    painter.end()


def main() -> None:
    app = QApplication([])
    pages = build_pages()
    write_text_copy(pages)
    draw_pdf(pages)
    print(f"pages={len(pages)}")
    print(f"lines_per_page={LINES_PER_PAGE}")
    print(f"output={OUTPUT}")
    print(f"text_output={TEXT_OUTPUT}")
    app.quit()


if __name__ == "__main__":
    main()
