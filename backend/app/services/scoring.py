"""评分调度服务"""
from datetime import datetime, timedelta, timezone
import time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import WeeklyReport, ReportScore, ScoringConfig
from app.services.ai_scorer import score_report, get_grade, AIScoringError
from app.utils.logger import log_scoring, log_error
from app.utils.time_utils import bj_now


async def get_active_config(db: AsyncSession) -> ScoringConfig | None:
    """获取当前激活的评分配置"""
    result = await db.execute(
        select(ScoringConfig).where(ScoringConfig.is_active == True).limit(1)
    )
    return result.scalar_one_or_none()


def normalize_dimensions(dimensions: list[dict]) -> list[dict]:
    normalized = []
    for d in dimensions:
        item = dict(d)
        if "full_score" not in item and "weight" in item:
            item["full_score"] = round(50 * float(item["weight"]) / 100, 1)
        if "evaluation_content" not in item:
            item["evaluation_content"] = item.get("description", "")
        normalized.append(item)
    return normalized


async def trigger_scoring(report_id: str, db: AsyncSession) -> dict:
    """对指定周报执行评分"""
    start_time = time.time()
    
    try:
        # 获取周报
        result = await db.execute(
            select(WeeklyReport).where(WeeklyReport.id == report_id)
        )
        report = result.scalar_one_or_none()
        if not report:
            raise ValueError("周报不存在")

        # 获取配置
        config = await get_active_config(db)
        if not config:
            raise ValueError("未配置评分规则，请先在管理页面配置")

        dimensions = normalize_dimensions(config.dimensions or [])
        if not dimensions:
            raise ValueError("评分维度为空")

        # 调用 AI 评分
        ai_result = await score_report(
            content=report.content,
            author_name=report.author_name,
            department=report.department or "",
            dimensions=dimensions,
            prompt_template=config.prompt_template or "",
            grade_thresholds=config.grade_thresholds,
        )

        # 计算等级
        total = ai_result["total_score"]
        grade = get_grade(total, config.grade_thresholds or {"优": 45, "良": 38, "一般": 33, "差": 28})

        # 保存评分结果
        score_record = ReportScore(
            report_id=report.id,
            dimension_scores=ai_result["dimension_scores"],
            total_score=total,
            grade=grade,
            ai_comment=ai_result.get("comment", ""),
            ai_suggestion=ai_result.get("suggestion", ""),
            raw_response=ai_result,
        )
        db.add(score_record)

        # 更新周报状态
        report.status = "scored"
        report.score_time = bj_now()

        await db.commit()

        # 记录评分日志
        duration_ms = (time.time() - start_time) * 1000
        log_scoring(report_id, total, grade, duration_ms)

        return {
            "report_id": report.id,
            "total_score": total,
            "grade": grade,
            "dimension_scores": ai_result["dimension_scores"],
            "ai_comment": ai_result.get("comment", ""),
            "ai_suggestion": ai_result.get("suggestion", ""),
        }
    except Exception as e:
        log_error(f"评分失败 - report_id={report_id}: {str(e)}")
        raise
