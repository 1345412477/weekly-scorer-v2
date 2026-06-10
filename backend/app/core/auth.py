"""管理员认证与权限校验"""
import base64
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.database import get_db
from app.models.models import AdminUser, OperationLog

settings = get_settings()
TOKEN_EXPIRE_HOURS = 12
_runtime_auth_secret = settings.AUTH_SECRET_KEY or secrets.token_urlsafe(32)


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, expected = password_hash.split("$", 1)
    except ValueError:
        return False
    actual = hash_password(password, salt).split("$", 1)[1]
    return hmac.compare_digest(actual, expected)


def _sign(payload: str) -> str:
    secret = settings.AUTH_SECRET_KEY.encode("utf-8")
    return hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def create_admin_token(user: AdminUser) -> str:
    payload = {
        "sub": user.id,
        "username": user.username,
        "role": user.role,
        "exp": (datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)).timestamp(),
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("utf-8")
    return f"{payload_b64}.{_sign(payload_b64)}"


def decode_token(token: str) -> dict:
    try:
        payload_b64, signature = token.rsplit(".", 1)
        if not hmac.compare_digest(_sign(payload_b64), signature):
            raise ValueError("签名无效")
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")))
        if payload.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            raise ValueError("登录已过期")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=401, detail="登录状态无效，请重新登录") from exc


async def require_admin(
    authorization: str = Header("", alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="管理员功能需要登录")
    payload = decode_token(authorization.removeprefix("Bearer ").strip())
    result = await db.execute(select(AdminUser).where(AdminUser.id == payload.get("sub"), AdminUser.is_active == True))
    user = result.scalar_one_or_none()
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="没有管理员权限")
    return user


async def ensure_default_admin(db: AsyncSession):
    result = await db.execute(select(AdminUser).where(AdminUser.username == settings.ADMIN_USERNAME))
    if result.scalar_one_or_none():
        return
    admin = AdminUser(
        id=str(uuid.uuid4()),
        username=settings.ADMIN_USERNAME,
        password_hash=hash_password(settings.ADMIN_PASSWORD),
        role="admin",
        is_active=True,
    )
    db.add(admin)
    await db.commit()


async def write_operation_log(
    db: AsyncSession,
    user: AdminUser,
    action: str,
    resource: str,
    resource_id: str = "",
    request: Optional[Request] = None,
    detail: Optional[dict] = None,
):
    log = OperationLog(
        id=str(uuid.uuid4()),
        user_id=user.id,
        username=user.username,
        action=action,
        resource=resource,
        resource_id=resource_id or "",
        detail=detail or {},
        ip_address=request.client.host if request and request.client else "",
    )
    db.add(log)
