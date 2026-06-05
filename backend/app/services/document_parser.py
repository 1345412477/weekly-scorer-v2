"""文档解析服务 - 支持 Excel / Word / PDF 周报解析"""
import os
import re
from datetime import date, timedelta
from typing import Optional

import openpyxl


TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "周报模板.xlsx",
)


def get_template_path() -> str:
    return TEMPLATE_PATH


SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".docx", ".pdf"}


def parse_report(file_path: str) -> dict:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return _parse_excel(file_path)
    elif ext == ".docx":
        return _parse_docx(file_path)
    elif ext == ".pdf":
        return _parse_pdf(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")


def extract_week_dates(file_path: str) -> tuple[Optional[date], Optional[date]]:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return _extract_dates_from_excel(file_path)
    elif ext == ".docx":
        return _extract_dates_from_docx(file_path)
    elif ext == ".pdf":
        return _extract_dates_from_pdf(file_path)
    return None, None


def get_current_week(today: date = None) -> tuple[date, date]:
    if today is None:
        today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def classify_report_week(
    week_start: Optional[date], week_end: Optional[date]
) -> dict:
    today = date.today()
    current_monday, current_sunday = get_current_week(today)

    result = {
        "report_type": "normal",
        "week_diff": 0,
        "needs_confirmation": False,
        "is_future": False,
        "message": "",
    }

    if week_start is None or week_end is None:
        result["report_type"] = "unknown"
        result["needs_confirmation"] = True
        result["message"] = "无法从文件中识别周报时间，请手动确认周报所属周次"
        return result

    if week_start > current_sunday:
        result["is_future"] = True
        result["report_type"] = "future"
        result["message"] = f"无法提交未来时间的周报。文件标注时间为 {week_start} ~ {week_end}，当前周为 {current_monday} ~ {current_sunday}"
        return result

    if week_start >= current_monday and week_end <= current_sunday:
        result["report_type"] = "normal"
        result["week_diff"] = 0
        result["message"] = "本周周报"
        return result

    if week_end < current_monday:
        diff_days = (current_monday - week_start).days
        weeks_behind = max(1, diff_days // 7)
        result["report_type"] = "catch_up"
        result["week_diff"] = weeks_behind
        result["message"] = f"补周报：这是 {weeks_behind} 周前的周报（{week_start} ~ {week_end}）"
        return result

    result["report_type"] = "normal"
    result["message"] = "本周周报"
    return result


def _dates_from_text(text: str) -> tuple[Optional[date], Optional[date]]:
    patterns = [
        r'(\d{4})[.\-/年](\d{1,2})[.\-/月](\d{1,2})',
    ]
    all_dates = []
    for pat in patterns:
        for m in re.finditer(pat, text):
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                all_dates.append(d)
            except (ValueError, IndexError):
                continue

    if len(all_dates) >= 2:
        all_dates.sort()
        return all_dates[0], all_dates[-1]
    return None, None


# ── Excel 解析 ──

def _parse_excel(file_path: str) -> dict:
    wb = openpyxl.load_workbook(file_path)
    ws = wb.active

    result = {
        "title": ws.title,
        "last_week_work": [],
        "this_week_plan": [],
        "raw_content": "",
    }

    current_section = None
    headers = []

    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=ws.max_column, values_only=False):
        first_cell = row[0]
        if first_cell.value is None:
            continue

        cell_value = str(first_cell.value).strip()

        if "上周工作" in cell_value:
            current_section = "last_week"
            headers = []
            continue
        elif "本周工作" in cell_value:
            current_section = "this_week"
            headers = []
            continue

        if current_section is None:
            continue

        row_values = [str(cell.value).strip() if cell.value is not None else "" for cell in row]

        if cell_value == "序号" or (len(row_values) > 1 and row_values[1] in ["客户/项目", "项目"]):
            headers = row_values
            continue

        if not headers:
            continue

        try:
            int(cell_value)
        except ValueError:
            continue

        item = {}
        for i, h in enumerate(headers):
            if i < len(row_values):
                item[h] = row_values[i]

        if current_section == "last_week":
            result["last_week_work"].append(item)
        elif current_section == "this_week":
            result["this_week_plan"].append(item)

    result["raw_content"] = _build_text_content(result)
    wb.close()
    return result


def _extract_dates_from_excel(file_path: str) -> tuple[Optional[date], Optional[date]]:
    wb = openpyxl.load_workbook(file_path)
    ws = wb.active

    for row in ws.iter_rows(min_row=1, max_row=min(10, ws.max_row), max_col=ws.max_column, values_only=False):
        first_cell = row[0]
        if first_cell.value is None:
            continue
        cell_value = str(first_cell.value)
        if "上周" in cell_value or "本周" in cell_value or "工作" in cell_value:
            d1, d2 = _dates_from_text(cell_value)
            if d1 and d2:
                wb.close()
                return d1, d2

    wb.close()
    return None, None


# ── Word 解析 ──

def _parse_docx(file_path: str) -> dict:
    try:
        from docx import Document
    except ImportError:
        raise ImportError("需要安装 python-docx: pip install python-docx")

    doc = Document(file_path)

    result = {
        "title": "",
        "last_week_work": [],
        "this_week_plan": [],
        "raw_content": "",
    }

    current_section = None
    headers = []
    all_text_parts = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        all_text_parts.append(text)

        if "上周工作" in text or "上周工作内容" in text:
            current_section = "last_week"
            headers = []
            continue
        elif "本周工作" in text or "本周工作计划" in text:
            current_section = "this_week"
            headers = []
            continue

    for table in doc.tables:
        for row_idx, row in enumerate(table.rows):
            cells = [cell.text.strip() for cell in row.cells]

            if any("序号" in c for c in cells) and any("项目" in c or "工作" in c for c in cells):
                headers = cells
                if current_section is None:
                    current_section = "last_week"
                continue

            if not headers or not cells:
                continue

            try:
                int(cells[0])
            except (ValueError, IndexError):
                continue

            item = {}
            for i, h in enumerate(headers):
                if i < len(cells):
                    item[h] = cells[i]

            if current_section == "last_week":
                result["last_week_work"].append(item)
            elif current_section == "this_week":
                result["this_week_plan"].append(item)

    if not result["last_week_work"] and not result["this_week_plan"]:
        result["raw_content"] = "\n".join(all_text_parts)
    else:
        result["raw_content"] = _build_text_content(result)

    return result


def _extract_dates_from_docx(file_path: str) -> tuple[Optional[date], Optional[date]]:
    try:
        from docx import Document
    except ImportError:
        return None, None

    doc = Document(file_path)
    for para in doc.paragraphs[:20]:
        text = para.text.strip()
        if text:
            d1, d2 = _dates_from_text(text)
            if d1 and d2:
                return d1, d2
    return None, None


# ── PDF 解析 ──

def _parse_pdf(file_path: str) -> dict:
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("需要安装 pdfplumber: pip install pdfplumber")

    result = {
        "title": "",
        "last_week_work": [],
        "this_week_plan": [],
        "raw_content": "",
    }

    all_text_parts = []
    current_section = None
    headers = []

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text:
                all_text_parts.append(text)

            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or all(cell is None for cell in row):
                        continue
                    cells = [str(cell).strip() if cell else "" for cell in row]

                    if any("序号" in c for c in cells) and any("项目" in c or "工作" in c for c in cells):
                        headers = cells
                        if current_section is None:
                            current_section = "last_week"
                        continue

                    if not headers:
                        continue

                    try:
                        int(cells[0])
                    except (ValueError, IndexError):
                        continue

                    item = {}
                    for i, h in enumerate(headers):
                        if i < len(cells):
                            item[h] = cells[i]

                    if current_section == "last_week":
                        result["last_week_work"].append(item)
                    elif current_section == "this_week":
                        result["this_week_plan"].append(item)

    full_text = "\n".join(all_text_parts)

    if not result["last_week_work"] and not result["this_week_plan"]:
        result["raw_content"] = full_text
    else:
        result["raw_content"] = _build_text_content(result)

    return result


def _extract_dates_from_pdf(file_path: str) -> tuple[Optional[date], Optional[date]]:
    try:
        import pdfplumber
    except ImportError:
        return None, None

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages[:3]:
            text = page.extract_text() or ""
            if text:
                d1, d2 = _dates_from_text(text)
                if d1 and d2:
                    return d1, d2
    return None, None


# ── 通用工具 ──

def _build_text_content(parsed: dict) -> str:
    lines = []

    if parsed["last_week_work"]:
        lines.append("## 上周工作内容")
        lines.append("")
        for i, item in enumerate(parsed["last_week_work"], 1):
            project = item.get("客户/项目", item.get("项目", ""))
            content = item.get("工作内容", "")
            reporter = item.get("汇报人", "")
            feedback = item.get("结果反馈", "")
            lines.append(f"### {i}. {project}")
            if content:
                lines.append(f"- 工作内容：{content}")
            if reporter:
                lines.append(f"- 汇报人：{reporter}")
            if feedback:
                lines.append(f"- 结果反馈：{feedback}")
            lines.append("")

    if parsed["this_week_plan"]:
        lines.append("## 本周工作计划")
        lines.append("")
        for i, item in enumerate(parsed["this_week_plan"], 1):
            project = item.get("客户/项目", item.get("项目", ""))
            content = item.get("工作内容", "")
            reporter = item.get("汇报人", "")
            feedback = item.get("结果反馈", "")
            lines.append(f"### {i}. {project}")
            if content:
                lines.append(f"- 工作内容：{content}")
            if reporter:
                lines.append(f"- 汇报人：{reporter}")
            if feedback:
                lines.append(f"- 预期产出：{feedback}")
            lines.append("")

    return "\n".join(lines)
