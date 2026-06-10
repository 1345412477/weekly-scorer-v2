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

router = APIRouter(prefix="/api/v1/config", tags=["配置管理"])

DEFAULT_DIMENSIONS = [
    {"name": "工作反馈深度", "full_score": 14, "evaluation_content": "问题发现+分析+解决方案"},
    {"name": "进度节点明确", "full_score": 13, "evaluation_content": "项目是否有明确进度/节点"},
    {"name": "计划可行性", "full_score": 10, "evaluation_content": "下周计划是否具体可执行"},
    {"name": "工作连续性", "full_score": 13, "evaluation_content": "是否承接上周计划且有闭环"},
]


@router.get("", response_model=ConfigResponse)
async def get_config(db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    """获取当前评分配置"""
    result = await db.execute(select(ScoringConfig).where(ScoringConfig.is_active == True).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        return ConfigResponse(
            dimensions=[DimensionConfig(**d) for d in DEFAULT_DIMENSIONS],
            grade_thresholds={"优": 45, "良": 38, "一般": 33, "差": 28},
        )

    dims = config.dimensions or DEFAULT_DIMENSIONS
    converted_dims = []
    for d in dims:
        if "full_score" not in d and "weight" in d:
            converted_dims.append({
                "name": d["name"],
                "full_score": round(50 * d["weight"] / 100, 1),
                "highest_score": d.get("highest_score"),
                "lowest_score": d.get("lowest_score"),
                "evaluation_content": d.get("description", d.get("evaluation_content", "")),
            })
        else:
            converted_dims.append(d)

    return ConfigResponse(
        id=config.id,
        name=config.name,
        dimensions=[DimensionConfig(**d) for d in converted_dims],
        grade_thresholds=config.grade_thresholds or {"优": 45, "良": 38, "一般": 33, "差": 28},
        prompt_template=config.prompt_template or "",
        min_content_length=config.min_content_length or 50,
    )


@router.put("")
async def update_config(
    req: ConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """更新评分配置"""
    result = await db.execute(select(ScoringConfig).where(ScoringConfig.is_active == True).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        config = ScoringConfig(id=str(uuid.uuid4()), is_active=True)
        db.add(config)

    if req.name is not None:
        config.name = req.name
    if req.dimensions is not None:
        for d in req.dimensions:
            if d.full_score <= 0:
                raise HTTPException(status_code=400, detail=f"维度 '{d.name}' 的满分必须大于0")
            if d.highest_score is not None and d.highest_score > d.full_score:
                raise HTTPException(status_code=400, detail=f"维度 '{d.name}' 的最高分不能超过满分")
            if d.lowest_score is not None and d.lowest_score > d.full_score:
                raise HTTPException(status_code=400, detail=f"维度 '{d.name}' 的最低分不能超过满分")
            if d.highest_score is not None and d.lowest_score is not None and d.lowest_score > d.highest_score:
                raise HTTPException(status_code=400, detail=f"维度 '{d.name}' 的最低分不能超过最高分")
        config.dimensions = [d.model_dump() for d in req.dimensions]
    if req.grade_thresholds is not None:
        config.grade_thresholds = req.grade_thresholds
    if req.prompt_template is not None:
        config.prompt_template = req.prompt_template
    if req.min_content_length is not None:
        config.min_content_length = req.min_content_length

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
    if req.dimensions:
        dimensions = [d.model_dump() for d in req.dimensions]
    else:
        result = await db.execute(select(ScoringConfig).where(ScoringConfig.is_active == True).limit(1))
        config = result.scalar_one_or_none()
        dimensions = config.dimensions if config and config.dimensions else DEFAULT_DIMENSIONS

    ai_result = await score_report(
        content=req.content,
        author_name="测试用户",
        department="测试部门",
        dimensions=dimensions,
        prompt_template=req.prompt_template or "",
    )
    return {
        "dimension_scores": ai_result["dimension_scores"],
        "total_score": ai_result["total_score"],
        "grade": ai_result["grade"],
        "ai_comment": ai_result["comment"],
        "ai_suggestion": ai_result["suggestion"],
        "source": "ai",
    }


@router.get("/ai-status")
async def get_ai_status(user: AdminUser = Depends(require_admin)):
    """获取 AI 模型连接状态"""
    return await test_connection()


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
    path = backup_database()
    if path:
        await write_operation_log(db, user, "backup", "database", "", request, {"path": os.path.basename(path)})
        await db.commit()
        return {"message": "备份成功", "path": os.path.basename(path)}
    raise HTTPException(status_code=404, detail="数据库文件不存在")
