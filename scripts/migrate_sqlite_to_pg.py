#!/usr/bin/env python3
"""
SQLite → PostgreSQL 数据迁移脚本

用法:
  python migrate_sqlite_to_pg.py --sqlite ./backend/weekly_scorer.db --pg "postgresql+asyncpg://user:pass@host/db"

功能:
  1. 读取 SQLite 数据库所有表数据
  2. 写入 PostgreSQL（自动建表 + 插入数据）
  3. 迁移前后自动备份
  4. 支持 dry-run 模式（只读不写）
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

import aiosqlite
import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("migrate")

# 表结构映射：SQLite → PostgreSQL
# 注意：SQLAlchemy 的 create_all 会自动建表，此脚本只负责数据迁移
TABLE_ORDER = [
    "departments",
    "persons",
    "scoring_configs",
    "scoring_dimensions",
    "ai_models",
    "weekly_reports",
    "report_scores",
    "weekly_aggregates",
    "department_summaries",
    "upload_logs",
    "scoring_schedule",
]


async def get_sqlite_tables(sqlite_path: str) -> dict:
    """读取 SQLite 所有表数据"""
    data = {}
    async with aiosqlite.connect(sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in await cursor.fetchall()]

        for table in tables:
            cursor = await db.execute(f"SELECT * FROM {table}")
            columns = [desc[0] for desc in cursor.description]
            rows = []
            async for row in cursor:
                row_dict = dict(row)
                # 处理 SQLite 特有的类型
                for k, v in row_dict.items():
                    if isinstance(v, bytes):
                        row_dict[k] = v.decode("utf-8", errors="replace")
                rows.append(row_dict)
            data[table] = {"columns": columns, "rows": rows}
            log.info(f"  SQLite [{table}]: {len(rows)} rows, columns={columns}")

    return data


async def migrate_to_postgres(pg_dsn: str, data: dict, dry_run: bool = False):
    """将数据写入 PostgreSQL"""
    if dry_run:
        log.info("[DRY RUN] 不会写入任何数据")
        for table, info in data.items():
            log.info(f"  [DRY RUN] {table}: {len(info['rows'])} rows")
        return

    conn = await asyncpg.connect(pg_dsn)
    try:
        for table in TABLE_ORDER:
            if table not in data:
                log.info(f"  跳过 {table}（无数据）")
                continue

            info = data[table]
            columns = info["columns"]
            rows = info["rows"]

            if not rows:
                log.info(f"  {table}: 0 rows, 跳过")
                continue

            # 构建 INSERT 语句（ON CONFLICT DO NOTHING 避免重复）
            col_list = ", ".join(columns)
            placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))

            # 获取主键列（用于 ON CONFLICT）
            pk_result = await conn.fetch("""
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = $1::regclass AND i.indisprimary
            """, table)

            conflict_cols = ", ".join(r["attname"] for r in pk_result) if pk_result else None

            inserted = 0
            skipped = 0
            for row in rows:
                values = []
                for col in columns:
                    v = row.get(col)
                    # 处理 JSON 字段
                    if isinstance(v, (dict, list)):
                        v = json.dumps(v, ensure_ascii=False)
                    values.append(v)

                try:
                    if conflict_cols:
                        await conn.execute(
                            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT ({conflict_cols}) DO NOTHING",
                            *values,
                        )
                    else:
                        await conn.execute(
                            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",
                            *values,
                        )
                    inserted += 1
                except asyncpg.UniqueViolationError:
                    skipped += 1
                except Exception as e:
                    log.error(f"  插入 {table} 失败: {e}, row={row.get('id', 'N/A')}")

            log.info(f"  {table}: inserted={inserted}, skipped={skipped}")

        log.info("迁移完成!")
    finally:
        await conn.close()


async def main():
    parser = argparse.ArgumentParser(description="SQLite → PostgreSQL 数据迁移")
    parser.add_argument("--sqlite", required=True, help="SQLite 数据库文件路径")
    parser.add_argument("--pg", required=True, help="PostgreSQL DSN (postgresql+asyncpg://user:pass@host/db)")
    parser.add_argument("--dry-run", action="store_true", help="只读取不写入")
    parser.add_argument("--backup", action="store_true", default=True, help="迁移前备份 SQLite（默认开启）")
    args = parser.parse_args()

    if not os.path.exists(args.sqlite):
        log.error(f"SQLite 文件不存在: {args.sqlite}")
        sys.exit(1)

    # 备份 SQLite
    if args.backup and not args.dry_run:
        backup_path = f"{args.sqlite}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        import shutil
        shutil.copy2(args.sqlite, backup_path)
        log.info(f"SQLite 已备份: {backup_path}")

    # 读取 SQLite 数据
    log.info("读取 SQLite 数据...")
    data = await get_sqlite_tables(args.sqlite)

    total_rows = sum(len(info["rows"]) for info in data.values())
    log.info(f"共 {len(data)} 张表, {total_rows} 行数据")

    # 迁移到 PostgreSQL
    log.info("写入 PostgreSQL...")
    await migrate_to_postgres(args.pg, data, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
