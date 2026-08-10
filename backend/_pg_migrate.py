"""
补 weekly_aggregates.error_message / weekly_aggregates.retry_count / idx_aggregate_status
的独立迁移脚本。

用法（线上服务器 backend 目录下执行）：
    python _pg_migrate.py

该脚本会自动读取 .env 中的 DATABASE_URL（兼容 SQLite 和 PostgreSQL），
如果不提供就用默认 SQLite，对 PostgreSQL 会跑 ALTER TABLE 补列并创建缺失索引。
全程幂等：重复执行不会报错。

部署建议：
    1) 先执行本脚本补列；
    2) 再重启/部署新版后端服务。
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from app.database import engine, _get_existing_columns, _table_exists, _IS_SQLITE, _IS_POSTGRES
from app.config import get_settings
from sqlalchemy import text

settings = get_settings()

print("=" * 70)
print("智友辰评分系统 - 每周聚合表补列迁移 v1.0")
print("=" * 70)
print(f"[INFO] 当前数据库类型: {'SQLite' if _IS_SQLITE else 'PostgreSQL'}")
print(f"[INFO] DATABASE_URL = {settings.DATABASE_URL[:80]}{'...' if len(settings.DATABASE_URL) > 80 else ''}")
print()


async def main():
    ok_count = 0
    warn_count = 0
    skip_count = 0
    err_count = 0

    async with engine.begin() as conn:
        # =====================================================
        # 1. 补列: error_message / retry_count
        # =====================================================
        cols = await _get_existing_columns(conn, "weekly_aggregates")
        print(f"[1/3] weekly_aggregates 现有列: {sorted(cols)}")
        need_cols = [
            ("error_message", "TEXT DEFAULT ''"),
            ("retry_count", "INTEGER NOT NULL DEFAULT 0"),
            ("status", "VARCHAR(20) NOT NULL DEFAULT 'pending'"),
            ("modified_at", "TIMESTAMP"),
            ("modified_by", "VARCHAR(100)"),
            ("manual_override", "TEXT"),
        ]
        for col_name, col_def in need_cols:
            if col_name in cols:
                skip_count += 1
                print(f"   - {col_name:20s} 已存在，跳过")
                continue
            try:
                sql = f"ALTER TABLE weekly_aggregates ADD COLUMN {col_name} {col_def}"
                await conn.execute(text(sql))
                ok_count += 1
                print(f"   ✅ {col_name:20s} 新增成功  ({col_def})")
            except Exception as e:
                err_count += 1
                print(f"   ❌ {col_name:20s} 新增失败: {e}")

        # =====================================================
        # 2. 补索引: idx_aggregate_status
        # =====================================================
        print()
        print("[2/3] 检查索引 idx_aggregate_status ...")
        try:
            if _IS_SQLITE:
                r = await conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_aggregate_status'"
                ))
                exists = r.scalar() is not None
            elif _IS_POSTGRES:
                r = await conn.execute(text("""
                    SELECT indexname FROM pg_indexes
                    WHERE tablename = 'weekly_aggregates' AND indexname = 'idx_aggregate_status'
                """))
                exists = r.scalar() is not None
            else:
                exists = False

            if exists:
                skip_count += 1
                print("   - 索引已存在，跳过")
            else:
                await conn.execute(text(
                    "CREATE INDEX idx_aggregate_status ON weekly_aggregates (status)"
                ))
                ok_count += 1
                print("   ✅ 索引 idx_aggregate_status 已创建")
        except Exception as e:
            err_count += 1
            print(f"   ❌ 索引创建失败: {e}")

        # =====================================================
        # 3. PostgreSQL: 补唯一约束 uq_aggregate_author_week
        # =====================================================
        print()
        print("[3/3] 检查唯一约束 uq_aggregate_author_week ...")
        if _IS_POSTGRES:
            try:
                r = await conn.execute(text("""
                    SELECT conname FROM pg_constraint
                    WHERE conrelid = 'weekly_aggregates'::regclass AND conname = 'uq_aggregate_author_week'
                """))
                exists = r.scalar() is not None
                if exists:
                    skip_count += 1
                    print("   - 约束已存在，跳过")
                else:
                    # 先清理重复
                    await conn.execute(text("""
                        DELETE FROM weekly_aggregates WHERE id NOT IN (
                            SELECT id FROM (
                                SELECT id, ROW_NUMBER() OVER (
                                    PARTITION BY author_name, week_start
                                    ORDER BY created_at DESC
                                ) as rn
                                FROM weekly_aggregates
                            ) _t WHERE rn = 1
                        )
                    """))
                    print("   - 已清理重复记录")
                    await conn.execute(text("""
                        ALTER TABLE weekly_aggregates
                        ADD CONSTRAINT uq_aggregate_author_week UNIQUE (author_name, week_start)
                    """))
                    ok_count += 1
                    print("   ✅ 唯一约束 uq_aggregate_author_week 已创建")
            except Exception as e:
                warn_count += 1
                print(f"   ⚠  唯一约束处理失败（可忽略，仅优化去重）: {e}")
        else:
            skip_count += 1
            print("   - SQLite 不支持在线 ADD CONSTRAINT，跳过（不影响核心功能）")

    await engine.dispose()

    print()
    print("=" * 70)
    print(f"迁移完成：成功 {ok_count} 项，跳过 {skip_count} 项，警告 {warn_count} 项，失败 {err_count} 项")
    if err_count == 0:
        print("✅ 数据库结构已与最新代码模型对齐，可以安全启动后端服务。")
    else:
        print("❌ 存在失败项，请检查上方错误日志后重试或联系开发。")
        sys.exit(2)


if __name__ == '__main__':
    asyncio.run(main())
