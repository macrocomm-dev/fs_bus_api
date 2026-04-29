from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, field_validator

INSPECTION_TYPES = ("Inside", "Outside", "Full", "Technical")
INSPECTION_STATUSES = ("draft", "submitted", "reviewed", "approved", "queried")


class ErrorResponse(BaseModel):
    detail: str


# ── POST response schemas ─────────────────────────────────────────────────────


class InspectionCreatedResponse(BaseModel):
    message: str
    inspection_id: int
    vehicle_id: int
    route_id: int | None


class InspectionCheckCreatedResponse(BaseModel):
    message: str
    inspection_check_id: int
    inspection_id: int


class InspectionPhotoCreatedResponse(BaseModel):
    message: str
    photo_id: int
    inspection_id: int


class PassengerCountCreatedResponse(BaseModel):
    message: str
    count_id: int
    vehicle_id: int
    route_id: int | None


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


class InspectionPhotoCreate(BaseModel):
    inspection_id: int
    inspection_check_id: int | None = None
    storage_url: str


class PassengerCountCreate(BaseModel):
    vehicle_id: int
    route_id: int | None = None
    route_text: str | None = None
    user_id: int

    count: int
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


# ── Response schemas ──────────────────────────────────────────────────────────


class InspectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inspection_id: int
    vehicle_id: int
    route_id: int | None
    route_text: str | None
    user_id: int
    inspection_type: str
    status: str
    captured_at: datetime
    submitted_at: datetime | None
    latitude: Decimal | None
    longitude: Decimal | None
    notes: str | None


class InspectionCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inspection_check_id: int
    inspection_id: int
    section: str
    check_code: str
    check_label: str
    result: str
    notes: str | None
    display_order: int


class InspectionPhotoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    photo_id: int
    inspection_id: int
    inspection_check_id: int | None
    storage_url: str
    captured_at: datetime


class PassengerCountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    count_id: int
    vehicle_id: int
    route_id: int | None
    route_text: str | None
    user_id: int
    passenger_count: int
    captured_at: datetime
    latitude: Decimal | None
    longitude: Decimal | None
    notes: str | None


# ── Envelope (GET response wrapper) schemas ───────────────────────────────────


class InspectionEnvelope(BaseModel):
    message: str
    inspection: InspectionResponse


class InspectionListEnvelope(BaseModel):
    message: str
    inspections: List[InspectionResponse]


class InspectionChecksEnvelope(BaseModel):
    message: str
    checks: List[InspectionCheckResponse]


class InspectionPhotosEnvelope(BaseModel):
    message: str
    photos: List[InspectionPhotoResponse]


class PassengerCountEnvelope(BaseModel):
    message: str
    passenger_count: PassengerCountResponse
