# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: generate_git_log_attachment_pdf.py
#  @FileType: 生成脚本，用于产出图标、文档或版权材料
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

import subprocess
import textwrap
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "F4CP_Git提交日志_开发过程证明附件.pdf"
TEXT_OUTPUT = ROOT / "docs" / "F4CP_Git提交日志_开发过程证明附件.txt"
LINES_PER_PAGE = 34


def git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def choose_font() -> QFont:
    candidates = ["Microsoft YaHei UI", "Microsoft YaHei", "SimSun", "Arial"]
    families = set(QFontDatabase().families())
    family = next((name for name in candidates if name in families), "Arial")
    font = QFont(family, 8)
    font.setStyleHint(QFont.SansSerif)
    return font


def wrap_line(line: str, width: int = 72) -> list[str]:
    if len(line) <= width:
        return [line]
    return textwrap.wrap(line, width=width, break_long_words=False, replace_whitespace=False) or [line]


def build_lines() -> list[str]:
    top = git(["rev-parse", "--show-toplevel"])
    branch = git(["branch", "--show-current"]) or "(detached)"
    head = git(["rev-parse", "HEAD"])
    total = git(["rev-list", "--count", "HEAD"])
    all_dates = git(["log", "--reverse", "--date=iso-local", "--pretty=format:%ad"]).splitlines()
    first = all_dates[0] if all_dates else ""
    latest = all_dates[-1] if all_dates else ""
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = git(["status", "--short"])
    status_text = "存在未提交或未跟踪文件，未纳入本附件提交历史。" if status else "工作区干净。"

    raw_log = git([
        "log",
        "--date=iso-local",
        "--pretty=format:%h%x09%H%x09%ad%x09%an%x09%s",
    ])

    lines = [
        "F4CP 数字电源上位机控制软件",
        "Git 提交日志及开发过程证明附件",
        "",
        f"生成时间：{generated}",
        f"仓库路径：{top}",
        f"当前分支：{branch}",
        f"当前 HEAD：{head}",
        f"提交总数：{total}",
        f"最早提交时间：{first}",
        f"最新提交时间：{latest}",
        "说明：本附件根据本地 Git 仓库提交历史自动生成，用于辅助证明软件持续开发过程。",
        "说明：提交日志按时间倒序排列，包含短哈希、完整哈希、提交时间、作者和提交说明。",
        "说明：工作区未提交文件不属于 Git 历史提交记录，提交证明以已提交历史为准。",
        f"导出时工作区状态：{status_text}",
        "",
    ]

    lines.extend([
        "提交日志明细：",
        "序号 | 短哈希 | 完整哈希 | 提交时间 | 作者 | 提交说明",
        "-" * 96,
    ])

    for index, row in enumerate(raw_log.splitlines(), start=1):
        parts = row.split("\t", 4)
        if len(parts) != 5:
            lines.append(f"{index:03d} | {row}")
            continue
        short_hash, full_hash, date, author, subject = parts
        lines.append(f"{index:03d} | {short_hash} | {full_hash} | {date} | {author} | {subject}")

    return lines


def paginate(lines: list[str]) -> list[list[str]]:
    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(wrap_line(line))
    pages: list[list[str]] = []
    for offset in range(0, len(wrapped), LINES_PER_PAGE):
        page = wrapped[offset: offset + LINES_PER_PAGE]
        if len(page) < LINES_PER_PAGE:
            page.extend([""] * (LINES_PER_PAGE - len(page)))
        pages.append(page)
    return pages


def write_text(lines: list[str]) -> None:
    TEXT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    TEXT_OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def draw_pdf(pages: list[list[str]]) -> None:
    writer = QPdfWriter(str(OUTPUT))
    writer.setResolution(300)
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageOrientation(QPageLayout.Portrait)
    writer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Millimeter)
    writer.setTitle("F4CP Git 提交日志 开发过程证明附件")
    writer.setCreator("F4CP git log attachment generator")

    painter = QPainter(writer)
    font = choose_font()
    width = writer.width()
    height = writer.height()
    margin_left = 44
    margin_right = 36
    margin_top = 48
    margin_bottom = 38
    line_height = (height - margin_top - margin_bottom - 30) / LINES_PER_PAGE
    usable_width = width - margin_left - margin_right

    for page_no, page_lines in enumerate(pages, start=1):
        if page_no > 1:
            writer.newPage()

        header_font = QFont(font)
        header_font.setPointSize(9)
        header_font.setBold(True)
        painter.setFont(header_font)
        painter.setPen(QColor("#222222"))
        painter.drawText(QRectF(margin_left, 24, usable_width, 20), "F4CP Git 提交日志及开发过程证明附件")

        footer_font = QFont(font)
        footer_font.setPointSize(7)
        painter.setFont(footer_font)
        painter.setPen(QColor("#666666"))
        painter.drawText(QRectF(margin_left, height - 28, usable_width, 16), f"第 {page_no:02d} 页 / 共 {len(pages):02d} 页")

        body_font = QFont(font)
        body_font.setPointSize(7)
        painter.setFont(body_font)

        for line_no, line in enumerate(page_lines, start=1):
            y = margin_top + (line_no - 1) * line_height
            painter.setPen(QColor("#777777"))
            painter.drawText(QRectF(margin_left, y, 32, line_height), f"{line_no:02d}")
            painter.setPen(QColor("#111111"))
            painter.drawText(QRectF(margin_left + 38, y, usable_width - 38, line_height), line)

    painter.end()


def main() -> None:
    app = QApplication([])
    lines = build_lines()
    write_text(lines)
    pages = paginate(lines)
    draw_pdf(pages)
    print(f"lines={len(lines)}")
    print(f"pages={len(pages)}")
    print(f"output={OUTPUT}")
    print(f"text_output={TEXT_OUTPUT}")
    app.quit()


if __name__ == "__main__":
    main()
