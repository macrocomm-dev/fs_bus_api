from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserLoginRequest(BaseModel):
    """Credentials submitted by a client that wants to log in."""

    email: str
    password: str


class UserLoginResponse(BaseModel):
    """Enriched login response returned after successful authentication.

    This combines Firebase-issued tokens with local application user metadata so
    clients can bootstrap a session from a single response payload.
    """

    access_token: str
    refresh_token: str
    token_type: str
    role: str
    user_id: str
    name: str | None = None
    surname: str | None = None
    expires_at: datetime | None = None


class UserRefreshResponse(UserLoginResponse):
    """Refresh response model.

    It currently reuses the same shape as ``UserLoginResponse`` so clients can
    handle login and refresh results consistently.
    """

    pass


class UserCreateRequest(BaseModel):
    """Payload for creating a new application user record."""

    full_name: str
    email: str
    password: str
    role: str
    operator_id: int | None = None
    is_active: bool = True


class UserCreateResponse(BaseModel):
    """Response returned after successfully creating a user."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    firebase_uid: str
    full_name: str
    name: str | None = None
    surname: str | None = None
    email: str
    role: str
    operator_id: int | None = None
    is_active: bool
    created_at: datetime
