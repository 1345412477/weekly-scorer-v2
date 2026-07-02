"""AI 模型管理 API - 支持自定义模型 ID、API Key 和 Base URL"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.database import get_db
from app.models.models import AIModel, AdminUser
from app.core.auth import require_admin, write_operation_log
from app.utils.time_utils import bj_now
from app.services.ai_scorer import _clear_db_model_cache

router = APIRouter(prefix="/api/v1/ai-models", tags=["AI 模型管理"])


def _mask_key(key: str) -> str:
    """脱敏显示 API Key"""
    if not key:
        return "(empty)"
    if len(key) <= 8:
        return key[:2] + "***"
    return key[:4] + "****" + key[-4:]


def _model_to_dict(m: AIModel, include_key: bool = False) -> dict:
    """将 AIModel 转为字典"""
    d = {
        "id": m.id,
        "name": m.name,
        "provider": m.provider,
        "model_id": m.model_id,
        "base_url": m.base_url,
        "is_active": m.is_active,
        "is_vision": m.is_vision,
        "sort_order": m.sort_order,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }
    if include_key:
        d["api_key"] = m.api_key
    else:
        d["api_key_masked"] = _mask_key(m.api_key)
    return d


@router.get("")
async def list_models(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """获取所有 AI 模型配置列表"""
    result = await db.execute(
        select(AIModel).order_by(AIModel.sort_order, AIModel.created_at)
    )
    models = result.scalars().all()
    return {
        "models": [_model_to_dict(m) for m in models],
    }


@router.get("/{model_id}")
async def get_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """获取单个 AI 模型配置（含完整 API Key）"""
    result = await db.execute(select(AIModel).where(AIModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    return _model_to_dict(model, include_key=True)


@router.post("")
async def create_model(
    req: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """新增 AI 模型配置"""
    name = req.get("name", "").strip()
    provider = req.get("provider", "").strip()
    model_id = req.get("model_id", "").strip()
    api_key = req.get("api_key", "").strip()
    base_url = req.get("base_url", "").strip()

    if not name:
        raise HTTPException(status_code=400, detail="模型名称不能为空")
    if not provider:
        raise HTTPException(status_code=400, detail="厂商标识不能为空")
    if not model_id:
        raise HTTPException(status_code=400, detail="模型 ID 不能为空")
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")
    if not base_url:
        raise HTTPException(status_code=400, detail="Base URL 不能为空")

    # 如果设为激活，先取消其他激活
    is_active = req.get("is_active", False)
    if is_active:
        result = await db.execute(select(AIModel).where(AIModel.is_active == True))
        for m in result.scalars().all():
            m.is_active = False

    model = AIModel(
        id=str(uuid.uuid4()),
        name=name,
        provider=provider,
        model_id=model_id,
        api_key=api_key,
        base_url=base_url,
        is_active=is_active,
        is_vision=req.get("is_vision", False),
        sort_order=req.get("sort_order", 0),
    )
    db.add(model)

    await write_operation_log(db, user, "create", "ai_model", model.id, request, {"name": name})
    await db.commit()
    _clear_db_model_cache()

    return _model_to_dict(model, include_key=True)


@router.put("/{model_id}")
async def update_model(
    model_id: str,
    req: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """更新 AI 模型配置"""
    result = await db.execute(select(AIModel).where(AIModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    # 如果设为激活，先取消其他激活
    is_active = req.get("is_active")
    if is_active is True:
        all_result = await db.execute(select(AIModel).where(AIModel.is_active == True))
        for m in all_result.scalars().all():
            if m.id != model_id:
                m.is_active = False

    if "name" in req:
        model.name = req["name"].strip()
    if "provider" in req:
        model.provider = req["provider"].strip()
    if "model_id" in req:
        model.model_id = req["model_id"].strip()
    if "api_key" in req:
        model.api_key = req["api_key"].strip()
    if "base_url" in req:
        model.base_url = req["base_url"].strip()
    if is_active is not None:
        model.is_active = is_active
    if "is_vision" in req:
        model.is_vision = req["is_vision"]
    if "sort_order" in req:
        model.sort_order = req["sort_order"]

    model.updated_at = bj_now()

    await write_operation_log(db, user, "update", "ai_model", model_id, request, {"name": model.name})
    await db.commit()
    _clear_db_model_cache()

    return _model_to_dict(model, include_key=True)


@router.delete("/{model_id}")
async def delete_model(
    model_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """删除 AI 模型配置"""
    result = await db.execute(select(AIModel).where(AIModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    if model.is_active:
        raise HTTPException(status_code=400, detail="不能删除当前正在使用的模型，请先切换到其他模型")

    model_name = model.name
    await db.delete(model)

    await write_operation_log(db, user, "delete", "ai_model", model_id, request, {"name": model_name})
    await db.commit()

    return {"message": "删除成功"}


@router.post("/{model_id}/activate")
async def activate_model(
    model_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """将指定模型设为当前使用模型"""
    result = await db.execute(select(AIModel).where(AIModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    # 取消所有其他激活
    all_result = await db.execute(select(AIModel).where(AIModel.is_active == True))
    for m in all_result.scalars().all():
        if m.id != model_id:
            m.is_active = False

    model.is_active = True
    model.updated_at = bj_now()

    await write_operation_log(db, user, "activate", "ai_model", model_id, request, {"name": model.name})
    await db.commit()
    _clear_db_model_cache()

    return {"message": f"已切换到 {model.name}", "model": _model_to_dict(model)}


@router.post("/test")
async def test_model_connection(
    req: dict,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """测试指定模型的连接（不保存到数据库）"""
    from openai import AsyncOpenAI
    import httpx

    api_key = req.get("api_key", "").strip()
    base_url = req.get("base_url", "").strip()
    model_id = req.get("model_id", "").strip()

    if not api_key or not base_url or not model_id:
        raise HTTPException(status_code=400, detail="api_key、base_url、model_id 均不能为空")

    timeout = httpx.Timeout(connect=10, read=30, write=30, pool=5)
    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)

    try:
        response = await client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "请回复 OK"}],
            max_tokens=10,
        )
        content = ""
        if response.choices and response.choices[0].message.content:
            content = response.choices[0].message.content
        return {"success": True, "message": "连接成功", "response": content[:50]}
    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower() or "auth" in error_msg.lower():
            user_msg = "认证失败：请检查 API Key 是否正确"
        elif "rate" in error_msg.lower() or "limit" in error_msg.lower():
            user_msg = "请求频率超限"
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            user_msg = "连接超时：请检查网络或 Base URL"
        elif "connection" in error_msg.lower() or "network" in error_msg.lower():
            user_msg = "连接失败：请检查 Base URL 是否正确"
        elif "model" in error_msg.lower() or "not found" in error_msg.lower():
            user_msg = f"模型 '{model_id}' 不可用"
        else:
            user_msg = error_msg
        return {"success": False, "message": user_msg}
