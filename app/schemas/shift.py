from datetime import date, datetime, time
from enum import Enum
from typing import List, Optional
from fastapi import Query
from pydantic import BaseModel, Field, field_validator, model_validator


def _has_any_item_photos(*items) -> bool:
    """Return true when at least one checklist item carries one photo."""
    return any(item.photos for item in items)


class ErrorResponse(BaseModel):
    """Minimal error response used by shift-related endpoints."""

    detail: str


class InspectionType(str, Enum):
    """Flat inspection row types stored in the shift inspection table."""

    external = "external"
    internal = "internal"
    count = "count"
    driver = "driver"
    behind_schedule = "behind_schedule"
    technical = "technical"


class BehindScheduleInterval(str, Enum):
    """Allowed labels for behind-schedule reports."""

    zero_to_five = "0-5 mins"
    five_to_ten = "5-10 mins"
    ten_to_fifteen = "10-15 mins"
    fifteen_plus = "15+ mins"


# ---------------------------------------------------------------------------
# Photo / Selfie  (photos sent as base64 bytes in JSON body)
# ---------------------------------------------------------------------------


class PhotoIn(BaseModel):
    """Base64 photo payload supplied inline inside JSON requests."""

    timestamp: datetime
    lat: float
    lon: float
    photo: str  # base64-encoded image string


class SelfieIn(PhotoIn):
    """Inline selfie payload captured as part of a shift."""

    pass


class InspectionItemPhotoIn(BaseModel):
    """Inline image attached to one checklist item inside an inspection."""

    timestamp: datetime
    lat: float
    lon: float
    photo: str  # base64-encoded image string


class InspectionItemIn(BaseModel):
    """Pass/fail result, optional reason, and optional photos for one item."""

    pass_: bool = False
    reason: Optional[str] = None
    photos: list[InspectionItemPhotoIn] = []


class InspectionBaseIn(BaseModel):
    """Fields common to every nested inspection event sent by the client."""

    internal_inspection_id: str
    inspection_time: datetime
    inspection_lat: float
    inspection_lon: float


class ExteriorInspectionIn(InspectionBaseIn):
    """Nested request model for one external bus inspection."""

    tyres: InspectionItemIn
    windows: InspectionItemIn
    other: InspectionItemIn


class InteriorInspectionIn(InspectionBaseIn):
    """Nested request model for one internal bus inspection."""

    fire_extinguisher_present: bool = False
    seats: InspectionItemIn
    aisle: InspectionItemIn
    other: InspectionItemIn


