"""端到端验证：模拟后端启动（init_scheduler）→ 配置写入 → 调度线程状态"""
import asyncio
import sys
sys.path.insert(0, r"c:\Users\13454\Projects\weekly-scorer-v2\backend")

from app.core.task_queue import (
    init_scheduler,
    update_aggregate_schedule,
    get_aggregate_schedule,
    _scheduler_thread,
)
from app.utils.time_utils import bj_now


async def main():
    print("=== 阶段 1: 启动前，检查当前配置 ===")
    print(f"  启动前配置: {get_aggregate_schedule()}")
    print(f"  _scheduler_thread 是否存在: {_scheduler_thread is not None}")

    print("\n=== 阶段 2: 启动调度线程 ===")
    await init_scheduler()
    print(f"  启动后配置: {get_aggregate_schedule()}")
    print(f"  _scheduler_thread 是否活着: {_scheduler_thread.is_alive() if _scheduler_thread else False}")

    print(f"\n=== 阶段 3: 模拟用户保存 weekly 配置 ===")
    update_aggregate_schedule(enabled=True, hour=3, minute=30, recurrence="weekly", weekdays=[0,2,4])
    print(f"  更新后配置: {get_aggregate_schedule()}")

    print(f"\n=== 阶段 4: 当前北京时间 == {bj_now().strftime('%Y-%m-%d %H:%M:%S')}")

asyncio.run(main())
