"""数据库配置 - 异步 SQLite"""
import logging
import os
import shutil
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings
from app.utils.time_utils import bj_now

logger = logging.getLogger(__name__)

settings = get_settings()

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "weekly_scorer.db")
BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backups")


def backup_database():
    """备份数据库文件"""
    if not os.path.exists(DB_PATH):
        return None

    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = bj_now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"weekly_scorer_{timestamp}.db")
    shutil.copy2(DB_PATH, backup_path)

    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.endswith(".db")],
        key=lambda x: os.path.getmtime(os.path.join(BACKUP_DIR, x)),
        reverse=True,
    )
    for old_backup in backups[5:]:
        os.remove(os.path.join(BACKUP_DIR, old_backup))

    return backup_path

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    backup_database()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 对已有表做列迁移（SQLite 不支持自动改表）
    await _migrate_schema()


async def _migrate_schema():
    """
    检查 weekly_aggregates 表是否有最新列，没有则 ALTER TABLE 新增。
    这解决了"先建表后改模型"的场景，不会丢数据。

    注意：本函数仅在服务启动时执行，所有 SQL 片段均为硬编码内部常量，
    不处理外部输入，因此使用 text() 属 schema 迁移白名单场景。
    """
    ALLOWED_COL_NAMES = {
        "status", "manual_override", "modified_by", "modified_at",
        "recurrence", "weekdays", "last_run_date",
        "ai_connection_status", "ai_connection_provider",
        "ai_connection_model", "ai_connection_checked_at",
    }
    ALLOWED_COL_DEFS = {
        "status": "VARCHAR(20) NOT NULL DEFAULT 'pending'",
        "manual_override": "TEXT",
        "modified_by": "VARCHAR(100)",
        "modified_at": "DATETIME",
        "recurrence": "VARCHAR(16) DEFAULT 'daily'",
        "weekdays": "VARCHAR(32) DEFAULT ''",
        "last_run_date": "DATE",
        "ai_connection_status": "BOOLEAN",
        "ai_connection_provider": "VARCHAR(50)",
        "ai_connection_model": "VARCHAR(100)",
        "ai_connection_checked_at": "DATETIME",
    }
    async with engine.begin() as conn:
        # 1) weekly_aggregates 新增列检查
        try:
            # raw-sql-migration: SQLite PRAGMA 无对应 ORM API
            r = await conn.execute(text("PRAGMA table_info(weekly_aggregates)"))  # noqa: raw-sql-migration
            cols = {row[1] for row in r.fetchall()}
        except Exception:
            cols = set()

        weekly_agg_additions = [
            ("status", "VARCHAR(20) NOT NULL DEFAULT 'pending'"),
            ("manual_override", "TEXT"),
            ("modified_by", "VARCHAR(100)"),
            ("modified_at", "DATETIME"),
        ]
        for col_name, col_def in weekly_agg_additions:
            if col_name not in cols:
                if col_name not in ALLOWED_COL_NAMES or ALLOWED_COL_DEFS.get(col_name) != col_def:
                    logger.warning(f"[migration] weekly_aggregates 新增列 {col_name} 不在白名单，跳过")
                    continue
                try:
                    # raw-sql-migration: SQLite ALTER TABLE ADD COLUMN
                    await conn.execute(text(f"ALTER TABLE weekly_aggregates ADD COLUMN {col_name} {col_def}"))  # noqa: raw-sql-migration
                    logger.info(f"[migration] weekly_aggregates 新增列 {col_name}")
                except Exception as e:
                    logger.warning(f"[migration] weekly_aggregates 新增 {col_name} 失败: {e}")

        # 2) 创建 scoring_schedule 表（如果 Base.metadata.create_all 没处理到）
        try:
            # raw-sql-migration: sqlite_master 反射
            r = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='scoring_schedule'"))  # noqa: raw-sql-migration
            if r.fetchone() is None:
                # raw-sql-migration: SQLite CREATE TABLE 兜底
                # noqa: raw-sql-migration
                await conn.execute(text(
                    "CREATE TABLE scoring_schedule ("
                    "id VARCHAR(36) PRIMARY KEY, "
                    "enabled BOOLEAN DEFAULT 1, "
                    "hour INTEGER DEFAULT 3, "
                    "minute INTEGER DEFAULT 0, "
                    "recurrence VARCHAR(16) DEFAULT 'daily', "
                    "weekdays VARCHAR(32) DEFAULT '', "
                    "last_run_date DATE, "
                    "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
                ))
                logger.info("[migration] 已创建 scoring_schedule 表")
            else:
                # 3) scoring_schedule 已有表 → 检查新增列
                try:
                    r2 = await conn.execute(text("PRAGMA table_info(scoring_schedule)"))  # noqa: raw-sql-migration
                    sched_cols = {row[1] for row in r2.fetchall()}
                except Exception:
                    sched_cols = set()
                sched_additions = [
                    ("recurrence", "VARCHAR(16) DEFAULT 'daily'"),
                    ("weekdays", "VARCHAR(32) DEFAULT ''"),
                    ("last_run_date", "DATE"),
                ]
                for col_name, col_def in sched_additions:
                    if col_name not in sched_cols:
                        if col_name not in ALLOWED_COL_NAMES or ALLOWED_COL_DEFS.get(col_name) != col_def:
                            logger.warning(f"[migration] scoring_schedule 新增列 {col_name} 不在白名单，跳过")
                            continue
                        try:
                            await conn.execute(text(f"ALTER TABLE scoring_schedule ADD COLUMN {col_name} {col_def}"))  # noqa: raw-sql-migration
                            logger.info(f"[migration] scoring_schedule 新增列 {col_name}")
                        except Exception as e:
                            logger.warning(f"[migration] scoring_schedule 新增 {col_name} 失败: {e}")
        except Exception as e:
            logger.warning(f"[migration] 创建/升级 scoring_schedule 失败: {e}")

        # 4) scoring_configs 表：AI 连接状态缓存列
        try:
            r3 = await conn.execute(text("PRAGMA table_info(scoring_configs)"))  # noqa: raw-sql-migration
            sc_cols = {row[1] for row in r3.fetchall()}
        except Exception:
            sc_cols = set()
        sc_additions = [
            ("ai_connection_status", "BOOLEAN"),
            ("ai_connection_provider", "VARCHAR(50)"),
            ("ai_connection_model", "VARCHAR(100)"),
            ("ai_connection_checked_at", "DATETIME"),
        ]
        for col_name, col_def in sc_additions:
            if col_name in sc_cols:
                continue
            if col_name not in ALLOWED_COL_NAMES or ALLOWED_COL_DEFS.get(col_name) != col_def:
                logger.warning(f"[migration] scoring_configs 新增列 {col_name} 不在白名单，跳过")
                continue
            try:
                await conn.execute(text(f"ALTER TABLE scoring_configs ADD COLUMN {col_name} {col_def}"))  # noqa: raw-sql-migration
                logger.info(f"[migration] scoring_configs 新增列 {col_name}")
            except Exception as e:
                logger.warning(f"[migration] scoring_configs 新增 {col_name} 失败: {e}")
