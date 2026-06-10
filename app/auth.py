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
    """Check whether a plain-text password matches a stored hash."""
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    """Hash a plain-text password before saving it to storage."""
    return pwd_context.hash(plain)


# ---------------------------------------------------------------------------
# Token models
# ---------------------------------------------------------------------------


class Token(BaseModel):
    """Simple bearer-token response model used by auth-style endpoints."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Normalized identity information extracted from an incoming bearer token.

    This is the object route handlers receive after authentication succeeds.
    It intentionally contains only the user details the API needs for access
    control and auditing.
    """

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
    """Return the shared Firebase Admin app instance.

    Firebase Admin only needs to be initialized once per process. Caching the
    result avoids repeated setup work and prevents duplicate-app errors.
    """
    try:
        return get_app()
    except ValueError:
        return initialize_app(options={"projectId": project_id})


def create_access_token(
    data: dict,
    settings: Settings,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT using the app's own secret key.

    Most current auth flows use Firebase tokens, but this helper remains useful
    for internal tokens and for keeping the auth module self-contained.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def normalize_role(role: str | None) -> str | None:
    """Convert role input into the API's canonical role names.

    Normalization lets the rest of the code compare roles reliably without
    caring whether the incoming value was upper-case, lower-case, or mixed.
    """
    if role is None:
        return None
    return {
        "monitor": "Monitor",
        "supervisor": "Supervisor",
        "admin": "Admin",
        "technical manager": "Technical Manager",
        "office administrator": "Office Administrator",
        "procurement and secretariat": "Procurement and Secretariat",
        "project administrator": "Project Administrator",
        "project manager": "Project Manager",
    }.get(role.strip().lower())


def expand_role_permissions(role: str | None) -> tuple[str, ...]:
    """Expand one role into every permission level it should inherit.

    For example, an Admin is also allowed to do Supervisor and Monitor work, so
    this helper returns the full set of effective permissions.
    """
    normalized_role = normalize_role(role)
    if normalized_role is None:
        return ()
    return ROLE_HIERARCHY[normalized_role.lower()]


def split_user_name(full_name: str | None) -> tuple[str | None, str | None]:
    """Split a display name into first-name and surname-style parts.

    This is a pragmatic formatter for APIs that store ``name`` and ``surname``
    separately even when the identity provider gives the application a single
    full display name string.
    """
    if full_name is None:
        return None, None

    parts = [part for part in full_name.strip().split() if part]
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


def require_role(required_role: str):
    """Build a FastAPI dependency that enforces a minimum application role.

    The returned dependency can be plugged directly into a route. It reads the
    already-authenticated ``TokenData`` object and rejects users whose role does
    not include the required permission level.
    """
    normalized_required_role = normalize_role(required_role)
    if normalized_required_role is None:
        raise ValueError(f"Unsupported role: {required_role}")

    def role_dependency(
        current_user: Annotated[TokenData, Depends(get_current_user)],
    ) -> TokenData:
        """Validate the current user against the role requirement."""
        if normalized_required_role not in expand_role_permissions(current_user.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_dependency


def decode_access_token(token: str, settings: Settings) -> TokenData:
    """Validate an incoming Firebase ID token and map it into ``TokenData``.

    The Firebase Admin SDK does the heavy lifting here: signature validation,
    expiration checks, optional revocation checks, and clock skew handling.
    This function converts the provider-specific payload into the smaller shape
    the rest of the API consumes.
    """
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
    except (
        Exception
    ) as exc:  # noqa: BLE001 - provider libraries raise varied auth errors
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
    """FastAPI dependency that authenticates the request bearer token.

    Route handlers use this dependency instead of manually reading headers.
    That keeps authentication logic centralized and makes routes easier to
    read, test, and secure consistently.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(credentials.credentials, settings)
