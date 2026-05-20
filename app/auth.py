"""
OAuth2 / OIDC authentication helpers for FS Bus API.

The API accepts Bearer tokens and validates provider-issued identity tokens.
Firebase Authentication is the current identity provider direction.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from firebase_admin import get_app, initialize_app
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.config import Settings, get_settings

# ---------------------------------------------------------------------------
# Scheme
# ---------------------------------------------------------------------------

bearer_scheme = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


# ---------------------------------------------------------------------------
# Token models
# ---------------------------------------------------------------------------

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    sub: str
    name: str | None = None
    email: str | None = None
    role: str | None = None


ROLE_HIERARCHY: dict[str, tuple[str, ...]] = {
    "monitor": ("Monitor",),
    "supervisor": ("Monitor", "Supervisor"),
    "admin": ("Monitor", "Supervisor", "Admin"),
}


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


@lru_cache
def get_firebase_app(project_id: str):
    try:
        return get_app()
    except ValueError:
        return initialize_app(options={"projectId": project_id})


def create_access_token(
    data: dict,
    settings: Settings,
    expires_delta: timedelta | None = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def normalize_role(role: str | None) -> str | None:
    if role is None:
        return None
    return {
        "monitor": "Monitor",
        "supervisor": "Supervisor",
        "admin": "Admin",
    }.get(role.strip().lower())


def expand_role_permissions(role: str | None) -> tuple[str, ...]:
    normalized_role = normalize_role(role)
    if normalized_role is None:
        return ()
    return ROLE_HIERARCHY[normalized_role.lower()]


def split_user_name(full_name: str | None) -> tuple[str | None, str | None]:
    if full_name is None:
        return None, None

    parts = [part for part in full_name.strip().split() if part]
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


def require_role(required_role: str):
    normalized_required_role = normalize_role(required_role)
    if normalized_required_role is None:
        raise ValueError(f"Unsupported role: {required_role}")

    def role_dependency(
        current_user: Annotated[TokenData, Depends(get_current_user)],
    ) -> TokenData:
        if normalized_required_role not in expand_role_permissions(current_user.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_dependency


def decode_access_token(token: str, settings: Settings) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = firebase_auth.verify_id_token(
            token,
            app=get_firebase_app(settings.firebase_project_id),
            check_revoked=settings.firebase_check_revoked,
            clock_skew_seconds=settings.firebase_clock_skew_seconds,
        )
        sub: str | None = payload.get("uid") or payload.get("sub")
        if sub is None:
            raise credentials_exception
        return TokenData(
            sub=sub,
            name=payload.get("name"),
            email=payload.get("email"),
            role=payload.get("role"),
        )
    except Exception as exc:  # noqa: BLE001 - provider libraries raise varied auth errors
        raise credentials_exception from exc


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenData:
    """Dependency that validates the Bearer token and returns the token data."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(credentials.credentials, settings)
