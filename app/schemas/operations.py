from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator

INSPECTION_TYPES = ("Inside", "Outside", "Full", "Technical")
INSPECTION_STATUSES = ("draft", "submitted", "reviewed", "approved", "queried")


from fastapi import Form


class Inspectiontype(str, Enum):
    inside = "In-Transit Monitoring"
    outside = "Physical Bus Inspection"
    full = "Full"
    technical = "Technical"


class InspectionCreate(BaseModel):
    vehicle_id: str
    user_id: int
    inspection_type: Inspectiontype
    status: str
    route_id: Optional[str] = None
    route_text: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None
    date_of_inspection: Optional[datetime] = None
    device_id: Optional[str] = None


def inspection_create_form(
    vehicle_id: str = Form(...),
    user_id: int = Form(...),
    inspection_type: str = Form(...),
    status: str = Form(...),
    route_id: str | None = Form(None),
    route_text: str | None = Form(None),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    notes: str | None = Form(None),
    date_of_inspection: datetime | None = Form(None),
    device_id: str | None = Form(None),
) -> InspectionCreate:
    return InspectionCreate(
        vehicle_id=vehicle_id,
        user_id=user_id,
        inspection_type=inspection_type,
        status=status,
        route_id=route_id,
        route_text=route_text,
        latitude=latitude,
        longitude=longitude,
        notes=notes,
        date_of_inspection=date_of_inspection,
        device_id=device_id,
    )


class ErrorResponse(BaseModel):
    detail: str


# ── POST response schemas ─────────────────────────────────────────────────────


class MessageResponse(str, Enum):
    success = "pass"
    fail = "fail"


class InspectionCreatedResponse(BaseModel):
    message: MessageResponse
    inspection_id: int
    vehicle_id: str
    route_id: str | None
    photo_id: int | None = None


class InspectionCheckCreatedResponse(BaseModel):
    message: MessageResponse
    inspection_check_id: int
    inspection_id: int


class InspectionPhotoCreatedResponse(BaseModel):
    message: MessageResponse
    photo_id: int
    inspection_id: int


class PhotoUploadResponse(BaseModel):
    message: MessageResponse
    photo_id: int
    inspection_id: int


class PassengerCountCreatedResponse(BaseModel):
    message: MessageResponse
    count_id: int
    vehicle_id: str
    route_id: str | None


class InspectionCreate(BaseModel):
    vehicle_id: str
    route_id: str | None = None
    route_text: str | None = None
    inspection_type: Literal["Inside", "Outside", "Full", "Technical"]
    status: Literal["draft", "submitted", "reviewed", "approved", "queried"]
    device_id: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    user_id: int
    date_of_inspection: datetime | None = None
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
    section: Literal["Inside", "Outside"]
    check_code: str
    check_label: str
    result: Literal["pass", "fail"]
    notes: str | None = None
    display_order: int = 1
    date_of_inspectioncheck: datetime | None = None
    user_id: int


class InspectionPhotoCreate(BaseModel):
    inspection_id: int
    inspection_check_id: int | None = None


class PassengerCountCreate(BaseModel):
    vehicle_id: str
    route_id: str | None = None
    route_text: str | None = None
    device_id: str | None = None
    user_id: int
    date_of_passenger_count: datetime | None = None
    count: int = Field(..., ge=0)
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
    vehicle_id: str
    route_id: str | None
    route_text: str | None
    device_id: str | None
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
    content_type: str
    captured_at: datetime


class PassengerCountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    count_id: int
    vehicle_id: str
    route_id: str | None
    device_id: str | None
    route_text: str | None
    user_id: int
    passenger_count: int
    captured_at: datetime
    latitude: Decimal | None
    longitude: Decimal | None
    notes: str | None


# ── Envelope (GET response wrapper) schemas ───────────────────────────────────


class InspectionEnvelope(BaseModel):
    message: MessageResponse
    inspection: InspectionResponse


class InspectionListEnvelope(BaseModel):
    message: MessageResponse
    inspections: List[InspectionResponse]


class InspectionChecksEnvelope(BaseModel):
    message: MessageResponse
    checks: List[InspectionCheckResponse]


class InspectionPhotosEnvelope(BaseModel):
    message: MessageResponse
    photos: List[InspectionPhotoResponse]


class PassengerCountEnvelope(BaseModel):
    message: MessageResponse
    passenger_count: PassengerCountResponse


# ── Master data response schemas ──────────────────────────────────────────────


class OperatorSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    operator_id: int
    operator_name: str
    is_active: bool


class VehicleResponse(BaseModel):
    vehicle_id: int
    vin: str
    registration_number: str | None
    fleet_number: str | None
    operator_id: int | None
    operator_name: str | None
    # operator: OperatorSummary | None
    make: str | None
    year: str | None
    engine_number: str | None
    gvm: int | None
    tare: int | None
    chassis_no: str | None
    date_of_1st_reg: datetime | None
    is_active: bool
    created_at: datetime


class VehicleEnvelope(BaseModel):
    message: MessageResponse
    vehicle: VehicleResponse


class VehicleListEnvelope(BaseModel):
    message: MessageResponse
    total: int
    page: int
    page_size: int
    vehicles: List[VehicleResponse]


class RouteResponse(BaseModel):
    route_id: int
    route_code: str
    route_name: str | None
    operator_id: int | None
    operator_name: str | None
    operator: OperatorSummary | None
    description: str | None
    is_active: bool
    created_at: datetime


class RouteEnvelope(BaseModel):
    message: MessageResponse
    route: RouteResponse


class RouteListEnvelope(BaseModel):
    message: MessageResponse
    total: int
    page: int
    page_size: int
    routes: List[RouteResponse]
