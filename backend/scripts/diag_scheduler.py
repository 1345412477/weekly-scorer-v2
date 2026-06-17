"""定时任务快速验证 - 直接用 Python """
import sys
sys.path.insert(0, r"c:\Users\13454\Projects\weekly-scorer-v2\backend")

from app.database import async_session
from app.models.models import ScoringSchedule
from app.api.weekly_aggregates import _parse_weekdays
from app.core.task_queue import update_aggregate_schedule, get_aggregate_schedule
from app.utils.time_utils import bj_now
from sqlalchemy import select
import asyncio


async def main():
    print("=== 1. 查 DB 配置 ===")
    async with async_session() as db:
        result = await db.execute(select(ScoringSchedule).limit(1))
        cfg = result.scalar_one_or_none()
        if cfg:
            print(f"  enabled = {cfg.enabled}")
            print(f"  hour = {cfg.hour}, minute = {cfg.minute}")
            print(f"  recurrence = {getattr(cfg, 'recurrence', 'daily')}")
            print(f"  weekdays raw = '{getattr(cfg, 'weekdays', '')}'")
            print(f"  _parse_weekdays = {_parse_weekdays(getattr(cfg, 'weekdays', ''))}")
        else:
            print("  DB 中无 ScoringSchedule 记录")

    print("\n=== 2. 模拟用户保存 weekly 配置 ===")
    # 模拟用户前端选择: 每周日 03:30, recurrence=weekly, weekdays=[0,2,4]
    update_aggregate_schedule(enabled=True, hour=3, minute=30, recurrence="weekly", weekdays=[0,2,4])
    print(f"  当前内存配置 = {get_aggregate_schedule()}")

    print("\n=== 3. 模拟用户保存 daily 配置 ===")
    update_aggregate_schedule(enabled=True, hour=12, minute=0, recurrence="daily", weekdays=None)
    print(f"  当前内存配置 = {get_aggregate_schedule()}")

    print("\n=== 4. 当前北京时间 ==", bj_now().strftime("%Y-%m-%d %H:%M:%S"))

asyncio.run(main())
