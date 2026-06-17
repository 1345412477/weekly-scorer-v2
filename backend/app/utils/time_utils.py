"""统一时间工具 - 全项目使用北京时间 (Asia/Shanghai / UTC+8)"""
from datetime import datetime, timezone, timedelta

BJ_TZ = timezone(timedelta(hours=8), "Asia/Shanghai")


def bj_now() -> datetime:
    """获取当前北京时间（无时区信息，直接存储到 SQLite DATETIME）"""
    return datetime.now(timezone.utc).astimezone(BJ_TZ).replace(tzinfo=None)


def bj_tz_now() -> datetime:
    """获取带时区信息的当前北京时间（用于明确需要时区的场景）"""
    return datetime.now(timezone.utc).astimezone(BJ_TZ)


def to_bj_naive(dt: datetime) -> datetime:
    """把任意 datetime 转换为北京时间（无时区信息）"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(BJ_TZ).replace(tzinfo=None)


def bj_today():
    """获取北京时间的 date"""
    return bj_now().date()
