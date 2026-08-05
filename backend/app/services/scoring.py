"""评分调度服务"""
import logging
from datetime import datetime, timedelta, timezone
import time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import WeeklyReport, ReportScore, ScoringConfig
from app.services.ai_scorer import score_report, AIScoringError
from app.utils.logger import log_scoring, log_error
from app.utils.time_utils import bj_now

logger = logging.getLogger(__name__)


async def get_active_config(db: AsyncSession) -> ScoringConfig | None:
    """获取当前激活的评分配置"""
    result = await db.execute(
        select(ScoringConfig).where(ScoringConfig.is_active == True).limit(1)
    )
    return result.scalar_one_or_none()


async def trigger_scoring(report_id: str, db: AsyncSession) -> dict:
    """对指定周报执行评分（若已存在评分记录则更新而非重复创建）"""
    start_time = time.time()
    
    try:
        # 获取周报
        result = await db.execute(
            select(WeeklyReport).where(WeeklyReport.id == report_id)
        )
        report = result.scalar_one_or_none()
        if not report:
            raise ValueError("周报不存在")

        # 检查是否已存在评分记录 —— 防止重复评分
        existing_score_r = await db.execute(
            select(ReportScore).where(ReportScore.report_id == report_id).limit(1)
        )
        existing_score = existing_score_r.scalar_one_or_none()
        if existing_score:
            logger.info(f"[scoring] report_id={report_id} 已有评分（id={existing_score.id}），跳过重复评分")
            return {
                "report_id": report.id,
                "total_score": float(existing_score.total_score),
                "grade": existing_score.grade,
                "ai_comment": existing_score.ai_comment or "",
                "ai_suggestion": existing_score.ai_suggestion or "",
            }

        # 获取配置
        config = await get_active_config(db)
        if not config:
            raise ValueError("未配置评分规则，请先在管理页面配置")

        # 调用 AI 评分
        ai_result = await score_report(
            content=report.content,
            author_name=report.author_name,
            department=report.department or "",
            prompt_template=config.report_prompt or config.prompt_template or "",
            db=db,
        )

        # 按提交时间应用迟交/补交规则（方案B：周一 00:00 起算期限）
        base_total = float(ai_result["total_score"])
        total = base_total
        grade = ai_result.get("grade", "一般")
        comment = ai_result.get("comment", "")
        suggestion = ai_result.get("suggestion", "")
        dimension_scores = ai_result.get("dimension_scores", [])
        penalty_note = ""
        if report.submit_time is not None and report.week_start is not None:
            week_start_dt = datetime.combine(report.week_start, datetime.min.time())
            deadline = week_start_dt + timedelta(
                hours=float(getattr(config, "submission_deadline_hours", 159) or 159)
            )
            late_deadline = week_start_dt + timedelta(
                hours=float(getattr(config, "late_deadline_hours", 327) or 327)
            )
            submit = report.submit_time
            if submit > late_deadline:
                total = 0.0
                grade = "差"
                dimension_scores = []
                penalty_note = "补交周报，按规则计 0 分"
            elif submit > deadline:
                total = max(0.0, total - 5)
                if total < 28:
                    grade = "差"
                penalty_note = "迟交周报，扣 5 分"
        if penalty_note:
            comment = (comment + " | " if comment else "") + penalty_note

        # 保存评分结果
        score_record = ReportScore(
            report_id=report.id,
            dimension_scores=dimension_scores,
            total_score=total,
            grade=grade,
            ai_comment=comment,
            ai_suggestion=suggestion,
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
            "ai_comment": comment,
            "ai_suggestion": suggestion,
        }
    except Exception as e:
        log_error(f"评分失败 - report_id={report_id}: {str(e)}")
        raise
