"""
JWT + bcrypt + Fernet hybrid auth utilities。
- 密码 bcrypt(cost=12) + 额外 salt 防 rainbow table
- JWT HS256,access 24h / refresh 30d
- refresh token 哈希存 DB,撤销灵活
"""
from __future__ import annotations
import os
import time
import uuid
import hashlib
import secrets
import bcrypt
import jwt
from typing import Annotated, Any
from fastapi import Depends, HTTPException, Header
from pathlib import Path
from ..config import (
    JWT_ALGORITHM,
    JWT_ACCESS_TTL_SECONDS,
    JWT_REFRESH_TTL_SECONDS,
    PASSWORD_BCRYPT_ROUNDS,
    DATA_DIR,
)


def _ensure_jwt_secret() -> str:
    """首次启动自动生成 JWT 密钥,落盘 0o600。"""
    secret_file = DATA_DIR / ".jwt_secret"
    if secret_file.exists():
        return secret_file.read_text().strip()
    secret = secrets.token_urlsafe(48)
    secret_file.write_text(secret)
    os.chmod(secret_file, 0o600)
    return secret


JWT_SECRET = os.environ.get("LEGAL_JWT_SECRET") or _ensure_jwt_secret()


# ── 密码 ──────────────────────────────────────
def hash_password(plain: str) -> tuple[str, str]:
    """返回 (bcrypt_hash, salt)。"""
    salt = secrets.token_hex(16)
    h = bcrypt.hashpw((salt + plain).encode(), bcrypt.gensalt(rounds=PASSWORD_BCRYPT_ROUNDS))
    return h.decode(), salt


def verify_password(plain: str, stored_hash: str, salt: str) -> bool:
    try:
        return bcrypt.checkpw((salt + plain).encode(), stored_hash.encode())
    except Exception:
        return False


# ── JWT ───────────────────────────────────────
def _now() -> int:
    return int(time.time())


def make_access_token(user_id: int, username: str, role: str) -> tuple[str, int]:
    """返回 (token, expires_at)。"""
    exp = _now() + JWT_ACCESS_TTL_SECONDS
    payload = {
        "sub": str(user_id),
        "uname": username,
        "role": role,
        "type": "access",
        "iat": _now(),
        "exp": exp,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, exp


def make_refresh_token(user_id: int) -> tuple[str, int, str]:
    """返回 (token, expires_at, token_hash)。"""
    exp = _now() + JWT_REFRESH_TTL_SECONDS
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": _now(),
        "exp": exp,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, exp, hashlib.sha256(token.encode()).hexdigest()


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any] | None:
    """解析 + 校验,失败返回 None。"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if expected_type and payload.get("type") != expected_type:
            return None
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── 校验用户名/密码强度 ─────────────────────
def validate_username(username: str) -> str | None:
    if not username or len(username) < 3:
        return "用户名至少 3 个字符"
    if len(username) > 32:
        return "用户名不能超过 32 个字符"
    if not all(c.isalnum() or c in "._-" for c in username):
        return "用户名只允许字母/数字/._-"
    return None


def validate_password(password: str) -> str | None:
    if not password or len(password) < 8:
        return "密码至少 8 个字符"
    if len(password) > 128:
        return "密码不能超过 128 个字符"
    if password.isdigit() or password.isalpha():
        return "密码不能全为数字或字母"
    return None


# ── FastAPI 依赖注入 ──────────────────────────
async def get_current_user(authorization: str | None = Header(None)) -> dict:
    """FastAPI Depends: 从 Authorization header 解析 JWT → 返回 user dict。
    未认证或 token 无效时抛出 401。
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization[7:]
    payload = decode_token(token, expected_type="access")
    if not payload:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    # 动态导入避免 circular import
    from app.services.user_service import get_by_id
    user = get_by_id(int(payload["sub"]))
    if not user or not user.get("is_active", False):
        raise HTTPException(status_code=401, detail="用户不存在或已停用")
    return user