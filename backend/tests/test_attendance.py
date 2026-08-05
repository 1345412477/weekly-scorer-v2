"""考勤解析与考勤评分（无规则兜底）测试"""
import os
import tempfile
from datetime import date

import pytest

from app.services.wechat_parser import (
    parse_attendance_excel,
    summarize_attendance_for_person,
)
from app.services.aggregator import _get_attendance_score
from app.services.ai_scorer import AIScoringError


def _make_sheet1_file(path: str):
    """构造与「上下班打卡_日报」Sheet1 相同结构的 Excel"""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["概况统计与打卡明细"])
    ws.append(["统计时间:06-01 ～ 06-07     制表时间:2026-06-07 17:23(UTC+8)"])
    ws.append(["时间", "姓名", "上班1", "", "下班1", "", "打卡时间记录"])
    ws.append(["", "", "打卡时间", "打卡状态", "打卡时间", "打卡状态", ""])
    # 张三：周日/周六休息，周五正常，周四迟到，周三缺下班卡，周二整天双缺
    ws.append(["2026/06/07 星期日", "张三", "--", "--", "--", "--", "--"])
    ws.append(["2026/06/06 星期六", "张三", "--", "--", "--", "--", "--"])
    ws.append(["2026/06/05 星期五", "张三", "09:00", "正常", "18:00", "正常", "09:00 18:00"])
    ws.append(["2026/06/04 星期四", "张三", "09:15", "迟到15分钟", "18:30", "正常", "09:15 18:30"])
    ws.append(["2026/06/03 星期三", "张三", "09:02", "正常", "--", "--", "09:02"])
    ws.append(["2026/06/02 星期二", "张三", "--", "--", "--", "--", "--"])
    # 李四：周一至周五全勤
    ws.append(["2026/06/07 星期日", "李四", "--", "--", "--", "--", "--"])
    ws.append(["2026/06/06 星期六", "李四", "--", "--", "--", "--", "--"])
    for d in range(1, 6):
        ws.append([f"2026/06/0{d} 星期{'一二三四五'[d - 1]}", "李四", "09:00", "正常", "18:00", "正常", "09:00 18:00"])
    wb.save(path)


@pytest.mark.asyncio
class TestSheet1AttendanceParsing:
    async def test_parse_sheet1(self):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            path = f.name
        try:
            _make_sheet1_file(path)
            records, employees = parse_attendance_excel(path)
            zhangsan = [r for r in records if r.get("author_name") == "张三"]
            assert len(zhangsan) == 6
            by_date = {r["record_date"].isoformat(): r for r in zhangsan}
            # 休息日时间缺失
            assert by_date["2026-06-07"]["check_in_time"] is None
            assert by_date["2026-06-07"]["check_out_time"] is None
            # 迟到状态保留
            assert "迟到" in (by_date["2026-06-04"]["attendance_status"] or "")
            # 缺下班卡 / 整天双缺
            assert by_date["2026-06-03"]["check_out_time"] is None
            assert by_date["2026-06-02"]["check_in_time"] is None
            assert "李四" in employees
        finally:
            os.unlink(path)

    async def test_summarize_contains_weekday_and_stats(self):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            path = f.name
        try:
            _make_sheet1_file(path)
            records, _ = parse_attendance_excel(path)
            summary = summarize_attendance_for_person(records, "张三")
            assert "（周日）" in summary
            assert "统计：工作日 4 天，休息日 2 天" in summary
            assert "迟到 1 次" in summary
            assert "缺卡 2 次" in summary
            assert "整天双缺 1 天" in summary
            assert "18点后加班 0.5h" in summary  # 6/4 下班 18:30
        finally:
            os.unlink(path)


@pytest.mark.asyncio
class TestAttendanceNoRuleFallback:
    async def test_ai_failure_returns_none(self, db, monkeypatch):
        from app.models.models import AttendanceRecord

        rec = AttendanceRecord(
            id="att-1",
            author_name="张三",
            week_start=date(2026, 6, 1),
            week_end=date(2026, 6, 7),
            record_date=date(2026, 6, 2),
            check_in_time="09:00",
            check_out_time="18:00",
        )
        db.add(rec)
        await db.commit()

        async def _fail(*args, **kwargs):
            raise AIScoringError("AI 服务不可用")

        monkeypatch.setattr("app.services.aggregator.score_attendance", _fail)
        result = await _get_attendance_score(
            db, "张三", date(2026, 6, 1), date(2026, 6, 7), "prompt"
        )
        assert result is None


@pytest.mark.asyncio
class TestAttendanceScoreAbove100:
    async def test_score_attendance_allows_overtime_over_100(self, monkeypatch):
        from app.services.ai_scorer import score_attendance

        async def fake_call(system_prompt, user_prompt, db=None):
            return (
                {"score": 112.0, "comment": "加班加分", "overtime_points": 12.0},
                "raw",
            )

        monkeypatch.setattr("app.services.ai_scorer._call_ai_with_retry", fake_call)
        result = await score_attendance("summary", "张三", "技术部", "prompt")
        assert result["score"] == 112.0
        assert result["overtime_points"] == 12.0

    async def test_aggregate_attendance_allows_over_100(self, db, monkeypatch):
        from app.models.models import AttendanceRecord
        from app.services.aggregator import _get_attendance_score

        rec = AttendanceRecord(
            id="att-over",
            author_name="李四",
            week_start=date(2026, 6, 1),
            week_end=date(2026, 6, 7),
            record_date=date(2026, 6, 2),
            check_in_time="09:00",
            check_out_time="20:30",
        )
        db.add(rec)
        await db.commit()

        async def fake_score(*args, **kwargs):
            return {"score": 105.0, "comment": "加班", "overtime_points": 5.0}

        monkeypatch.setattr("app.services.aggregator.score_attendance", fake_score)
        result = await _get_attendance_score(
            db, "李四", date(2026, 6, 1), date(2026, 6, 7), "prompt"
        )
        assert result == 105.0