class DriverInspectionIn(InspectionBaseIn):
    """Nested request model for one driver inspection event."""

    prdp_scan_succeeded: Optional[bool] = None
    prdp_expiry_date: Optional[datetime] = None
    driver_identified: Optional[bool] = None
    driver_fail_reason: Optional[str] = None
    driver_name: Optional[str] = None
    photos: list[InspectionItemPhotoIn] = []

    @field_validator("prdp_expiry_date", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "":
            return None
        return v


class PassengerCountIn(InspectionBaseIn):
    """Nested request model for one passenger count event."""

    number_seated: int
    number_standing: int


class BehindScheduleReportIn(InspectionBaseIn):
    """Nested request model for one behind-schedule report."""

    behind_schedule_interval: BehindScheduleInterval


class BusInspectionsIn(BaseModel):
    """All inspection sections that can belong to one bus within a shift."""

    external_inspected: bool = False
    internal_inspected: bool = False
    driver_inspected: bool = False
    passenger_counts_done: bool = False
    behind_schedule_reports_done: bool = False
    external: Optional[ExteriorInspectionIn] = None
    internal: Optional[InteriorInspectionIn] = None
    driver: Optional[DriverInspectionIn] = None
    passenger_counts: list[PassengerCountIn] = []
    behind_schedule_reports: list[BehindScheduleReportIn] = []

    @model_validator(mode="after")
    def sync_done_flags(self):
        """Keep done flags and payload sections in sync after validation.

        If a section is present, its corresponding flag is automatically turned
        on. If a flag says work is done but the section data is missing, the
        payload is rejected as inconsistent.
        """
        if self.external is not None:
            self.external_inspected = True
        if self.internal is not None:
            self.internal_inspected = True
        if self.driver is not None:
            self.driver_inspected = True
        if self.passenger_counts:
            self.passenger_counts_done = True
        if self.behind_schedule_reports:
            self.behind_schedule_reports_done = True

        if self.external_inspected and self.external is None:
            raise ValueError(
                "external must be provided when external_inspected is true"
            )
        if self.internal_inspected and self.internal is None:
            raise ValueError(
                "internal must be provided when internal_inspected is true"
            )
        if self.driver_inspected and self.driver is None:
            raise ValueError("driver must be provided when driver_inspected is true")
        if self.passenger_counts_done and not self.passenger_counts:
            raise ValueError(
                "passenger_counts must be provided when passenger_counts_done is true"
            )
        if self.behind_schedule_reports_done and not self.behind_schedule_reports:
            raise ValueError(
                "behind_schedule_reports must be provided when behind_schedule_reports_done is true"
            )
        return self


# ---------------------------------------------------------------------------
# Inspection
# ---------------------------------------------------------------------------


class InspectionIn(BaseModel):
    """Legacy alias retained temporarily while create-shift is migrated."""

    internal_inspection_id: str
    inspection_type: InspectionType
    inspection_time: datetime
    inspection_lat: float
    inspection_lon: float
    count: Optional[int] = 0
    pass_: bool = False
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
    photos: list[PhotoIn]

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Bus (one entry per bus inspected during the shift)
# ---------------------------------------------------------------------------


class BusIn(BaseModel):
    """One bus entry inside a shift creation request."""

    bus_id: Optional[str] = None  # maps to bus_id / vin
    bus_number: Optional[str] = None  # maps to fleet_number
    duty_number: str
    replacement_bus: bool = False
    license_disk_scan_succeeded: Optional[bool] = True
    destination_displayed: Optional[bool] = True
    inspections: BusInspectionsIn

    @model_validator(mode="after")
    def require_identifier(self):
        """Require at least one bus identifier so the API can resolve the bus."""
        if not self.bus_id and not self.bus_number:
            raise ValueError("Either bus_id or bus_number must be provided")
        return self


# ---------------------------------------------------------------------------
# Shift  (top-level request body)
# ---------------------------------------------------------------------------


class ShiftCreate(BaseModel):
    """Top-level JSON payload for creating one complete shift."""

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
    """Photo metadata used by multipart requests where files travel separately."""

    timestamp: datetime
    lat: float
    lon: float


class SelfieMetaIn(PhotoMetaIn):
    """Selfie metadata used by multipart shift creation requests."""

    pass


class InspectionItemPhotoMetaIn(BaseModel):
    """Inspection-item photo metadata for multipart requests."""

    timestamp: datetime
    lat: float
    lon: float


class InspectionItemMetaIn(BaseModel):
    """Checklist item data for multipart requests."""

    pass_: bool = False
    reason: Optional[str] = None
    photos: list[InspectionItemPhotoMetaIn] = []


class InspectionBaseMetaIn(BaseModel):
    """Base inspection metadata shared by multipart request sections."""

    internal_inspection_id: str
    inspection_time: datetime
    inspection_lat: float
    inspection_lon: float


class ExteriorInspectionMetaIn(InspectionBaseMetaIn):
    """Multipart metadata for one external inspection."""

    tyres: InspectionItemMetaIn
    windows: InspectionItemMetaIn
    other: InspectionItemMetaIn


class InteriorInspectionMetaIn(InspectionBaseMetaIn):
    """Multipart metadata for one internal inspection."""

    fire_extinguisher_present: bool = False
    seats: InspectionItemMetaIn
    aisle: InspectionItemMetaIn
    other: InspectionItemMetaIn


class DriverInspectionMetaIn(InspectionBaseMetaIn):
    """Multipart metadata for one driver inspection."""

    prdp_scan_succeeded: Optional[bool] = None
    prdp_expiry_date: Optional[datetime] = None
    driver_identified: Optional[bool] = None
    driver_fail_reason: Optional[str] = None
    driver_name: Optional[str] = None
    photos: list[InspectionItemPhotoMetaIn] = []

    @field_validator("prdp_expiry_date", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "":
            return None
        return v


class PassengerCountMetaIn(InspectionBaseMetaIn):
    """Multipart metadata for one passenger-count event."""

    number_seated: int
    number_standing: int


class BehindScheduleReportMetaIn(InspectionBaseMetaIn):
    """Multipart metadata for one behind-schedule report."""

    behind_schedule_interval: BehindScheduleInterval


class BusInspectionsMetaIn(BaseModel):
    """All multipart inspection sections that can belong to one bus."""

    external_inspected: bool = False
    internal_inspected: bool = False
    driver_inspected: bool = False
    passenger_counts_done: bool = False
    behind_schedule_reports_done: bool = False
    external: Optional[ExteriorInspectionMetaIn] = None
    internal: Optional[InteriorInspectionMetaIn] = None
    driver: Optional[DriverInspectionMetaIn] = None
    passenger_counts: list[PassengerCountMetaIn] = []
    behind_schedule_reports: list[BehindScheduleReportMetaIn] = []

    @model_validator(mode="after")
    def sync_done_flags(self):
        """Keep multipart done flags consistent with the included sections."""
        if self.external is not None:
            self.external_inspected = True
        if self.internal is not None:
            self.internal_inspected = True
        if self.driver is not None:
            self.driver_inspected = True
        if self.passenger_counts:
            self.passenger_counts_done = True
        if self.behind_schedule_reports:
            self.behind_schedule_reports_done = True

        if self.external_inspected and self.external is None:
            raise ValueError(
                "external must be provided when external_inspected is true"
            )
        if self.internal_inspected and self.internal is None:
            raise ValueError(
                "internal must be provided when internal_inspected is true"
            )
        if self.driver_inspected and self.driver is None:
            raise ValueError("driver must be provided when driver_inspected is true")
        if self.passenger_counts_done and not self.passenger_counts:
            raise ValueError(
                "passenger_counts must be provided when passenger_counts_done is true"
            )
        if self.behind_schedule_reports_done and not self.behind_schedule_reports:
            raise ValueError(
                "behind_schedule_reports must be provided when behind_schedule_reports_done is true"
            )
        return self


class InspectionMetaIn(BaseModel):
    """Legacy alias retained temporarily while multipart create-shift is migrated."""

    internal_inspection_id: str
    inspection_type: InspectionType
    inspection_time: datetime
    inspection_lat: float
    inspection_lon: float
    count: Optional[int] = 0
    pass_: bool = False
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
    """One bus entry inside a multipart shift creation request."""

    bus_id: Optional[str] = None
    bus_number: Optional[str] = None  # maps to fleet_number
    duty_number: str
    replacement_bus: bool = False
    license_disk_scan_succeeded: Optional[bool] = True
    destination_displayed: Optional[bool] = True
    inspections: BusInspectionsMetaIn

    @model_validator(mode="after")
    def require_identifier(self):
        """Require at least one bus identifier so the API can resolve the bus."""
        if not self.bus_id and not self.bus_number:
            raise ValueError("Either bus_id or bus_number must be provided")
        return self


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
    """Success/error marker used in shift responses."""

    success = "success"
    error = "error"


class ShiftCreatedResponse(BaseModel):
    """Response returned after a shift row and its child records are created."""

    status: int
    message: MessageResponse
    shift_id: int


class ShiftResponse(BaseModel):
    """Read model for one stored shift row."""

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
    """Read model for one stored shift selfie."""

    id: int
    shift_id: int
    timestamp: datetime
    lat: float
    lon: float
    photo: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PhotoResponse(BaseModel):
    """Read model for one stored inspection photo."""

    id: int
    inspection_id: int
    timestamp: datetime
    lat: float
    lon: float
    inspection_item: str
    photo: str
    created_at: datetime

    model_config = {"from_attributes": True}


class InspectionItemPhotoResponse(BaseModel):
    """Photo response nested inside grouped checklist items."""

    id: int
    timestamp: datetime
    lat: float
    lon: float
    photo: str
    created_at: datetime


class InspectionItemResponse(BaseModel):
    """Grouped checklist item response with pass/fail status and photos."""

    pass_: Optional[bool] = False
    reason: Optional[str] = None
    photos: list[InspectionItemPhotoResponse] = []


class InspectionEventResponse(BaseModel):
    """Fields shared by every grouped inspection event response."""

    inspection_id: int
    internal_inspection_id: str
    inspection_time: datetime
    inspection_lat: float
    inspection_lon: float
    pass_: Optional[bool] = False
    notes: Optional[str] = None


class ExteriorInspectionResponse(InspectionEventResponse):
    """Grouped response model for one external inspection."""

    tyres: InspectionItemResponse
    windows: InspectionItemResponse
    other: InspectionItemResponse


class InteriorInspectionResponse(InspectionEventResponse):
    """Grouped response model for one internal inspection."""

    fire_extinguisher_present: Optional[bool] = None
    seats: InspectionItemResponse
    aisle: InspectionItemResponse
    other: InspectionItemResponse


class DriverInspectionResponse(InspectionEventResponse):
    """Grouped response model for one driver inspection."""

    prdp_scan_succeeded: Optional[bool] = None
    prdp_expiry_date: Optional[datetime] = None
    driver_identified: Optional[bool] = None
    driver_fail_reason: Optional[str] = None
    driver_name: Optional[str] = None
    photos: list[InspectionItemPhotoResponse] = []


class PassengerCountInspectionResponse(InspectionEventResponse):
    """Grouped response model for one passenger-count event."""

    count: Optional[int] = 0
    number_seated: Optional[int] = None
    number_standing: Optional[int] = None


class BehindScheduleInspectionResponse(InspectionEventResponse):
    """Grouped response model for one behind-schedule event."""

    behind_schedule_interval: Optional[str] = None


class BusInspectionGroupItemsResponse(BaseModel):
    """Nested grouped inspection sections for one bus in a read response."""

    external_inspected: bool = False
    internal_inspected: bool = False
    driver_inspected: bool = False
    passenger_counts_done: bool = False
    behind_schedule_reports_done: bool = False
    external: Optional[ExteriorInspectionResponse] = None
    internal: Optional[InteriorInspectionResponse] = None
    driver: Optional[DriverInspectionResponse] = None
    passenger_counts: list[PassengerCountInspectionResponse] = []
    behind_schedule_reports: list[BehindScheduleInspectionResponse] = []


class GroupedBusInspectionResponse(BaseModel):
    """Top-level grouped read model returned by bus-inspection endpoints."""

    shift_id: int
    user_id: str
    bus_id: str
    fleet_number: Optional[str] = None
    duty_number: Optional[str] = None
    replacement_bus: bool = False
    license_disk_scan_succeeded: Optional[bool] = None
    destination_displayed: Optional[bool] = None
    inspections: BusInspectionGroupItemsResponse


class BusInspectionResponse(BaseModel):
    """Flat read model mirroring one stored bus inspection row."""

    id: int
    shift_id: int
    user_id: str
    bus_id: str
    fleet_number: str
    duty_number: Optional[str] = None
    replacement_bus: bool = False
    internal_inspection_id: str
    inspection_type: str
    inspection_time: datetime
    inspection_lat: float
    inspection_lon: float
    count: Optional[int] = 0
    pass_: Optional[bool] = False
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
    driver_name: Optional[str] = None

    model_config = {"from_attributes": True}


class DateRangeLimitQueryParams(BaseModel):
    """Shared query-parameter model for date-range and limit filtering."""

    start_date: Optional[date] = Field(
        None,
        description="Start date filter (format: YYYY-MM-DD, e.g. 2026-05-01)",
        examples=["2026-05-01"],
    )
    end_date: Optional[date] = Field(
        None,
        description="End date filter (format: YYYY-MM-DD, e.g. 2026-05-15)",
        examples=["2026-05-15"],
    )
    start_time: Optional[time] = Field(
        None,
        description="Start time filter (format: HH:MM:SS, e.g. 08:00:00 — defaults to 00:00:00 when start_date is set)",
        examples=["08:00:00"],
    )
    end_time: Optional[time] = Field(
        None,
        description="End time filter (format: HH:MM:SS, e.g. 16:00:00 — defaults to 23:59:59 when end_date is set)",
        examples=["16:00:00"],
    )
    limit: Optional[int] = Field(
        100,
        description="Maximum number of records to return",
        examples=[100],
    )

    model_config = {"from_attributes": True}


def date_range_params(
    start_date: Optional[date] = Query(
        None,
        description="Start date filter (format: YYYY-MM-DD, e.g. 2026-05-01)",
        examples=["2026-05-01"],
    ),
    end_date: Optional[date] = Query(
        None,
        description="End date filter (format: YYYY-MM-DD, e.g. 2026-05-15)",
        examples=["2026-05-15"],
    ),
    start_time: Optional[time] = Query(
        None,
        description="Start time filter (format: HH:MM:SS, e.g. 08:00:00 — defaults to 00:00:00 when start_date is set)",
        examples=["08:00:00"],
    ),
    end_time: Optional[time] = Query(
        None,
        description="End time filter (format: HH:MM:SS, e.g. 16:00:00 — defaults to 23:59:59 when end_date is set)",
        examples=["16:00:00"],
    ),
    limit: Optional[int] = Query(
        100, description="Maximum number of records to return", examples=[100]
    ),
) -> DateRangeLimitQueryParams:
    """Build ``DateRangeLimitQueryParams`` from FastAPI query parameters."""
    return DateRangeLimitQueryParams(
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
