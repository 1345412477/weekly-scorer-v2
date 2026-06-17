"""日志工具模块"""
import logging
import time
import functools
from datetime import datetime
from typing import Any, Callable

from app.utils.time_utils import bj_now

logger = logging.getLogger("weekly_scorer")
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def log_performance(func: Callable) -> Callable:
    """性能监控装饰器"""
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        start_datetime = bj_now()

        try:
            result = await func(*args, **kwargs)
            duration = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"[PERF] {func.__name__} completed in {duration:.2f}ms "
                f"at {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            return result
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"[PERF] {func.__name__} failed in {duration:.2f}ms: {str(e)}"
            )
            raise

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        start_datetime = bj_now()

        try:
            result = func(*args, **kwargs)
            duration = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"[PERF] {func.__name__} completed in {duration:.2f}ms "
                f"at {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            return result
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"[PERF] {func.__name__} failed in {duration:.2f}ms: {str(e)}"
            )
            raise

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def log_api_request(endpoint: str, method: str, status_code: int, duration_ms: float):
    """记录API请求日志"""
    log_level = logging.INFO if status_code < 400 else logging.WARNING
    logger.log(
        log_level,
        f"[API] {method} {endpoint} - {status_code} - {duration_ms:.2f}ms"
    )


def log_scoring(report_id: str, total_score: float, grade: str, duration_ms: float):
    """记录评分日志"""
    logger.info(
        f"[SCORING] report_id={report_id} score={total_score} grade={grade} duration={duration_ms:.2f}ms"
    )


def log_error(message: str, exc_info: bool = False):
    """记录错误日志"""
    logger.error(f"[ERROR] {message}", exc_info=exc_info)


def log_info(message: str):
    """记录信息日志"""
    logger.info(f"[INFO] {message}")


def log_warning(message: str):
    """记录警告日志"""
    logger.warning(f"[WARN] {message}")


import asyncio