from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserLoginResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    user_id: int
