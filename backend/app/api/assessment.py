"""内部考核 API - 提供考核数据查询和报告导出"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.auth import require_admin
from app.services.assessment_service import get_assessment_list, get_assessment_detail

router = APIRouter(prefix="/api/v1/assessment", tags=["内部考核"])


@router.get("/list")
async def list_assessments(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    department: Optional[str] = Query(None, description="部门筛选"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=200, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    """
    获取考核列表 - 统计指定时间范围内每个员工的平均分和提交情况
    """
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")
    
    if start > end:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
    
    result = await get_assessment_list(
        db=db,
        start_date=start,
        end_date=end,
        department=department,
        page=page,
        size=size
    )
    
    return result


@router.get("/{person_id}")
async def get_person_assessment(
    person_id: str,
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    """
    获取个人考核详情 - 包含各项平均分、每周分数、项目贡献
    """
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")
    
    if start > end:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
    
    result = await get_assessment_detail(
        db=db,
        person_id=person_id,
        start_date=start,
        end_date=end
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="未找到该员工的考核数据")
    
    return result
