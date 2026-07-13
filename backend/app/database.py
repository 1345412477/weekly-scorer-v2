"""数据库配置 - 支持 SQLite 和 PostgreSQL"""
import logging
import os
import shutil
from datetime import datetime
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings
from app.utils.time_utils import bj_now

logger = logging.getLogger(__name__)

settings = get_settings()

# 检测数据库类型
_IS_POSTGRES = settings.DATABASE_URL.startswith("postgresql")
_IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")

# Docker 环境中数据库在 /app/data/，开发环境在 backend/ 目录
_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.dirname(__file__)))
DB_PATH = os.path.join(_DATA_DIR, "weekly_scorer.db")
BACKUP_DIR = os.path.join(_DATA_DIR, "backups")


def backup_database():
    """备份数据库文件（仅 SQLite 需要文件级备份）"""
    if not _IS_SQLITE or not os.path.exists(DB_PATH):
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


def _get_engine_kwargs() -> dict:
    """根据数据库类型返回引擎配置"""
    kwargs: dict = {"echo": False}
    if _IS_POSTGRES:
        kwargs.update({
            "pool_size": 10,
            "max_overflow": 20,
            "pool_pre_ping": True,
            "pool_recycle": 300,
        })
    elif _IS_SQLITE:
        kwargs["connect_args"] = {"check_same_thread": False}
    return kwargs


engine = create_async_engine(settings.DATABASE_URL, **_get_engine_kwargs())
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
    await _migrate_schema()


async def _get_existing_columns(conn, table_name: str) -> set:
    """获取表的已有列名（兼容 SQLite 和 PostgreSQL）"""
    if _IS_SQLITE:
        r = await conn.execute(text(f"PRAGMA table_info({table_name})"))
        return {row[1] for row in r.fetchall()}
    else:
        # PostgreSQL: 使用 information_schema
        r = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :table_name
        """), {"table_name": table_name})
        return {row[0] for row in r.fetchall()}


async def _table_exists(conn, table_name: str) -> bool:
    """检查表是否存在（兼容 SQLite 和 PostgreSQL）"""
    if _IS_SQLITE:
        r = await conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=:name"
        ), {"name": table_name})
    else:
        r = await conn.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = :name
        """), {"name": table_name})
    return r.fetchone() is not None


async def _migrate_schema():
    """
    检查表是否有最新列，没有则 ALTER TABLE 新增。
    兼容 SQLite 和 PostgreSQL。
    """
    ALLOWED_COLUMNS = {
        "status": "VARCHAR(20) NOT NULL DEFAULT 'pending'",
        "manual_override": "TEXT",
        "modified_by": "VARCHAR(100)",
        "modified_at": "TIMESTAMP",
        "recurrence": "VARCHAR(16) DEFAULT 'daily'",
        "weekdays": "VARCHAR(32) DEFAULT ''",
        "last_run_date": "DATE",
        "ai_connection_status": "BOOLEAN",
        "ai_connection_provider": "VARCHAR(50)",
        "ai_connection_model": "VARCHAR(100)",
        "ai_connection_checked_at": "TIMESTAMP",
    }

    async with engine.begin() as conn:
        # 1) weekly_aggregates 新增列检查
        try:
            cols = await _get_existing_columns(conn, "weekly_aggregates")
        except Exception:
            cols = set()

        weekly_agg_additions = [
            ("status", "VARCHAR(20) NOT NULL DEFAULT 'pending'"),
            ("manual_override", "TEXT"),
            ("modified_by", "VARCHAR(100)"),
            ("modified_at", "TIMESTAMP"),
        ]
        for col_name, col_def in weekly_agg_additions:
            if col_name not in cols:
                if ALLOWED_COLUMNS.get(col_name) != col_def:
                    logger.warning(f"[migration] weekly_aggregates 新增列 {col_name} 不在白名单，跳过")
                    continue
                try:
                    await conn.execute(text(f"ALTER TABLE weekly_aggregates ADD COLUMN {col_name} {col_def}"))
                    logger.info(f"[migration] weekly_aggregates 新增列 {col_name}")
                except Exception as e:
                    logger.warning(f"[migration] weekly_aggregates 新增 {col_name} 失败: {e}")

        # 2) 创建 scoring_schedule 表（如果 Base.metadata.create_all 没处理到）
        try:
            if not await _table_exists(conn, "scoring_schedule"):
                if _IS_SQLITE:
                    ts_default = "DATETIME DEFAULT CURRENT_TIMESTAMP"
                    bool_default = "BOOLEAN DEFAULT 1"
                else:
                    ts_default = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                    bool_default = "BOOLEAN DEFAULT true"

                await conn.execute(text(
                    f"CREATE TABLE scoring_schedule ("
                    f"id VARCHAR(36) PRIMARY KEY, "
                    f"enabled {bool_default}, "
                    f"hour INTEGER DEFAULT 3, "
                    f"minute INTEGER DEFAULT 0, "
                    f"recurrence VARCHAR(16) DEFAULT 'daily', "
                    f"weekdays VARCHAR(32) DEFAULT '', "
                    f"last_run_date DATE, "
                    f"created_at {ts_default}, "
                    f"updated_at {ts_default})"
                ))
                logger.info("[migration] 已创建 scoring_schedule 表")
            else:
                # 3) scoring_schedule 已有表 → 检查新增列
                try:
                    sched_cols = await _get_existing_columns(conn, "scoring_schedule")
                except Exception:
                    sched_cols = set()
                sched_additions = [
                    ("recurrence", "VARCHAR(16) DEFAULT 'daily'"),
                    ("weekdays", "VARCHAR(32) DEFAULT ''"),
                    ("last_run_date", "DATE"),
                ]
                for col_name, col_def in sched_additions:
                    if col_name not in sched_cols:
                        if ALLOWED_COLUMNS.get(col_name) != col_def:
                            logger.warning(f"[migration] scoring_schedule 新增列 {col_name} 不在白名单，跳过")
                            continue
                        try:
                            await conn.execute(text(f"ALTER TABLE scoring_schedule ADD COLUMN {col_name} {col_def}"))
                            logger.info(f"[migration] scoring_schedule 新增列 {col_name}")
                        except Exception as e:
                            logger.warning(f"[migration] scoring_schedule 新增 {col_name} 失败: {e}")
        except Exception as e:
            logger.warning(f"[migration] 创建/升级 scoring_schedule 失败: {e}")

        # 4) scoring_configs 表：AI 连接状态缓存列
        try:
            sc_cols = await _get_existing_columns(conn, "scoring_configs")
        except Exception:
            sc_cols = set()
        sc_additions = [
            ("ai_connection_status", "BOOLEAN"),
            ("ai_connection_provider", "VARCHAR(50)"),
            ("ai_connection_model", "VARCHAR(100)"),
            ("ai_connection_checked_at", "TIMESTAMP"),
        ]
        for col_name, col_def in sc_additions:
            if col_name in sc_cols:
                continue
            if ALLOWED_COLUMNS.get(col_name) != col_def:
                logger.warning(f"[migration] scoring_configs 新增列 {col_name} 不在白名单，跳过")
                continue
            try:
                await conn.execute(text(f"ALTER TABLE scoring_configs ADD COLUMN {col_name} {col_def}"))
                logger.info(f"[migration] scoring_configs 新增列 {col_name}")
            except Exception as e:
                logger.warning(f"[migration] scoring_configs 新增 {col_name} 失败: {e}")
