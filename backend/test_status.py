import asyncio
from datetime import date, datetime, timedelta
from app.database import async_session
from app.models.models import ChatRecord, DataUploadLog
from sqlalchemy import select, func, and_

async def main():
    async with async_session() as db:
        today = date(2026, 7, 16)
        offset = today.weekday()
        week_start = today - timedelta(days=offset)
        week_end = week_start + timedelta(days=6)
        
        # 查最近一条 chat 上传日志
        q = select(DataUploadLog).where(DataUploadLog.data_type == "chat").order_by(DataUploadLog.created_at.desc()).limit(1)
        last = (await db.execute(q)).scalar_one_or_none()
        
        if last:
            # 修复后的逻辑：直接用 record_count
            print(f"=== 修复后 ===")
            print(f"last_upload.record_count: {last.record_count}")
            print(f"last_upload.filename: {last.filename}")
            print(f"last_upload.employees_matched: {last.employees_matched}")
            
            # 修复前的逻辑：按周范围查
            total_q = select(func.sum(ChatRecord.message_count)).where(
                and_(ChatRecord.week_start >= last.week_start, ChatRecord.week_start <= last.week_end)
            )
            old_total = (await db.execute(total_q)).scalar() or 0
            print(f"\n=== 修复前（按周范围） ===")
            print(f"record_count: {old_total}")
            print(f"\n修复效果: {old_total} -> {last.record_count}")

asyncio.run(main())
