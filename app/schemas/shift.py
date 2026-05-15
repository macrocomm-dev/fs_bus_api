from datetime import datetime
from enum import Enum
from typing import List, Optional
from fastapi.params import Query
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str


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
    inspection_item: str
    photo: str  # base64-encoded image string


class SelfieIn(BaseModel):
    timestamp: datetime
    lat: float
    lon: float
    photo: str  # base64-encoded image string


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
    notes: Optional[str] = None
    # Exterior inspection
    tyres_pass: Optional[bool] = None
    tyres_notes: Optional[str] = None
    windows_pass: Optional[bool] = None
    windows_notes: Optional[str] = None
    ext_other_pass: Optional[bool] = None
    ext_other_notes: Optional[str] = None
    # Interior inspection
    seats_pass: Optional[bool] = None
    seats_notes: Optional[str] = None
    aisle_pass: Optional[bool] = None
    aisle_notes: Optional[str] = None
    int_other_pass: Optional[bool] = None
    int_other_notes: Optional[str] = None
    # Passenger count
    number_seated: Optional[int] = None
    number_standing: Optional[int] = None
    # Behind schedule
    behind_schedule_interval: Optional[str] = None
    photos: list[PhotoIn]

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Bus (one entry per bus inspected during the shift)
# ---------------------------------------------------------------------------


class BusIn(BaseModel):
    bus_id: str  # maps to bus_id / vin
    bus_number: str  # maps to fleet_number
    # Bus / driver identification
    license_disk_scan_succeeded: Optional[bool] = None
    destination_displayed: Optional[bool] = None
    prdp_scan_succeeded: Optional[bool] = None
    prdp_expiry_date: Optional[datetime] = None
    driver_identified: Optional[bool] = None
    driver_fail_reason: Optional[str] = None
    driver: Optional[str] = None
    inspections: list[InspectionIn]


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
    selfies: list[SelfieIn]
    busses: list[BusIn]

    # model_config = {
    #     "json_schema_extra": {
    #         "example": {
    #             "user_id": "firebase_uid_abc123",
    #             "start_time": "2026-05-06T08:00:00",
    #             "end_time": "2026-05-06T16:00:00",
    #             "start_lat": -26.2041,
    #             "start_lon": 28.0473,
    #             "end_lat": -26.2041,
    #             "end_lon": 28.0473,
    #             "device_id": "device_xyz",
    #             "selfies": [
    #                 {
    #                     "timestamp": "2026-05-06T08:05:00",
    #                     "lat": -26.2041,
    #                     "lon": 28.0473,
    #                     "photo": "<base64-encoded-image-string>",
    #                 }
    #             ],
    #             "busses": [
    #                 {
    #                     "bus_id": "WVWZZZ1KZ8W123456",
    #                     "bus_number": "BUS-001",
    #                     "inspections": [
    #                         {
    #                             "internal_inspection_id": "INSP-001",
    #                             "inspection_type": "external",
    #                             "inspection_time": "2026-05-06T08:10:00",
    #                             "inspection_lat": -26.2041,
    #                             "inspection_lon": 28.0473,
    #                             "count": 0,
    #                             "pass_": True,
    #                             "notes": "All clear",
    #                             "photos": [
    #                                 {
    #                                     "timestamp": "2026-05-06T08:10:05",
    #                                     "lat": -26.2041,
    #                                     "lon": 28.0473,
    #                                     "photo": "<base64-encoded-image-string>",
    #                                 }
    #                             ],
    #                         }
    #                     ],
    #                 }
    #             ],
    #         }
    #     }
    # }


# ---------------------------------------------------------------------------
# Multipart variants — no photo field; files sent as separate form fields
#
# File naming convention for multipart/form-data:
#   selfie_{i}                          e.g. selfie_0, selfie_1
#   bus_{i}_inspection_{j}_photo_{k}    e.g. bus_0_inspection_0_photo_0
# ---------------------------------------------------------------------------


class PhotoMetaIn(BaseModel):
    timestamp: datetime
    lat: float
    lon: float
    inspection_item: str


class SelfieMetaIn(BaseModel):
    timestamp: datetime
    lat: float
    lon: float


