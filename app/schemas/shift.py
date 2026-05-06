from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class InspectionType(str, Enum):
    external = "external"
    internal = "internal"
    count = "count"
    driver = "driver"
    technical = "technical"


# ---------------------------------------------------------------------------
# Photo / Selfie  (photos sent as base64 bytes in JSON body)
# ---------------------------------------------------------------------------


class PhotoIn(BaseModel):
    timestamp: datetime
    lat: float
    lon: float
    photo: bytes  # base64-encoded bytes


class SelfieIn(BaseModel):
    timestamp: datetime
    lat: float
    lon: float
    photo: bytes  # base64-encoded bytes


# ---------------------------------------------------------------------------
# Inspection
# ---------------------------------------------------------------------------


class InspectionIn(BaseModel):
    internal_inspection_id: str
    inspection_type: InspectionType
    inspection_time: datetime
    inspection_lat: float
    inspection_lon: float
    count: Optional[int] = 0
    pass_: bool = True
    photos: list[PhotoIn] = []
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Bus (one entry per bus inspected during the shift)
# ---------------------------------------------------------------------------


class BusIn(BaseModel):
    bus_id: str  # maps to bus_id / vin
    bus_number: str  # maps to fleet_number
    inspections: list[InspectionIn] = []


# ---------------------------------------------------------------------------
# Shift  (top-level request body)
# ---------------------------------------------------------------------------


class ShiftCreate(BaseModel):
    user_id: str
    start_time: datetime
    end_time: datetime
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    device_id: str
    selfies: list[SelfieIn] = []
    busses: list[BusIn] = []


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class MessageResponse(str, Enum):
    success = "success"
    error = "error"


class ShiftCreatedResponse(BaseModel):
    shift_id: int
    message: MessageResponse


class ShiftResponse(BaseModel):
    id: int
    user_id: str
    start_time: datetime
    end_time: datetime
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    device_id: str
    created_at: datetime

    model_config = {"from_attributes": True}
