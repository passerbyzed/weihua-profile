"""售后质量问题统计报表：按提问中的维度统计出现次数，导出 Excel / PDF / Word（含图表）。"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

DATA_DIR = Path(__file__).parent / "data"
ISSUES: list[dict] = json.loads((DATA_DIR / "issues.json").read_text(encoding="utf-8"))

COMPONENT_ALIASES = {
    "涂装": "涂装层",
    "油漆": "涂装层",
    "轴承座": "卷筒轴承座",
    "电机": "起升电机",
    "减速机": "起升减速机",
    "电控": "电控柜",
    "钢丝绳": "钢丝绳",
    "限位": "限位开关",
    "遥控": "遥控器",
    "小车": "小车运行机构",
    "主梁": "主梁",
    "缓冲": "缓冲器",
    "制动": "制动器",
    "司机室": "司机室",
    "车轮": "车轮",
    "回转": "回转机构",
    "吊钩": "吊钩组",
    "铭牌": "铭牌",
}

STOPWORDS = {
    "问题",
    "质量",
    "为什么",
    "什么",
    "哪些",
    "怎么",
    "如何",
    "多少",
    "最近",
    "近",
    "本月",
    "今年",
    "请",
    "给我",
    "一份",
    "报表",
    "统计",
    "出现",
    "次数",
    "维度",
    "以及",
    "还有",
    "这个",
    "那个",
    "客户",
    "公司",
    "情况",
    "分析",
    "集中",
    "属于",
    "同一",
    "根因",
    "摘要",
    "需要",
    "处理",
    "部件",
    "原因",
}

PHENOMENON_ALIASES = [
    "漏油",
    "异响",
    "过热",
    "打滑",
    "抖动",
    "磨损",
    "松动",
    "裂纹",
    "断裂",
    "烧毁",
    "跳闸",
    "失控",
    "跳槽",
    "色差",
    "起泡",
    "膜厚不足",
    "锈蚀",
    "变形",
]

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size, index=0)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _bar_chart(labels: list[str], values: list[int], title: str, color: str = "#2563EB") -> bytes:
    width, height = 960, 440
    image = PILImage.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = _font(26)
    label_font = _font(15)
    value_font = _font(14)
    small_font = _font(12)

    draw.text((40, 22), title, font=title_font, fill="#0F172A")
    left, right, top, bottom = 78, 36, 84, 86
    plot_w, plot_h = width - left - right, height - top - bottom
    max_value = max(values) if values else 1
    max_value = max(1, max_value)
    if max_value <= 6:
        axis_max = max_value
        ticks = list(range(axis_max + 1))
    else:
        step = max(1, (max_value + 3) // 4)
        axis_max = step * 4
        ticks = [step * index for index in range(5)]

    for tick in ticks:
        y = top + plot_h - plot_h * tick / axis_max
        draw.line((left, y, width - right, y), fill="#E2E8F0", width=1)
        text = str(tick)
        draw.text((left - 10 - _text_width(draw, text, small_font), y - 8), text, font=small_font, fill="#64748B")

    draw.line((left, top, left, top + plot_h), fill="#94A3B8", width=1)
    draw.line((left, top + plot_h, width - right, top + plot_h), fill="#94A3B8", width=1)

    if not labels:
        draw.text((left + 20, top + plot_h // 2), "暂无数据", font=label_font, fill="#94A3B8")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    slot = plot_w / len(labels)
    bar_w = min(86, slot * 0.56)
    label_step = max(1, (len(labels) + 9) // 10)
    for index, (label, value) in enumerate(zip(labels, values)):
        x_center = left + slot * index + slot / 2
        bar_h = plot_h * value / axis_max
        x1 = x_center - bar_w / 2
        y1 = top + plot_h - bar_h
        draw.rounded_rectangle((x1, y1, x1 + bar_w, top + plot_h), radius=4, fill=color)
        value_text = str(value)
        draw.text(
            (x_center - _text_width(draw, value_text, value_font) / 2, y1 - 23),
            value_text,
            font=value_font,
            fill="#1E293B",
        )
        if index % label_step == 0:
            label_text = label if len(label) <= 10 else label[:9] + "…"
            draw.text(
                (x_center - _text_width(draw, label_text, label_font) / 2, top + plot_h + 14),
                label_text,
                font=label_font,
                fill="#334155",
            )

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _pie_chart(labels: list[str], values: list[int], title: str) -> bytes:
    width, height = 820, 440
    image = PILImage.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = _font(26)
    label_font = _font(15)
    small_font = _font(13)

    draw.text((40, 22), title, font=title_font, fill="#0F172A")

    pairs = [(label, value) for label, value in zip(labels, values) if value > 0]
    if not pairs:
        draw.text((60, 180), "暂无数据", font=label_font, fill="#94A3B8")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    total = sum(value for _, value in pairs)
    palette = ["#2563EB", "#0EA5E9", "#14B8A6", "#F59E0B", "#EF4444", "#8B5CF6", "#64748B"]
    box = (60, 100, 380, 420)
    start = -90
    for index, (label, value) in enumerate(pairs):
        extent = 360 * value / total
        draw.pieslice(box, start=start, end=start + extent, fill=palette[index % len(palette)], outline="white", width=2)
        start += extent

    draw.ellipse((170, 210, 270, 310), fill="white")
    draw.text((192, 245), str(total), font=_font(22), fill="#0F172A")
    draw.text((188, 275), "总数", font=small_font, fill="#64748B")

    legend_x = 420
    legend_y = 130
    for index, (label, value) in enumerate(pairs):
        color = palette[index % len(palette)]
        draw.rounded_rectangle((legend_x, legend_y + index * 34, legend_x + 14, legend_y + 14 + index * 34), radius=3, fill=color)
        percent = value / total * 100
        text = f"{label}  {value}（{percent:.1f}%）"
        draw.text((legend_x + 24, legend_y - 2 + index * 34), text, font=small_font, fill="#334155")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _time_filter(question: str) -> tuple[list[dict], str]:
    latest = max((_parse_date(item.get("date", "")) for item in ISSUES), default=None)
    if not latest:
        return ISSUES, "全部数据"
    start: date | None = None
    label = "全部数据"

    month_match = re.search(r"(?:最近|近)\s*([一二三四五六七八九十\d]+)\s*个月", question)
    if month_match:
        raw = month_match.group(1)
        mapping = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12}
        months = int(raw) if raw.isdigit() else mapping.get(raw, 3)
        start = latest - timedelta(days=months * 30)
        label = f"最近 {months} 个月（{start.isoformat()} 至 {latest.isoformat()}）"
    elif "本月" in question:
        start = latest.replace(day=1)
        label = f"本月（{start.isoformat()} 至 {latest.isoformat()}）"
    elif "今年" in question:
        start = latest.replace(month=1, day=1)
        label = f"今年（{start.isoformat()} 至 {latest.isoformat()}）"

    if not start:
        return ISSUES, label
    rows = [item for item in ISSUES if (_parse_date(item.get("date", "")) or date.min) >= start]
    return rows, label


def _add_dimension(found: list[dict], seen: set[tuple[str, str]], kind: str, name: str, rows: list[dict]) -> None:
    key = (kind, name)
    if key in seen or not rows:
        return
    seen.add(key)
    found.append({"type": kind, "name": name, "rows": rows})


def _detect_dimensions(question: str, rows: list[dict]) -> list[dict]:
    components = sorted({item["component"] for item in rows if item.get("component")})
    causes = sorted({item["cause"] for item in rows if item.get("cause")})
    fault_types = sorted({item["fault_type"] for item in rows if item.get("fault_type")})
    customers = sorted({item["customer"] for item in rows if item.get("customer")})
    machines = sorted({item["machine_id"] for item in rows if item.get("machine_id")})

    candidates: list[tuple[int, str, str, list[dict]]] = []
    for component in components:
        position = question.find(component)
        if position >= 0:
            candidates.append((position, "问题部件", component, [x for x in rows if x.get("component") == component]))

    for alias, component in COMPONENT_ALIASES.items():
        position = question.find(alias)
        if position >= 0 and component in components:
            candidates.append((position, "问题部件", component, [x for x in rows if x.get("component") == component]))

    for phrase in PHENOMENON_ALIASES:
        position = question.find(phrase)
        if position >= 0:
            matched = [
                x
                for x in rows
                if phrase in f"{x.get('phenomenon') or ''}{x.get('description') or ''}"
            ]
            candidates.append((position, "问题现象", phrase, matched))

    for fault_type in fault_types:
        position = question.find(fault_type)
        if position >= 0:
            candidates.append((position, "故障类型", fault_type, [x for x in rows if x.get("fault_type") == fault_type]))

    for cause in causes:
        position = question.find(cause)
        if position >= 0:
            candidates.append((position, "原因归属", cause, [x for x in rows if x.get("cause") == cause]))

    for customer in customers:
        position = question.find(customer)
        if position >= 0:
            candidates.append((position, "使用单位", customer, [x for x in rows if x.get("customer") == customer]))

    for machine in machines:
        position = question.find(machine)
        if position >= 0:
            candidates.append((position, "整机", machine, [x for x in rows if x.get("machine_id") == machine]))

    candidates.sort(key=lambda item: (item[0], -len(item[2])))

    found: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for _, kind, name, matched in candidates:
        _add_dimension(found, seen, kind, name, matched)

    if found:
        return found

    tokens = [token for token in re.split(r"[，。！？、；：\s和与及/,]+", question) if token]
    for token in tokens:
        token = re.sub(r"^(?:最近|近|本月|今年|给我|一份)", "", token).strip()
        if len(token) < 2 or token in STOPWORDS:
            continue
        if any(token in item["name"] or item["name"] in token for item in found):
            continue
        matched = [
            item
            for item in rows
            if token in " ".join(
                str(item.get(field) or "")
                for field in ("component", "phenomenon", "description", "cause", "cause_detail", "customer", "machine_id")
            )
        ]
        _add_dimension(found, seen, "关键词", token, matched)
        if len(found) >= 5:
            break

    if not found:
        _add_dimension(found, seen, "全部", "全部问题", rows)
    return found


def _counts(rows: list[dict], field: str) -> list[dict]:
    counter = Counter(str(item.get(field) or "未填写") for item in rows)
    return [{"label": label, "count": count} for label, count in counter.most_common()]


def _monthly(rows: list[dict]) -> list[dict]:
    labels = sorted({str(item.get("date") or "")[:7] for item in rows if item.get("date")})
    if not labels:
        return []
    latest = max((str(item.get("date") or "")[:7] for item in ISSUES if item.get("date")), default=labels[-1])
    start_year, start_month = (int(part) for part in labels[0].split("-"))
    end_year, end_month = (int(part) for part in latest.split("-"))
    counter = Counter(str(item.get("date") or "")[:7] for item in rows if item.get("date"))
    result: list[dict] = []
    year, month = start_year, start_month
    while (year, month) <= (end_year, end_month):
        label = f"{year:04d}-{month:02d}"
        result.append({"label": label, "count": counter.get(label, 0)})
        month += 1
        if month > 12:
            month = 1
            year += 1
    return result


def build_report(question: str) -> dict[str, Any]:
    rows, scope = _time_filter(question)
    dimensions = _detect_dimensions(question, rows)
    total = len(rows)
    built: list[dict] = []
    for dimension in dimensions:
        dim_rows = dimension["rows"]
        built.append(
            {
                "name": dimension["name"],
                "type": dimension["type"],
                "count": len(dim_rows),
                "share": round(len(dim_rows) / total * 100, 1) if total else 0,
                "by_fault_type": _counts(dim_rows, "fault_type"),
                "by_cause": _counts(dim_rows, "cause"),
                "by_customer": _counts(dim_rows, "customer")[:10],
                "by_machine": _counts(dim_rows, "machine_id"),
                "by_status": _counts(dim_rows, "status"),
                "by_month": _monthly(dim_rows),
            }
        )

    return {
        "title": "售后质量问题统计报表",
        "question": question,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "scope": scope,
        "total": total,
        "dimensions": built,
        "comparison": [
            {"name": item["name"], "type": item["type"], "count": item["count"], "share": item["share"]}
            for item in built
        ],
    }


def _safe_sheet_name(name: str) -> str:
    return re.sub(r"[\\/*?:\[\]]", "_", name)[:31] or "统计"


def render_excel(data: dict[str, Any]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "报表概览"
    ws.sheet_view.showGridLines = False

    title_font = Font(name="微软雅黑", size=15, bold=True, color="FFFFFF")
    head_font = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
    body_font = Font(name="微软雅黑", size=9)
    title_fill = PatternFill("solid", fgColor="1E3A8A")
    head_fill = PatternFill("solid", fgColor="2563EB")
    thin = Side(style="thin", color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws.merge_cells("A1:F1")
    cell = ws["A1"]
    cell.value = data["title"]
    cell.font = title_font
    cell.fill = title_fill
    cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 30

    meta_rows = [
        ("提问内容", data["question"]),
        ("统计范围", data["scope"]),
        ("生成时间", data["generated_at"]),
        ("范围内问题总数", data["total"]),
    ]
    row = 3
    for label, value in meta_rows:
        ws.cell(row=row, column=1, value=label).font = Font(name="微软雅黑", size=9, bold=True)
        ws.cell(row=row, column=2, value=value).font = body_font
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=6)
        row += 1

    row += 1
    ws.cell(row=row, column=1, value="维度统计").font = Font(name="微软雅黑", size=11, bold=True)
    row += 1
    summary_start = row
    for col, header in enumerate(["维度类型", "维度", "问题数", "占比"], start=1):
        cell = ws.cell(row=row, column=col, value=header)
        cell.font = head_font
        cell.fill = head_fill
        cell.border = border
    row += 1
    for item in data["comparison"]:
        values = [item["type"], item["name"], item["count"], f"{item['share']}%"]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=row, column=col, value=value)
            cell.font = body_font
            cell.border = border
        row += 1

    if data["comparison"]:
        chart = BarChart()
        chart.title = "各维度问题数"
        chart.y_axis.title = "问题数"
        chart.height = 8
        chart.width = 14
        chart.legend = None
        data_ref = Reference(ws, min_col=3, min_row=summary_start + 1, max_row=summary_start + len(data["comparison"]))
        cats = Reference(ws, min_col=2, min_row=summary_start + 1, max_row=summary_start + len(data["comparison"]))
        chart.add_data(data_ref, titles_from_data=False)
        chart.set_categories(cats)
        ws.add_chart(chart, "H3")

    for column, width in {"A": 16, "B": 26, "C": 12, "D": 12, "E": 18, "F": 18, "G": 3}.items():
        ws.column_dimensions[column].width = width

    def write_table(sheet, start_row: int, headers: list[str], rows: list[list[Any]], widths: list[int] | None = None) -> int:
        for col, header in enumerate(headers, start=1):
            cell = sheet.cell(row=start_row, column=col, value=header)
            cell.font = head_font
            cell.fill = head_fill
            cell.border = border
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for offset, values in enumerate(rows, start=1):
            for col, value in enumerate(values, start=1):
                cell = sheet.cell(row=start_row + offset, column=col, value=value)
                cell.font = body_font
                cell.border = border
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        if widths:
            for index, width in enumerate(widths, start=1):
                sheet.column_dimensions[get_column_letter(index)].width = width
        return start_row + len(rows) + 2

    for dimension in data["dimensions"]:
        sheet = wb.create_sheet(_safe_sheet_name(dimension["name"]))
        sheet.sheet_view.showGridLines = False
        sheet.merge_cells("A1:F1")
        title = sheet["A1"]
        title.value = f"{dimension['name']} · {dimension['count']} 条（占 {dimension['share']}%）"
        title.font = title_font
        title.fill = title_fill
        title.alignment = Alignment(horizontal="center", vertical="center")
        sheet.row_dimensions[1].height = 28

        row = 3
        cause_start = 0
        cause_rows: list[list[Any]] = []
        for label, key in (("按故障类型", "by_fault_type"), ("按原因归属", "by_cause"), ("按状态", "by_status")):
            sheet.cell(row=row, column=1, value=label).font = Font(name="微软雅黑", size=10, bold=True)
            row += 1
            rows_for_table = [[x["label"], x["count"]] for x in dimension[key]]
            table_start = row
            if key == "by_cause":
                cause_start = table_start
                cause_rows = rows_for_table
            row = write_table(sheet, row, ["分类", "问题数"], rows_for_table, [26, 10])

        sheet.cell(row=row, column=1, value="按月分布").font = Font(name="微软雅黑", size=10, bold=True)
        row += 1
        month_rows = [[x["label"], x["count"]] for x in dimension["by_month"]]
        month_start = row
        row = write_table(sheet, row, ["月份", "问题数"], month_rows, [26, 10])

        sheet.cell(row=row, column=1, value="按使用单位").font = Font(name="微软雅黑", size=10, bold=True)
        row += 1
        row = write_table(sheet, row, ["使用单位", "问题数"], [[x["label"], x["count"]] for x in dimension["by_customer"]], [34, 10])

        if month_rows:
            month_chart = BarChart()
            month_chart.title = f"{dimension['name']} · 月度趋势"
            month_chart.y_axis.title = "问题数"
            month_chart.height = 8
            month_chart.width = 14
            month_chart.legend = None
            month_data = Reference(sheet, min_col=2, min_row=month_start + 1, max_row=month_start + len(month_rows))
            month_cats = Reference(sheet, min_col=1, min_row=month_start + 1, max_row=month_start + len(month_rows))
            month_chart.add_data(month_data, titles_from_data=False)
            month_chart.set_categories(month_cats)
            sheet.add_chart(month_chart, "H3")

        cause_rows = dimension["by_cause"]
        if cause_rows:
            cause_chart = PieChart()
            cause_chart.title = f"{dimension['name']} · 原因归属"
            cause_chart.height = 8
            cause_chart.width = 11
            cause_chart.dataLabels = DataLabelList()
            cause_chart.dataLabels.showPercent = True
            cause_data = Reference(sheet, min_col=2, min_row=cause_start + 1, max_row=cause_start + len(cause_rows))
            cause_cats = Reference(sheet, min_col=1, min_row=cause_start + 1, max_row=cause_start + len(cause_rows))
            cause_chart.add_data(cause_data, titles_from_data=False)
            cause_chart.set_categories(cause_cats)
            sheet.add_chart(cause_chart, "H22")

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _docx_set_cell(cell, text: str) -> None:
    cell.text = str(text)
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.font.name = "微软雅黑"
            run._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
            run.font.size = Pt(8)


def _docx_table(doc: Document, headers: list[str], rows: list[list[Any]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for index, header in enumerate(headers):
        _docx_set_cell(table.rows[0].cells[index], header)
    for values in rows:
        cells = table.add_row().cells
        for index, value in enumerate(values):
            _docx_set_cell(cells[index], value)
    doc.add_paragraph()


def _docx_picture(doc: Document, png: bytes, width_cm: float) -> None:
    from io import BytesIO as _BytesIO

    doc.add_picture(_BytesIO(png), width=Cm(width_cm))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER


def render_docx(data: dict[str, Any]) -> bytes:
    doc = Document()
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    section.left_margin = Cm(1.6)
    section.right_margin = Cm(1.6)
    section.top_margin = Cm(1.4)
    section.bottom_margin = Cm(1.4)

    normal = doc.styles["Normal"]
    normal.font.name = "微软雅黑"
    normal.font.size = Pt(9)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(data["title"])
    run.bold = True
    run.font.size = Pt(18)
    run.font.name = "微软雅黑"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

    for line in (
        f"提问内容：{data['question']}",
        f"统计范围：{data['scope']}",
        f"生成时间：{data['generated_at']}",
        f"范围内问题总数：{data['total']}",
    ):
        doc.add_paragraph(line)
    doc.add_paragraph()

    doc.add_heading("维度统计", level=2)
    _docx_table(
        doc,
        ["维度类型", "维度", "问题数", "占比"],
        [[item["type"], item["name"], item["count"], f"{item['share']}%"] for item in data["comparison"]],
    )

    if len(data["comparison"]) > 1:
        _docx_picture(doc, _bar_chart([item["name"] for item in data["comparison"]], [item["count"] for item in data["comparison"]], "各维度问题数"), 16)

    for dimension in data["dimensions"]:
        doc.add_page_break()
        doc.add_heading(f"{dimension['name']} · {dimension['count']} 条（占 {dimension['share']}%）", level=1)

        _docx_picture(
            doc,
            _bar_chart([x["label"] for x in dimension["by_month"]], [x["count"] for x in dimension["by_month"]], f"{dimension['name']} · 月度趋势"),
            17,
        )
        _docx_picture(
            doc,
            _pie_chart([x["label"] for x in dimension["by_cause"]], [x["count"] for x in dimension["by_cause"]], f"{dimension['name']} · 原因归属"),
            15,
        )

        doc.add_heading("按故障类型", level=3)
        _docx_table(doc, ["分类", "问题数"], [[x["label"], x["count"]] for x in dimension["by_fault_type"]])
        doc.add_heading("按原因归属", level=3)
        _docx_table(doc, ["分类", "问题数"], [[x["label"], x["count"]] for x in dimension["by_cause"]])
        doc.add_heading("按使用单位", level=3)
        _docx_table(doc, ["使用单位", "问题数"], [[x["label"], x["count"]] for x in dimension["by_customer"]])
        doc.add_heading("按月分布", level=3)
        _docx_table(doc, ["月份", "问题数"], [[x["label"], x["count"]] for x in dimension["by_month"]])

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def render_pdf(data: dict[str, Any]) -> bytes:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.4 * cm,
        rightMargin=1.4 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title=data["title"],
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("CNTitle", parent=styles["Title"], fontName="STSong-Light", fontSize=20, leading=26, alignment=TA_CENTER)
    h1 = ParagraphStyle("CNH1", parent=styles["Heading1"], fontName="STSong-Light", fontSize=14, leading=20, spaceBefore=10, spaceAfter=8)
    h2 = ParagraphStyle("CNH2", parent=styles["Heading2"], fontName="STSong-Light", fontSize=11, leading=16, spaceBefore=8, spaceAfter=5)
    body = ParagraphStyle("CNBody", parent=styles["BodyText"], fontName="STSong-Light", fontSize=9, leading=14, wordWrap="CJK")
    cell = ParagraphStyle("CNCell", parent=body, fontSize=8, leading=11)
    head = ParagraphStyle("CNHead", parent=cell, fontSize=8.5, leading=11, textColor=colors.white)

    story: list[Any] = [
        Paragraph(data["title"], title_style),
        Spacer(1, 6),
        Paragraph(f"提问内容：{data['question']}", body),
        Paragraph(f"统计范围：{data['scope']}　生成时间：{data['generated_at']}　问题总数：{data['total']}", body),
        Spacer(1, 10),
        Paragraph("维度统计", h1),
    ]

    def make_table(headers: list[str], rows: list[list[Any]], widths: list[float]) -> Table:
        table_rows = [[Paragraph(str(value), head) for value in headers]]
        for values in rows:
            table_rows.append([Paragraph(str(value), cell) for value in values])
        table = Table(table_rows, colWidths=widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return table

    story.append(make_table(["维度类型", "维度", "问题数", "占比"], [[x["type"], x["name"], x["count"], f"{x['share']}%"] for x in data["comparison"]], [5.5 * cm, 8 * cm, 3 * cm, 3 * cm]))

    if len(data["comparison"]) > 1:
        dimensions_png = _bar_chart([item["name"] for item in data["comparison"]], [item["count"] for item in data["comparison"]], "各维度问题数")
        story.append(Spacer(1, 8))
        story.append(Image(BytesIO(dimensions_png), width=16 * cm, height=7.3 * cm))

    for dimension in data["dimensions"]:
        story.append(PageBreak())
        story.append(Paragraph(f"{dimension['name']} · {dimension['count']} 条（占 {dimension['share']}%）", h1))

        monthly_png = _bar_chart([x["label"] for x in dimension["by_month"]], [x["count"] for x in dimension["by_month"]], f"{dimension['name']} · 月度趋势")
        cause_png = _pie_chart([x["label"] for x in dimension["by_cause"]], [x["count"] for x in dimension["by_cause"]], f"{dimension['name']} · 原因归属")
        charts = Table(
            [[Image(BytesIO(monthly_png), width=9.2 * cm, height=4.2 * cm), Image(BytesIO(cause_png), width=8.0 * cm, height=4.2 * cm)]],
            colWidths=[9.6 * cm, 8.4 * cm],
        )
        charts.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(charts)
        story.append(Spacer(1, 8))

        for label, key in (("按故障类型", "by_fault_type"), ("按原因归属", "by_cause"), ("按使用单位", "by_customer"), ("按月分布", "by_month")):
            story.append(Paragraph(label, h2))
            story.append(make_table(["分类", "问题数"], [[x["label"], x["count"]] for x in dimension[key]], [10 * cm, 3 * cm]))

    doc.build(story)
    return buffer.getvalue()


def generate_report(question: str, fmt: str) -> tuple[bytes, str, str]:
    fmt = (fmt or "").lower()
    data = build_report(question)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    if fmt in ("excel", "xlsx"):
        return render_excel(data), f"售后质量问题统计报表_{stamp}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if fmt == "pdf":
        return render_pdf(data), f"售后质量问题统计报表_{stamp}.pdf", "application/pdf"
    if fmt in ("doc", "docx", "word"):
        return render_docx(data), f"售后质量问题统计报表_{stamp}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    raise ValueError("报表格式只支持 excel、pdf、doc")
