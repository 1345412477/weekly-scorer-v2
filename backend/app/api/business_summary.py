"""业务盘 API - 部门工作事项汇总"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import date, timedelta
from typing import Optional
import uuid

from app.database import get_db
from app.models.models import DepartmentSummary, Department, AdminUser
from app.core.auth import require_admin, write_operation_log
from app.utils.time_utils import bj_now

router = APIRouter(prefix="/api/v1/business-dashboard", tags=["业务盘"])


def _get_week_range(target_date: Optional[date] = None) -> tuple[date, date]:
    """获取指定日期所在周的周一和周日"""
    if target_date is None:
        target_date = date.today()
    weekday = target_date.weekday()  # 0=Monday, 6=Sunday
    week_start = target_date - timedelta(days=weekday)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


@router.get("")
async def list_summaries(
    week_start: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """获取业务盘数据（所有部门当周总结）"""
    # 解析周开始日期
    if week_start:
        try:
            target_date = date.fromisoformat(week_start)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")
    else:
        target_date = date.today()
    
    ws, we = _get_week_range(target_date)
    
    # 查询所有部门的总结
    result = await db.execute(
        select(DepartmentSummary).where(
            DepartmentSummary.week_start == ws
        ).order_by(DepartmentSummary.department_name)
    )
    summaries = result.scalars().all()
    
    # 查询所有部门，补充未生成的
    dept_result = await db.execute(
        select(Department).order_by(Department.name)
    )
    departments = dept_result.scalars().all()
    
    # 构建返回数据
    summary_map = {s.department_id: s for s in summaries}
    items = []
    for dept in departments:
        summary = summary_map.get(dept.id)
        if summary:
            items.append({
                "id": summary.id,
                "department_id": summary.department_id,
                "department_name": summary.department_name,
                "week_start": summary.week_start.isoformat(),
                "week_end": summary.week_end.isoformat(),
                "last_week_summary": summary.last_week_summary or [],
                "this_week_summary": summary.this_week_summary or [],
                "is_department_highlight": summary.is_department_highlight,
                "status": summary.status,
                "error_message": summary.error_message,
                "generated_at": summary.generated_at.isoformat() if summary.generated_at else None,
            })
        else:
            items.append({
                "id": None,
                "department_id": dept.id,
                "department_name": dept.name,
                "week_start": ws.isoformat(),
                "week_end": we.isoformat(),
                "last_week_summary": [],
                "this_week_summary": [],
                "is_department_highlight": False,
                "status": "pending",
                "error_message": None,
                "generated_at": None,
            })
    
    return {
        "week_start": ws.isoformat(),
        "week_end": we.isoformat(),
        "items": items,
    }


@router.get("/{dept_id}")
async def get_summary(
    dept_id: str,
    week_start: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """获取单个部门的详细总结"""
    if week_start:
        try:
            target_date = date.fromisoformat(week_start)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误")
    else:
        target_date = date.today()
    
    ws, we = _get_week_range(target_date)
    
    result = await db.execute(
        select(DepartmentSummary).where(
            DepartmentSummary.department_id == dept_id,
            DepartmentSummary.week_start == ws,
        )
    )
    summary = result.scalar_one_or_none()
    
    if not summary:
        # 返回空结构
        dept_result = await db.execute(
            select(Department).where(Department.id == dept_id)
        )
        dept = dept_result.scalar_one_or_none()
        if not dept:
            raise HTTPException(status_code=404, detail="部门不存在")
        
        return {
            "id": None,
            "department_id": dept_id,
            "department_name": dept.name,
            "week_start": ws.isoformat(),
            "week_end": we.isoformat(),
            "last_week_summary": [],
            "this_week_summary": [],
            "is_department_highlight": False,
            "status": "pending",
            "error_message": None,
            "generated_at": None,
            "persons": [],
        }
    
    # 查询部门人员
    from app.models.models import Person
    person_result = await db.execute(
        select(Person).where(
            Person.department_id == dept_id,
            Person.is_active == True,
        ).order_by(Person.name)
    )
    persons = person_result.scalars().all()
    
    return {
        "id": summary.id,
        "department_id": summary.department_id,
        "department_name": summary.department_name,
        "week_start": summary.week_start.isoformat(),
        "week_end": summary.week_end.isoformat(),
        "last_week_summary": summary.last_week_summary or [],
        "this_week_summary": summary.this_week_summary or [],
        "is_department_highlight": summary.is_department_highlight,
        "status": summary.status,
        "error_message": summary.error_message,
        "generated_at": summary.generated_at.isoformat() if summary.generated_at else None,
        "persons": [
            {"name": p.name, "position": p.position or ""}
            for p in persons
        ],
    }


@router.post("/generate")
async def generate_all(
    week_start: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """触发所有部门的 AI 总结"""
    if week_start:
        try:
            target_date = date.fromisoformat(week_start)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误")
    else:
        target_date = date.today()
    
    ws, we = _get_week_range(target_date)
    
    # 调用服务层生成总结
    from app.services.business_summary_service import generate_all_department_summaries
    result = await generate_all_department_summaries(db, ws, we)
    
    await write_operation_log(
        db, user, "generate", "business_dashboard", "",
        detail={"week_start": ws.isoformat(), "results": result}
    )
    
    return {
        "message": "生成完成",
        "week_start": ws.isoformat(),
        "week_end": we.isoformat(),
        "results": result,
    }


@router.post("/{dept_id}/generate")
async def generate_dept(
    dept_id: str,
    week_start: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """触发单个部门的 AI 重新总结"""
    if week_start:
        try:
            target_date = date.fromisoformat(week_start)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误")
    else:
        target_date = date.today()
    
    ws, we = _get_week_range(target_date)
    
    # 验证部门存在
    dept_result = await db.execute(
        select(Department).where(Department.id == dept_id)
    )
    dept = dept_result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="部门不存在")
    
    # 调用服务层生成总结
    from app.services.business_summary_service import generate_department_summary
    result = await generate_department_summary(db, dept_id, dept.name, ws, we)
    
    await write_operation_log(
        db, user, "generate", "business_dashboard", dept_id,
        detail={"week_start": ws.isoformat(), "result": result}
    )
    
    return {
        "message": "生成完成",
        "department_id": dept_id,
        "department_name": dept.name,
        "result": result,
    }


@router.patch("/{dept_id}/highlight")
async def update_highlight(
    dept_id: str,
    req: dict,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """更新部门/事项的重点关注状态"""
    week_start = req.get("week_start")
    if week_start:
        try:
            target_date = date.fromisoformat(week_start)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误")
    else:
        target_date = date.today()
    
    ws, we = _get_week_range(target_date)
    
    # 查找或创建总结记录
    result = await db.execute(
        select(DepartmentSummary).where(
            DepartmentSummary.department_id == dept_id,
            DepartmentSummary.week_start == ws,
        )
    )
    summary = result.scalar_one_or_none()
    
    if not summary:
        # 创建空记录
        dept_result = await db.execute(
            select(Department).where(Department.id == dept_id)
        )
        dept = dept_result.scalar_one_or_none()
        if not dept:
            raise HTTPException(status_code=404, detail="部门不存在")
        
        summary = DepartmentSummary(
            id=str(uuid.uuid4()),
            department_id=dept_id,
            department_name=dept.name,
            week_start=ws,
            week_end=we,
            status="pending",
        )
        db.add(summary)
        await db.flush()
    
    # 更新重点关注状态
    highlight_type = req.get("type")  # "department" 或 "item"
    highlight_value = req.get("highlight", False)
    
    if highlight_type == "department":
        summary.is_department_highlight = highlight_value
    elif highlight_type == "item":
        item_type = req.get("item_type")  # "last_week" 或 "this_week"
        item_index = req.get("item_index")
        
        if item_type not in ["last_week", "this_week"]:
            raise HTTPException(status_code=400, detail="item_type 必须是 last_week 或 this_week")
        if item_index is None or not isinstance(item_index, int):
            raise HTTPException(status_code=400, detail="item_index 必须是整数")
        
        summary_list = summary.last_week_summary if item_type == "last_week" else summary.this_week_summary
        if summary_list is None:
            summary_list = []
        
        if item_index < 0 or item_index >= len(summary_list):
            raise HTTPException(status_code=400, detail="item_index 超出范围")
        
        summary_list[item_index]["highlight"] = highlight_value
        
        if item_type == "last_week":
            summary.last_week_summary = summary_list
        else:
            summary.this_week_summary = summary_list
    else:
        raise HTTPException(status_code=400, detail="type 必须是 department 或 item")
    
    summary.updated_at = bj_now()
    await db.commit()
    
    return {"message": "更新成功"}
