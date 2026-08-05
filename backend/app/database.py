"""数据库配置 - 支持 SQLite 和 PostgreSQL"""
import logging
import os
import shutil
from datetime import datetime, date
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


def _ensure_sqlite_parent(url: str) -> None:
    """确保 SQLite 数据库文件所在目录存在，避免“unable to open database file”。"""
    if not url.startswith("sqlite"):
        return
    if "://" not in url:
        return
    rest = url.split("://", 1)[1]
    if rest.startswith("/"):
        rest = rest[1:]
    if rest in ("", ":memory:"):
        return
    if rest.startswith("/"):
        path = rest
    else:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.abspath(os.path.join(backend_dir, rest))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


_ensure_sqlite_parent(settings.DATABASE_URL)


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
    # 异步执行备份，不阻塞启动（数据库大时同步复制会卡住事件循环导致 502）
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, backup_database)
    except Exception as e:
        logger.warning(f"[db] 启动备份失败（不影响服务）: {e}")
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
        "submission_deadline_hours": "REAL DEFAULT 159",
        "late_deadline_hours": "REAL DEFAULT 327",
        "ai_connection_status": "BOOLEAN",
        "ai_connection_provider": "VARCHAR(50)",
        "ai_connection_model": "VARCHAR(100)",
        "ai_connection_checked_at": "TIMESTAMP",
        "raw_messages": "TEXT",
        "sensitive_words": "TEXT",
        "ocr_prompt": "TEXT",
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

        # 4) scoring_configs 表：提交期限列 + AI 连接状态缓存列
        try:
            sc_cols = await _get_existing_columns(conn, "scoring_configs")
        except Exception:
            sc_cols = set()
        sc_additions = [
            ("submission_deadline_hours", "REAL DEFAULT 159"),
            ("late_deadline_hours", "REAL DEFAULT 327"),
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

        # 5) attendance_records 列类型变更（仅 PostgreSQL 需要显式 ALTER COLUMN）
        if _IS_POSTGRES:
            try:
                at_cols = await _get_existing_columns(conn, "attendance_records")
                if "attendance_status" in at_cols:
                    # 获取当前列的数据类型
                    r = await conn.execute(text(
                        "SELECT data_type FROM information_schema.columns "
                        "WHERE table_name='attendance_records' AND column_name='attendance_status'"
                    ))
                    row = r.fetchone()
                    if row and row[0] and "character" in row[0]:
                        await conn.execute(text(
                            "ALTER TABLE attendance_records ALTER COLUMN attendance_status TYPE TEXT"
                        ))
                        logger.info("[migration] attendance_records.attendance_status 类型已改为 TEXT")
            except Exception as e:
                logger.warning(f"[migration] attendance_records 列类型变更失败: {e}")

            # 5b) scoring_configs 期限列改为 DOUBLE PRECISION（支持分钟级时间）
            try:
                deadline_cols = await _get_existing_columns(conn, "scoring_configs")
                for col_name in ("submission_deadline_hours", "late_deadline_hours"):
                    if col_name in deadline_cols:
                        r = await conn.execute(text(
                            "SELECT data_type FROM information_schema.columns "
                            "WHERE table_name='scoring_configs' AND column_name=:col"
                        ), {"col": col_name})
                        row = r.fetchone()
                        if row and row[0] and row[0].lower() in ("integer", "smallint", "bigint"):
                            await conn.execute(text(
                                f"ALTER TABLE scoring_configs ALTER COLUMN {col_name} TYPE DOUBLE PRECISION"
                            ))
                            logger.info(f"[migration] scoring_configs.{col_name} 类型已改为 DOUBLE PRECISION")
            except Exception as e:
                logger.warning(f"[migration] scoring_configs 期限列类型变更失败: {e}")

        # 6) chat_records 表：raw_messages 列
        try:
            chat_cols = await _get_existing_columns(conn, "chat_records")
        except Exception:
            chat_cols = set()
        if "raw_messages" not in chat_cols:
            try:
                await conn.execute(text("ALTER TABLE chat_records ADD COLUMN raw_messages TEXT"))
                logger.info("[migration] chat_records 新增列 raw_messages")
            except Exception as e:
                logger.warning(f"[migration] chat_records 新增 raw_messages 失败: {e}")

        # 7) scoring_configs 表：sensitive_words 列
        try:
            sc2_cols = await _get_existing_columns(conn, "scoring_configs")
        except Exception:
            sc2_cols = set()
        if "sensitive_words" not in sc2_cols:
            try:
                await conn.execute(text("ALTER TABLE scoring_configs ADD COLUMN sensitive_words TEXT"))
                logger.info("[migration] scoring_configs 新增列 sensitive_words")
            except Exception as e:
                logger.warning(f"[migration] scoring_configs 新增 sensitive_words 失败: {e}")

        # 8) scoring_configs 表：ocr_prompt 列
        try:
            sc3_cols = await _get_existing_columns(conn, "scoring_configs")
        except Exception:
            sc3_cols = set()
        if "ocr_prompt" not in sc3_cols:
            try:
                await conn.execute(text("ALTER TABLE scoring_configs ADD COLUMN ocr_prompt TEXT"))
                logger.info("[migration] scoring_configs 新增列 ocr_prompt")
            except Exception as e:
                logger.warning(f"[migration] scoring_configs 新增 ocr_prompt 失败: {e}")

        # 8b) scoring_configs 表：summary_prompt 列
        try:
            sc4_cols = await _get_existing_columns(conn, "scoring_configs")
        except Exception:
            sc4_cols = set()
        if "summary_prompt" not in sc4_cols:
            try:
                await conn.execute(text("ALTER TABLE scoring_configs ADD COLUMN summary_prompt TEXT"))
                logger.info("[migration] scoring_configs 新增列 summary_prompt")
            except Exception as e:
                logger.warning(f"[migration] scoring_configs 新增 summary_prompt 失败: {e}")

        # 9) weekly_aggregates 表：添加 author_name + week_start 唯一约束（防止重复记录）
        if _IS_SQLITE:
            try:
                idx_check = await conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name='uq_aggregate_author_week'"
                ))
                if not idx_check.scalar():
                    # SQLite 不支持直接 ADD CONSTRAINT，需要重建表
                    # 先检查是否已有重复数据，有则只保留最新的
                    await conn.execute(text("""
                        DELETE FROM weekly_aggregates WHERE id NOT IN (
                            SELECT id FROM (
                                SELECT id, ROW_NUMBER() OVER (
                                    PARTITION BY author_name, week_start
                                    ORDER BY created_at DESC
                                ) as rn
                                FROM weekly_aggregates
                            ) WHERE rn = 1
                        )
                    """))
                    logger.info("[migration] 已清理 weekly_aggregates 重复记录")
                    # SQLite 无法在线添加唯一约束，记录日志提醒
                    logger.info("[migration] SQLite 不支持在线添加唯一约束，请手动重建表或忽略")
            except Exception as e:
                logger.warning(f"[migration] weekly_aggregates 唯一约束处理失败: {e}")
        elif _IS_POSTGRES:
            try:
                idx_check = await conn.execute(text("""
                    SELECT indexname FROM pg_indexes
                    WHERE tablename = 'weekly_aggregates' AND indexname = 'uq_aggregate_author_week'
                """))
                if not idx_check.scalar():
                    await conn.execute(text("""
                        ALTER TABLE weekly_aggregates
                        ADD CONSTRAINT uq_aggregate_author_week
                        UNIQUE (author_name, week_start)
                    """))
                    logger.info("[migration] weekly_aggregates 添加唯一约束 uq_aggregate_author_week")
            except Exception as e:
                logger.warning(f"[migration] weekly_aggregates 添加唯一约束失败: {e}")