class InspectionMetaIn(BaseModel):
    internal_inspection_id: str
    inspection_type: InspectionType
    inspection_time: datetime
    inspection_lat: float
    inspection_lon: float
    count: Optional[int] = 0
    pass_: bool = True
    notes: Optional[str] = None
    # Exterior inspection
    tyres_pass: Optional[bool] = None
    tyres_notes: Optional[str] = None
    windows_pass: Optional[bool] = None
    windows_notes: Optional[str] = None
    ext_other_pass: Optional[bool] = None
    ext_other_notes: Optional[str] = None
    # Interior inspection
    seats_pass: Optional[bool] = None
    seats_notes: Optional[str] = None
    aisle_pass: Optional[bool] = None
    aisle_notes: Optional[str] = None
    int_other_pass: Optional[bool] = None
    int_other_notes: Optional[str] = None
    # Passenger count
    number_seated: Optional[int] = None
    number_standing: Optional[int] = None
    # Behind schedule
    behind_schedule_interval: Optional[str] = None
    photos: list[PhotoMetaIn] = []

    model_config = {"populate_by_name": True}


class BusMetaIn(BaseModel):
    bus_id: str
    bus_number: str
    # Bus / driver identification
    license_disk_scan_succeeded: Optional[bool] = None
    destination_displayed: Optional[bool] = None
    prdp_scan_succeeded: Optional[bool] = None
    prdp_expiry_date: Optional[datetime] = None
    driver_identified: Optional[bool] = None
    driver_fail_reason: Optional[str] = None
    driver: Optional[str] = None
    inspections: list[InspectionMetaIn] = []


class ShiftCreateMeta(BaseModel):
    """Used with multipart/form-data. Send this as a JSON string in the `data` Form field."""

    user_id: str
    start_time: datetime
    end_time: datetime
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    device_id: str
    selfies: list[SelfieMetaIn] = []
    busses: list[BusMetaIn] = []


class MessageResponse(str, Enum):
    success = "success"
    error = "error"


class ShiftCreatedResponse(BaseModel):
    status: int
    message: MessageResponse


class ShiftResponse(BaseModel):
    id: int
    start_time: datetime
    end_time: datetime
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    device_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SelfieResponse(BaseModel):
    id: int
    shift_id: int
    timestamp: datetime
    lat: float
    lon: float
    photo: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PhotoResponse(BaseModel):
    id: int
    inspection_id: int
    timestamp: datetime
    lat: float
    lon: float
    inspection_item: str
    photo: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BusInspectionResponse(BaseModel):
    id: int
    shift_id: int
    user_id: str
    bus_id: str
    fleet_number: str
    internal_inspection_id: str
    inspection_type: str
    inspection_time: datetime
    inspection_lat: float
    inspection_lon: float
    count: Optional[int] = 0
    pass_: Optional[bool] = True
    notes: Optional[str] = None
    tyres_pass: Optional[bool] = None
    tyres_notes: Optional[str] = None
    windows_pass: Optional[bool] = None
    windows_notes: Optional[str] = None
    ext_other_pass: Optional[bool] = None
    ext_other_notes: Optional[str] = None
    seats_pass: Optional[bool] = None
    seats_notes: Optional[str] = None
    aisle_pass: Optional[bool] = None
    aisle_notes: Optional[str] = None
    int_other_pass: Optional[bool] = None
    int_other_notes: Optional[str] = None
    number_seated: Optional[int] = None
    number_standing: Optional[int] = None
    behind_schedule_interval: Optional[str] = None
    license_disk_scan_succeeded: Optional[bool] = None
    destination_displayed: Optional[bool] = None
    prdp_scan_succeeded: Optional[bool] = None
    prdp_expiry_date: Optional[datetime] = None
    driver_identified: Optional[bool] = None
    driver_fail_reason: Optional[str] = None
    driver: Optional[str] = None

    model_config = {"from_attributes": True}


class DateRangeLimitQueryParams:
    def __init__(
        self,
        daterange: Optional[str] = Query(
            None,
            description="Date range filter in the format 'YYYY-MM-DD,YYYY-MM-DD'",
            example="2026-05-01,2026-05-15",
        ),
        limit: Optional[int] = Query(
            None,
            description="Maximum number of records to return",
            example=100,
        ),
    ):
        self.daterange = daterange
        self.limit = limit
