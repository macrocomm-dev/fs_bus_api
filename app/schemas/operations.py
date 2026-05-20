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
    """Legacy inspection categories used by the operations endpoints."""

    inside = "In-Transit Monitoring"
    outside = "Physical Bus Inspection"
    full = "Full"
    technical = "Technical"


class InspectionCreate(BaseModel):
    """Multipart-friendly inspection creation payload used by older endpoints."""

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
    """Adapt multipart form fields into the ``InspectionCreate`` schema."""
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
    """Minimal error body returned by many operations endpoints."""

    detail: str


# ── POST response schemas ─────────────────────────────────────────────────────


class MessageResponse(str, Enum):
    """Common success/fail flags reused in envelope responses."""

    success = "pass"
    fail = "fail"


class InspectionCreatedResponse(BaseModel):
    """Response returned after creating a legacy inspection."""

    message: MessageResponse
    inspection_id: int
    vehicle_id: str
    route_id: str | None
    photo_id: int | None = None


class InspectionCheckCreatedResponse(BaseModel):
    """Response returned after creating one legacy inspection check."""

    message: MessageResponse
    inspection_check_id: int
    inspection_id: int


class InspectionPhotoCreatedResponse(BaseModel):
    """Response returned after creating one legacy inspection photo."""

    message: MessageResponse
    photo_id: int
    inspection_id: int


class PhotoUploadResponse(BaseModel):
    """Response returned after uploading an inspection-related image."""

    message: MessageResponse
    photo_id: int
    inspection_id: int


class PassengerCountCreatedResponse(BaseModel):
    """Response returned after creating one legacy passenger count."""

    message: MessageResponse
    count_id: int
    vehicle_id: str
    route_id: str | None


class InspectionCreate(BaseModel):
    """JSON inspection creation schema used by the legacy operations router."""

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
        """Reject latitude values outside the valid geographic range."""
        if v is not None and not (-90 <= v <= 90):
            raise ValueError("latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Decimal | None) -> Decimal | None:
        """Reject longitude values outside the valid geographic range."""
        if v is not None and not (-180 <= v <= 180):
            raise ValueError("longitude must be between -180 and 180")
        return v


class InspectionCheckCreate(BaseModel):
    """Payload for adding one checklist row to a legacy inspection."""

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
    """Minimal payload for creating a legacy inspection photo record."""

    inspection_id: int
    inspection_check_id: int | None = None


class PassengerCountCreate(BaseModel):
    """Payload for creating a legacy passenger-count row."""

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
        """Reject latitude values outside the valid geographic range."""
        if v is not None and not (-90 <= v <= 90):
            raise ValueError("latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Decimal | None) -> Decimal | None:
        """Reject longitude values outside the valid geographic range."""
        if v is not None and not (-180 <= v <= 180):
            raise ValueError("longitude must be between -180 and 180")
        return v


# ── Response schemas ──────────────────────────────────────────────────────────


class InspectionResponse(BaseModel):
    """Read model for one legacy inspection row."""

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
    """Read model for one legacy inspection-check row."""

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
    """Read model for one legacy inspection-photo row."""

    model_config = ConfigDict(from_attributes=True)

    photo_id: int
    inspection_id: int
    inspection_check_id: int | None
    content_type: str
    captured_at: datetime


class PassengerCountResponse(BaseModel):
    """Read model for one legacy passenger-count row."""

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
    """Single-inspection response wrapper."""

    message: MessageResponse
    inspection: InspectionResponse


class InspectionListEnvelope(BaseModel):
    """List response wrapper for legacy inspections."""

    message: MessageResponse
    inspections: List[InspectionResponse]


class InspectionChecksEnvelope(BaseModel):
    """List response wrapper for inspection checks."""

    message: MessageResponse
    checks: List[InspectionCheckResponse]


class InspectionPhotosEnvelope(BaseModel):
    """List response wrapper for inspection photos."""

    message: MessageResponse
    photos: List[InspectionPhotoResponse]


class PassengerCountEnvelope(BaseModel):
    """Single-passenger-count response wrapper."""

    message: MessageResponse
    passenger_count: PassengerCountResponse


# ── Master data response schemas ──────────────────────────────────────────────


class OperatorSummary(BaseModel):
    """Compact operator representation nested inside master-data responses."""

    model_config = ConfigDict(from_attributes=True)

    operator_id: int
    operator_name: str
    is_active: bool


class VehicleResponse(BaseModel):
    """API response model for master-data vehicles."""

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
    """Single-vehicle response wrapper."""

    message: MessageResponse
    vehicle: VehicleResponse


class VehicleListEnvelope(BaseModel):
    """Paginated vehicle list response wrapper."""

    message: MessageResponse
    total: int
    page: int
    page_size: int
    vehicles: List[VehicleResponse]


class RouteResponse(BaseModel):
    """API response model for master-data routes."""

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
    """Single-route response wrapper."""

    message: MessageResponse
    route: RouteResponse


class RouteListEnvelope(BaseModel):
    """Paginated route list response wrapper."""

    message: MessageResponse
    total: int
    page: int
    page_size: int
    routes: List[RouteResponse]
