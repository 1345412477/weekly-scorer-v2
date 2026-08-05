"""评分配置 API"""
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import uuid

from app.database import get_db, backup_database, BACKUP_DIR
from app.models.models import ScoringConfig, Department, Person, WeeklyReport, AdminUser
from app.schemas.schemas import ConfigResponse, ConfigUpdate, DimensionConfig, TestScoreRequest
from app.services.ai_scorer import score_report, test_connection
from app.core.auth import require_admin, write_operation_log
from app.utils.time_utils import bj_now

router = APIRouter(prefix="/api/v1/config", tags=["配置管理"])


@router.get("")
async def get_config(db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    """获取当前评分配置（含提示词与权重）"""
    result = await db.execute(select(ScoringConfig).where(ScoringConfig.is_active == True).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        return {
            "id": None,
            "name": "默认配置",
            "prompt_template": "",
            "report_prompt": "",
            "attendance_prompt": "",
            "chat_prompt": "",
            "summary_prompt": "",
            "ocr_prompt": "",
            "weights": {"report": 1.0, "attendance": 1.0, "chat": 1.0},
            "min_content_length": 50,
        }

    weights = getattr(config, "weights", None)
    if not isinstance(weights, dict):
        weights = {"report": 1.0, "attendance": 1.0, "chat": 1.0}

    return {
        "id": config.id,
        "name": config.name,
        "prompt_template": config.prompt_template or "",
        "report_prompt": getattr(config, "report_prompt", "") or "",
        "attendance_prompt": getattr(config, "attendance_prompt", "") or "",
        "chat_prompt": getattr(config, "chat_prompt", "") or "",
        "summary_prompt": getattr(config, "summary_prompt", "") or "",
        "ocr_prompt": getattr(config, "ocr_prompt", "") or "",
        "business_summary_prompt": getattr(config, "business_summary_prompt", "") or "",
        "weights": weights,
        "min_content_length": config.min_content_length or 50,
        "submission_deadline_hours": getattr(config, "submission_deadline_hours", 159) or 159,
        "late_deadline_hours": getattr(config, "late_deadline_hours", 327) or 327,
        "sensitive_words": getattr(config, "sensitive_words", None) or [
            "脏话", "骂人", "人身攻击", "消极怠工", "推诿", "甩锅",
            "不配合", "拖延", "敷衍", "投诉", "冲突",
        ],
    }


@router.put("")
async def update_config(
    req: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """更新评分配置（支持提示词与权重）"""
    result = await db.execute(select(ScoringConfig).where(ScoringConfig.is_active == True).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        config = ScoringConfig(id=str(uuid.uuid4()), is_active=True)
        db.add(config)

    name = req.get("name")
    if name is not None:
        config.name = name

    prompt_template = req.get("prompt_template")
    if prompt_template is not None:
        config.prompt_template = prompt_template

    # v3：三项提示词
    report_prompt = req.get("report_prompt")
    if report_prompt is not None:
        config.report_prompt = report_prompt
    attendance_prompt = req.get("attendance_prompt")
    if attendance_prompt is not None:
        config.attendance_prompt = attendance_prompt
    chat_prompt = req.get("chat_prompt")
    if chat_prompt is not None:
        config.chat_prompt = chat_prompt
    ocr_prompt = req.get("ocr_prompt")
    if ocr_prompt is not None:
        config.ocr_prompt = ocr_prompt

    # v7：一周小结评分提示词
    summary_prompt = req.get("summary_prompt")
    if summary_prompt is not None:
        config.summary_prompt = summary_prompt

    # v4：业务盘提示词
    business_summary_prompt = req.get("business_summary_prompt")
    if business_summary_prompt is not None:
        config.business_summary_prompt = business_summary_prompt

    # v3：三项权重
    weights = req.get("weights")
    if weights is not None and isinstance(weights, dict):
        try:
            normalized_weights = {
                "report": float(weights.get("report", 1.0)),
                "attendance": float(weights.get("attendance", 1.0)),
                "chat": float(weights.get("chat", 1.0)),
            }
            config.weights = normalized_weights
        except Exception:
            raise HTTPException(status_code=400, detail="weights 必须是数字字典")

    min_content_length = req.get("min_content_length")
    if min_content_length is not None:
        try:
            config.min_content_length = int(min_content_length)
        except Exception:
            raise HTTPException(status_code=400, detail="min_content_length 必须是整数")

    # 提交期限设置
    submission_deadline_hours = req.get("submission_deadline_hours")
    if submission_deadline_hours is not None:
        try:
            val = float(submission_deadline_hours)
            if val <= 0:
                raise HTTPException(status_code=400, detail="迟交期限必须大于0")
            config.submission_deadline_hours = val
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="迟交期限必须是数字")

    late_deadline_hours = req.get("late_deadline_hours")
    if late_deadline_hours is not None:
        try:
            val = float(late_deadline_hours)
            if val <= 0:
                raise HTTPException(status_code=400, detail="补交期限必须大于0")
            if val <= config.submission_deadline_hours:
                raise HTTPException(status_code=400, detail="补交期限必须大于迟交期限")
            config.late_deadline_hours = val
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="补交期限必须是数字")

    # v5：敏感词列表
    sensitive_words = req.get("sensitive_words")
    if sensitive_words is not None and isinstance(sensitive_words, list):
        config.sensitive_words = sensitive_words

    config.updated_at = bj_now()

    await write_operation_log(db, user, "update", "config", config.id, request, {"name": config.name})
    await db.commit()
    return {"message": "配置保存成功"}


@router.post("/test")
async def test_score(
    req: TestScoreRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """测试评分 - 用当前配置对测试内容评分"""

    ai_result = await score_report(
        content=req.content,
        author_name="测试用户",
        department="测试部门",
        prompt_template=req.prompt_template or "",
        db=db,
    )
    return {
        "total_score": ai_result["total_score"],
        "grade": ai_result["grade"],
        "ai_comment": ai_result["comment"],
        "ai_suggestion": ai_result["suggestion"],
        "source": "ai",
    }


@router.get("/ai-status")
async def get_ai_status(
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """获取 AI 模型连接状态。

    - 默认读取缓存（30 分钟内相同 Provider/Model 不消耗 token）
    - force=true 时强制重新检测
    """
    return await test_connection(db=db, force_refresh=force)


@router.get("/data-status")
async def get_data_status(db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    """获取数据状态概览"""
    dept_count = (await db.execute(select(func.count()).select_from(Department))).scalar() or 0
    person_count = (await db.execute(select(func.count()).select_from(Person).where(Person.is_active == True))).scalar() or 0
    report_count = (await db.execute(select(func.count()).select_from(WeeklyReport))).scalar() or 0

    backups = []
    if os.path.exists(BACKUP_DIR):
        for f in sorted(os.listdir(BACKUP_DIR), reverse=True)[:5]:
            if f.endswith(".db"):
                fpath = os.path.join(BACKUP_DIR, f)
                backups.append({"filename": f, "size": os.path.getsize(fpath), "time": os.path.getmtime(fpath)})

    return {"departments": dept_count, "persons": person_count, "reports": report_count, "backups": backups}


@router.post("/backup")
async def create_backup(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """手动创建数据库备份"""
    import asyncio
    loop = asyncio.get_event_loop()
    path = await loop.run_in_executor(None, backup_database)
    if path:
        await write_operation_log(db, user, "backup", "database", "", request, {"path": os.path.basename(path)})
        await db.commit()
        return {"message": "备份成功", "path": os.path.basename(path)}
    raise HTTPException(status_code=404, detail="数据库文件不存在")
