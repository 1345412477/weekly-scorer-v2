"""管理员登录 API"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_admin_token, require_admin, verify_password
from app.database import get_db
from app.models.models import AdminUser
from app.schemas.schemas import LoginRequest
from app.utils.time_utils import bj_now

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdminUser).where(AdminUser.username == req.username, AdminUser.is_active == True))
    user = result.scalar_one_or_none()
    logger.info(
        "[login] username=%s, user_found=%s",
        req.username,
        user is not None,
    )
    if not user or not verify_password(req.password, user.password_hash):
        logger.warning("[login] failed username=%s", req.username)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user.last_login_at = bj_now()
    await db.commit()
    logger.info("[login] success username=%s", req.username)
    return {
        "access_token": create_admin_token(user),
        "token_type": "bearer",
        "user": {"id": user.id, "username": user.username, "role": user.role},
    }


@router.get("/me")
async def me(user: AdminUser = Depends(require_admin)):
    return {"id": user.id, "username": user.username, "role": user.role}
