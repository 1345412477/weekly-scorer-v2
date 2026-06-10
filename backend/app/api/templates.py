"""周报模板 API"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.database import get_db
from app.models.models import ReportTemplate, AdminUser
from app.schemas.schemas import TemplateCreate, TemplateUpdate, TemplateResponse
from app.core.auth import require_admin, write_operation_log

router = APIRouter(prefix="/api/v1/templates", tags=["模板管理"])

DEFAULT_TEMPLATE_CONTENT = """## 本周工作内容

### 1. {项目名称}
- 工作内容：
- 完成情况：
- 产出/成果：

### 2. {项目名称}
- 工作内容：
- 完成情况：
- 产出/成果：

## 下周工作计划

### 1. {项目名称}
- 计划内容：
- 预期产出：

## 问题与风险
- 

## 需要协助的事项
- """

DEFAULT_FIELDS = [
    {"key": "project", "label": "项目名称", "type": "text", "required": True, "placeholder": "输入项目名称"},
    {"key": "work_content", "label": "工作内容", "type": "textarea", "required": True, "placeholder": "描述本周工作内容"},
    {"key": "completion", "label": "完成情况", "type": "textarea", "required": True, "placeholder": "说明完成进度"},
    {"key": "output", "label": "产出/成果", "type": "textarea", "required": False, "placeholder": "量化产出成果"},
]


async def ensure_default_template(db: AsyncSession):
    result = await db.execute(select(ReportTemplate).where(ReportTemplate.is_default == True).limit(1))
    if not result.scalar_one_or_none():
        default = ReportTemplate(
            id=str(uuid.uuid4()),
            name="标准周报模板",
            description="包含本周工作、下周计划、问题风险的标准模板",
            content=DEFAULT_TEMPLATE_CONTENT,
            fields=DEFAULT_FIELDS,
            is_default=True,
        )
        db.add(default)
        await db.commit()


@router.get("")
async def list_templates(db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    """获取所有模板"""
    await ensure_default_template(db)
    result = await db.execute(select(ReportTemplate).order_by(ReportTemplate.created_at.desc()))
    templates = result.scalars().all()
    return [
        TemplateResponse(
            id=t.id,
            name=t.name,
            description=t.description or "",
            content=t.content,
            fields=t.fields or [],
            is_default=t.is_default,
            created_at=t.created_at.isoformat() if t.created_at else None,
        )
        for t in templates
    ]


@router.get("/{template_id}")
async def get_template(template_id: str, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    """获取单个模板详情"""
    result = await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description or "",
        content=template.content,
        fields=template.fields or [],
        is_default=template.is_default,
        created_at=template.created_at.isoformat() if template.created_at else None,
    )


@router.post("")
async def create_template(
    req: TemplateCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """创建新模板"""
    if req.is_default:
        result = await db.execute(select(ReportTemplate).where(ReportTemplate.is_default == True))
        old_default = result.scalar_one_or_none()
        if old_default:
            old_default.is_default = False

    template = ReportTemplate(
        id=str(uuid.uuid4()),
        name=req.name,
        description=req.description,
        content=req.content,
        fields=[f.model_dump() for f in req.fields] if req.fields else [],
        is_default=req.is_default,
    )
    db.add(template)
    await write_operation_log(db, user, "create", "template", template.id, request, {"name": template.name})
    await db.commit()
    await db.refresh(template)
    return {"message": "模板创建成功", "id": template.id}


@router.put("/{template_id}")
async def update_template(
    template_id: str,
    req: TemplateUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """更新模板"""
    result = await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    if req.name is not None:
        template.name = req.name
    if req.description is not None:
        template.description = req.description
    if req.content is not None:
        template.content = req.content
    if req.fields is not None:
        template.fields = [f.model_dump() for f in req.fields]
    if req.is_default is not None:
        if req.is_default:
            result2 = await db.execute(select(ReportTemplate).where(ReportTemplate.is_default == True, ReportTemplate.id != template_id))
            old_default = result2.scalar_one_or_none()
            if old_default:
                old_default.is_default = False
        template.is_default = req.is_default

    await write_operation_log(db, user, "update", "template", template_id, request, {"name": template.name})
    await db.commit()
    return {"message": "模板更新成功"}


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """删除模板"""
    result = await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    if template.is_default:
        raise HTTPException(status_code=400, detail="不能删除默认模板")
    await db.delete(template)
    await write_operation_log(db, user, "delete", "template", template_id, request, {"name": template.name})
    await db.commit()
    return {"message": "模板已删除"}
