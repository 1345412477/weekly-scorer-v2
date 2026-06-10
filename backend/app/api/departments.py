"""部门管理 API"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.database import get_db
from app.models.models import Department, AdminUser
from app.schemas.schemas import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from app.core.auth import require_admin, write_operation_log

router = APIRouter(prefix="/api/v1/departments", tags=["部门管理"])


@router.get("")
async def list_departments(db: AsyncSession = Depends(get_db)):
    """获取所有部门，普通用户上传页可读取"""
    result = await db.execute(select(Department).order_by(Department.created_at.desc()))
    departments = result.scalars().all()
    return [
        DepartmentResponse(
            id=d.id,
            name=d.name,
            description=d.description or "",
            created_at=d.created_at.isoformat() if d.created_at else None,
        )
        for d in departments
    ]


@router.get("/{dept_id}")
async def get_department(dept_id: str, db: AsyncSession = Depends(get_db)):
    """获取单个部门，普通用户上传页可读取"""
    result = await db.execute(select(Department).where(Department.id == dept_id))
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="部门不存在")
    return DepartmentResponse(
        id=dept.id,
        name=dept.name,
        description=dept.description or "",
        created_at=dept.created_at.isoformat() if dept.created_at else None,
    )


@router.post("")
async def create_department(
    req: DepartmentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """创建部门"""
    existing = await db.execute(select(Department).where(Department.name == req.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="部门名称已存在")

    dept = Department(id=str(uuid.uuid4()), name=req.name, description=req.description)
    db.add(dept)
    await write_operation_log(db, user, "create", "department", dept.id, request, {"name": dept.name})
    await db.commit()
    await db.refresh(dept)
    return {"message": "部门创建成功", "id": dept.id}


@router.put("/{dept_id}")
async def update_department(
    dept_id: str,
    req: DepartmentUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """更新部门"""
    result = await db.execute(select(Department).where(Department.id == dept_id))
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="部门不存在")

    if req.name is not None:
        name_check = await db.execute(select(Department).where(Department.name == req.name, Department.id != dept_id))
        if name_check.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="部门名称已存在")
        dept.name = req.name

    if req.description is not None:
        dept.description = req.description

    await write_operation_log(db, user, "update", "department", dept_id, request, {"name": dept.name})
    await db.commit()
    return {"message": "部门更新成功"}


@router.delete("/{dept_id}")
async def delete_department(
    dept_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """删除部门"""
    result = await db.execute(select(Department).where(Department.id == dept_id))
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="部门不存在")

    await db.delete(dept)
    await write_operation_log(db, user, "delete", "department", dept_id, request, {"name": dept.name})
    await db.commit()
    return {"message": "部门已删除"}
