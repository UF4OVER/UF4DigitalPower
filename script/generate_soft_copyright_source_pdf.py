# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: generate_soft_copyright_source_pdf.py
#  @FileType: 生成脚本，用于产出图标、文档或版权材料
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

import html
from pathlib import Path

from PyQt5.QtCore import QMarginsF, QRectF
from PyQt5.QtGui import QColor, QFont, QFontDatabase, QPainter, QPageLayout, QPageSize, QPdfWriter, QTextOption
from PyQt5.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "F4CP_软著源程序_前30页后30页.pdf"
LINES_PER_PAGE = 50
FRONT_PAGES = 30
BACK_PAGES = 30


ORDERED_FILES = [
    "start.py",
    "config/config.py",
    "app/session/session_power.py",
    "app/widgets/pages/page_power.py",
    "app/session/session_serial.py",
    "app/widgets/pages/page_device.py",
    "app/session/session_daplink.py",
    "app/widgets/pages/page_daplink.py",
    "app/widgets/pages/page_home.py",
    "app/widgets/pages/page_battery.py",
    "app/widgets/pages/page_settings.py",
    "app/core/data_hub.py",
    "app/core/channel.py",
    "app/core/device_base.py",
    "app/core/ring_buffer.py",
    "app/core/utility.py",
    "app/devices/device_power.py",
    "app/devices/dummy_power_device.py",
    "app/manager/manager_firmware.py",
    "app/manager/manager_update.py",
    "app/manager/manager_stylesheet.py",
    "app/manager/manager_font.py",
    "app/widgets/chart/chart_model.py",
    "app/widgets/chart/realtime_chart_widget.py",
    "app/widgets/chart/fallback_chart_widget.py",
    "app/widgets/chart/simple_plot.py",
    "app/render/opengl/opengl_chart_widget.py",
    "app/render/opengl/opengl_renderer.py",
    "app/protocol/tvlcom.py",
    "app/widgets/icon/icons.py",
    "script/pyocd_launcher.py",
    "script/upx_zip.py",
]


def _read_lines(path: Path) -> list[str]:
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return path.read_text(encoding=encoding).splitlines()
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="replace").splitlines()


def collect_source_lines() -> list[str]:
    lines: list[str] = []
    used: set[Path] = set()

    ordered_paths = [(ROOT / item).resolve() for item in ORDERED_FILES]
    for path in ordered_paths:
        if not path.exists():
            continue
        used.add(path)
        rel = path.relative_to(ROOT).as_posix()
        lines.append(f"# ===== File: {rel} =====")
        lines.extend(_read_lines(path))
        lines.append("")

    for path in sorted((ROOT / "app").rglob("*.py")) + sorted((ROOT / "config").rglob("*.py")) + sorted((ROOT / "script").rglob("*.py")):
        path = path.resolve()
        if path in used or path.name == "uf4_icons_rc.py" or "__pycache__" in path.parts:
            continue
        used.add(path)
        rel = path.relative_to(ROOT).as_posix()
        lines.append(f"# ===== File: {rel} =====")
        lines.extend(_read_lines(path))
        lines.append("")

    return lines


def choose_font() -> QFont:
    candidates = [
        "Consolas",
        "Cascadia Mono",
        "Microsoft YaHei Mono",
        "Microsoft YaHei UI",
        "SimSun",
        "Courier New",
    ]
    families = set(QFontDatabase().families())
    family = next((name for name in candidates if name in families), "Courier New")
    font = QFont(family, 8)
    font.setStyleHint(QFont.TypeWriter)
    font.setFixedPitch(True)
    return font


def draw_page(
    painter: QPainter,
    lines: list[str],
    page_no: int,
    source_start_index: int,
    section: str,
    font: QFont,
    width: int,
    height: int,
) -> None:
    margin_left = 42
    margin_right = 32
    margin_top = 36
    header_height = 28
    footer_height = 22
    usable_width = width - margin_left - margin_right

    painter.setPen(QColor("#333333"))
    header_font = QFont(font)
    header_font.setPointSize(8)
    header_font.setBold(True)
    painter.setFont(header_font)
    painter.drawText(
        QRectF(margin_left, 18, usable_width, 18),
        f"F4CP 数字电源上位机控制软件源程序  {section}  第 {page_no:02d} 页",
    )

    painter.setPen(QColor("#666666"))
    footer_font = QFont(font)
    footer_font.setPointSize(7)
    painter.setFont(footer_font)
    painter.drawText(
        QRectF(margin_left, height - footer_height, usable_width, 14),
        f"每页 50 行源程序 | 全局源码起始行：{source_start_index + 1}",
    )

    code_font = QFont(font)
    code_font.setPointSize(7)
    painter.setFont(code_font)
    option = QTextOption()
    option.setWrapMode(QTextOption.NoWrap)
    line_height = (height - margin_top - header_height - footer_height - 12) / LINES_PER_PAGE
    y = margin_top + header_height
    number_width = 52

    for i, line in enumerate(lines):
        global_line = source_start_index + i + 1
        baseline_y = y + i * line_height
        painter.setPen(QColor("#777777"))
        painter.drawText(QRectF(margin_left, baseline_y, number_width, line_height), f"{global_line:>6}")
        painter.setPen(QColor("#111111"))
        text = html.unescape(line).replace("\t", "    ")
        painter.drawText(
            QRectF(margin_left + number_width + 8, baseline_y, usable_width - number_width - 8, line_height),
            text[:180],
            option,
        )


def generate_pdf(source_lines: list[str]) -> None:
    front_count = FRONT_PAGES * LINES_PER_PAGE
    back_count = BACK_PAGES * LINES_PER_PAGE
    if len(source_lines) < front_count + back_count:
        selected = [("全部源程序", source_lines, 0)]
    else:
        selected = [
            ("前30页", source_lines[:front_count], 0),
            ("后30页", source_lines[-back_count:], len(source_lines) - back_count),
        ]

    writer = QPdfWriter(str(OUTPUT))
    writer.setResolution(300)
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageOrientation(QPageLayout.Portrait)
    writer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Millimeter)
    writer.setTitle("F4CP 软著源程序 前30页后30页")
    writer.setCreator("F4CP source PDF generator")

    painter = QPainter(writer)
    font = choose_font()
    page_no = 1
    width = writer.width()
    height = writer.height()

    first_page = True
    for section, lines, start_index in selected:
        for offset in range(0, len(lines), LINES_PER_PAGE):
            page_lines = lines[offset: offset + LINES_PER_PAGE]
            if len(page_lines) < LINES_PER_PAGE:
                page_lines.extend([""] * (LINES_PER_PAGE - len(page_lines)))
            if not first_page:
                writer.newPage()
            first_page = False
            draw_page(
                painter=painter,
                lines=page_lines,
                page_no=page_no,
                source_start_index=start_index + offset,
                section=section,
                font=font,
                width=width,
                height=height,
            )
            page_no += 1

    painter.end()


def main() -> None:
    app = QApplication([])
    source_lines = collect_source_lines()
    generate_pdf(source_lines)
    print(f"source_lines={len(source_lines)}")
    print(f"output={OUTPUT}")
    app.quit()


if __name__ == "__main__":
    main()
