"""数据库配置 - 异步 SQLite"""
import os
import shutil
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "weekly_scorer.db")
BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backups")


def backup_database():
    """备份数据库文件"""
    if not os.path.exists(DB_PATH):
        return None

    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
