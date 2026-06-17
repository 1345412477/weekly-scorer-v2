"""诊断定时聚合执行结果"""
import asyncio
import sys
sys.path.insert(0, r"c:\Users\13454\Projects\weekly-scorer-v2\backend")

from datetime import date, timedelta
from app.database import async_session
from app.models.models import Person, WeeklyReport, WeeklyAggregate, ScoringSchedule
from sqlalchemy import select, func

async def main():
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    print(f"=== 本周: {week_start} ~ {week_end} ({today}, 周{'一二三四五六日'[today.weekday()]}) ===\n")

    async with async_session() as db:
        r = await db.execute(select(ScoringSchedule).limit(1))
        cfg = r.scalar_one_or_none()
        if cfg:
            print(f"[1] 定时: enabled={cfg.enabled} {cfg.recurrence} weekdays={cfg.weekdays} {cfg.hour:02d}:{cfg.minute:02d}")
        else:
            print("[1] 无定时配置")

        r2 = await db.execute(select(func.count()).select_from(Person).where(Person.is_active == True))
        p_cnt = r2.scalar() or 0
        print(f"[2] 活跃人员: {p_cnt}")

        r3 = await db.execute(select(WeeklyReport).where(WeeklyReport.week_start == week_start))
        reports = list(r3.scalars().all())
        print(f"[3] 本周周报: {len(reports)} 份")
        for rp in reports[:10]:
            print(f"    {rp.author_name} | {rp.status} | {rp.department}")

        r4 = await db.execute(select(WeeklyAggregate).where(WeeklyAggregate.week_start == week_start))
        aggs = list(r4.scalars().all())
        print(f"[4] 本周聚合: {len(aggs)} 条")
        for a in aggs[:10]:
            print(f"    {a.author_name} | {a.status} | R={a.report_score} A={a.attendance_score} C={a.chat_score} => {a.composite_score} | {a.updated_at}")

        if not reports and aggs:
            print(f"\n正常：{p_cnt}位员工无周报，聚合为0分记录已写入")
        elif reports and not aggs:
            print(f"\n❌ 异常：有{len(reports)}份周报但聚合表为空！")

asyncio.run(main())
