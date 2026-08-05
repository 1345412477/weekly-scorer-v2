"""Dashboard 异常人员分类（未提交/迟交/补交）测试"""
from datetime import date, datetime, timedelta

import pytest

from app.models.models import WeeklyReport
from tests.conftest import get_current_week


def _hours_after(day: date, hours: float) -> datetime:
    return datetime(day.year, day.month, day.day) + timedelta(hours=hours)


@pytest.mark.asyncio
class TestDashboardDeadlineClassification:
    async def test_abnormal_persons_three_way(self, client, db, seed_persons):
        current_monday, current_sunday = get_current_week()
        last_monday = current_monday - timedelta(days=7)
        last_sunday = current_sunday - timedelta(days=7)

        deadline = _hours_after(last_monday, 159)      # 本周日 15:00
        late_deadline = _hours_after(last_monday, 327)  # 下周日 15:00

        reports = [
            WeeklyReport(
                id="d-ok",
                author_name="张三",
                department="技术部",
                person_id="person-1",
                department_id="dept-tech",
                week_start=last_monday,
                week_end=last_sunday,
                content="正常提交",
                status="scored",
                submit_time=deadline - timedelta(hours=1),
            ),
            WeeklyReport(
                id="d-late",
                author_name="李四",
                department="产品部",
                person_id="person-2",
                department_id="dept-product",
                week_start=last_monday,
                week_end=last_sunday,
                content="迟交",
                status="scored",
                submit_time=late_deadline - timedelta(hours=1),
            ),
            WeeklyReport(
                id="d-catchup",
                author_name="王五",
                department="技术部",
                person_id="person-3",
                department_id="dept-tech",
                week_start=last_monday,
                week_end=last_sunday,
                content="补交",
                status="scored",
                submit_time=late_deadline + timedelta(hours=1),
            ),
        ]
        db.add_all(reports)
        await db.commit()

        resp = await client.get("/api/v1/leaderboard/dashboard")
        assert resp.status_code == 200
        data = resp.json()

        by_name = {item["name"]: item["status"] for item in data["abnormal_persons"]}
        # 正常提交的人不出现在异常列表
        assert "张三" not in by_name
        assert by_name["李四"] == "迟交"
        assert by_name["王五"] == "补交"
        assert by_name["赵六"] == "未提交"

        assert data["not_submitted_count"] == 1
        assert data["late_submitted_count"] == 1
        assert data["make_up_submitted_count"] == 1
