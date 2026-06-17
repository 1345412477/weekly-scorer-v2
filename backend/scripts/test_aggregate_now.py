"""模拟定时任务 auto_aggregate_for_latest_week 看异常"""
import asyncio, logging, sys
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
sys.path.insert(0, r"c:\Users\13454\Projects\weekly-scorer-v2\backend")

from app.database import async_session
from app.services.aggregator import auto_aggregate_for_latest_week


async def main():
    async with async_session() as db:
        print("=== 开始执行 auto_aggregate_for_latest_week ===\n")
        try:
            n = await auto_aggregate_for_latest_week(db)
            print(f"\n=== 完成! 处理了 {n} 人 ===")
        except Exception as e:
            import traceback
            print(f"\n=== 失败! ===")
            traceback.print_exc()

asyncio.run(main())
