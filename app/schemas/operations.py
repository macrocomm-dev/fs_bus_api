from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_validator

INSPECTION_TYPES = ("Inside", "Outside", "Full", "Technical")
INSPECTION_STATUSES = ("draft", "submitted", "reviewed", "approved", "queried")


class InspectionCreate(BaseModel):
    vehicle_id: int
    route_id: int | None = None
    route_text: str | None = None
    inspection_type: Literal["Inside", "Outside", "Full", "Technical"]
    status: Literal["draft", "submitted", "reviewed", "approved", "queried"]
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    notes: str | None = None

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and not (-90 <= v <= 90):
            raise ValueError("latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and not (-180 <= v <= 180):
            raise ValueError("longitude must be between -180 and 180")
        return v


class InspectionCheckCreate(BaseModel):
    inspection_id: int
    section: str
    check_code: str
    check_label: str
    result: str
    notes: str | None = None
    display_order: int = 1
