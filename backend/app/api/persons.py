"""人员管理 API"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.database import get_db
from app.models.models import Person, AdminUser
from app.schemas.schemas import PersonCreate, PersonUpdate, PersonResponse
from app.core.auth import require_admin, write_operation_log

router = APIRouter(prefix="/api/v1/persons", tags=["人员管理"])


@router.get("")
async def list_persons(department_id: str = None, db: AsyncSession = Depends(get_db)):
    """获取所有人员，普通用户上传页可读取"""
    query = select(Person).where(Person.is_active == True)
    if department_id:
        query = query.where(Person.department_id == department_id)
    query = query.order_by(Person.created_at.desc())

    result = await db.execute(query)
    persons = result.scalars().all()
    return [
        PersonResponse(
            id=p.id,
            name=p.name,
            department_id=p.department_id,
            department_name=p.department_name or "",
            position=p.position or "",
            email=p.email or "",
            is_active=p.is_active,
            created_at=p.created_at.isoformat() if p.created_at else None,
        )
        for p in persons
    ]


@router.get("/{person_id}")
async def get_person(person_id: str, db: AsyncSession = Depends(get_db)):
    """获取单个人员，普通用户上传页可读取"""
    result = await db.execute(select(Person).where(Person.id == person_id, Person.is_active == True))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="人员不存在")
    return PersonResponse(
        id=person.id,
        name=person.name,
        department_id=person.department_id,
        department_name=person.department_name or "",
        position=person.position or "",
        email=person.email or "",
        is_active=person.is_active,
        created_at=person.created_at.isoformat() if person.created_at else None,
    )


@router.post("")
async def create_person(
    req: PersonCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """创建人员"""
    person = Person(
        id=str(uuid.uuid4()),
        name=req.name,
        department_id=req.department_id,
        department_name=req.department_name or "",
        position=req.position or "",
        email=req.email or "",
    )
    db.add(person)
    await write_operation_log(db, user, "create", "person", person.id, request, {"name": person.name})
    await db.commit()
    await db.refresh(person)
    return {"message": "人员创建成功", "id": person.id}


@router.put("/{person_id}")
async def update_person(
    person_id: str,
    req: PersonUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """更新人员"""
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="人员不存在")

    if req.name is not None:
        person.name = req.name
    if req.department_id is not None:
        person.department_id = req.department_id
    if req.department_name is not None:
        person.department_name = req.department_name
    if req.position is not None:
        person.position = req.position
    if req.email is not None:
        person.email = req.email
    if req.is_active is not None:
        person.is_active = req.is_active

    await write_operation_log(db, user, "update", "person", person_id, request, {"name": person.name})
    await db.commit()
    return {"message": "人员更新成功"}


@router.delete("/{person_id}")
async def delete_person(
    person_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """删除人员（软删除）"""
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="人员不存在")

    person.is_active = False
    await write_operation_log(db, user, "delete", "person", person_id, request, {"name": person.name})
    await db.commit()
    return {"message": "人员已删除"}
