from datetime import date, datetime, time
from enum import Enum
from typing import List, Optional
from fastapi import Query
from pydantic import BaseModel, Field, model_validator

class ErrorResponse(BaseModel):
    detail: str


class InspectionType(str, Enum):
    external = "external"
    internal = "internal"
    count = "count"
    driver = "driver"
    behind_schedule = "behind_schedule"
    technical = "technical"


class BehindScheduleInterval(str, Enum):
    zero_to_five = "0-5 mins"
    five_to_ten = "5-10 mins"
    ten_to_fifteen = "10-15 mins"
    fifteen_plus = "15+ mins"


# ---------------------------------------------------------------------------
# Photo / Selfie  (photos sent as base64 bytes in JSON body)
# ---------------------------------------------------------------------------


class PhotoIn(BaseModel):
    timestamp: datetime
    lat: float
    lon: float
    photo: str  # base64-encoded image string


class SelfieIn(PhotoIn):
    pass


class InspectionItemPhotoIn(BaseModel):
    timestamp: datetime
    lat: float
    lon: float
    photo: str  # base64-encoded image string


class InspectionItemIn(BaseModel):
    pass_: bool = False
    reason: Optional[str] = None
    photos: list[InspectionItemPhotoIn] = []


class InspectionBaseIn(BaseModel):
    internal_inspection_id: str
    inspection_time: datetime
    inspection_lat: float
    inspection_lon: float


class ExteriorInspectionIn(InspectionBaseIn):
    tyres: InspectionItemIn
    windows: InspectionItemIn
    other: InspectionItemIn


class InteriorInspectionIn(InspectionBaseIn):
    fire_extinguisher_present: bool
    seats: InspectionItemIn
    aisle: InspectionItemIn
    other: InspectionItemIn


class DriverInspectionIn(InspectionBaseIn):
    prdp_scan_succeeded: Optional[bool] = None
    prdp_expiry_date: Optional[datetime] = None
    driver_identified: Optional[bool] = None
    driver_fail_reason: Optional[str] = None
    driver_name: Optional[str] = None


class PassengerCountIn(InspectionBaseIn):
    number_seated: int
    number_standing: int


class BehindScheduleReportIn(InspectionBaseIn):
    behind_schedule_interval: BehindScheduleInterval


class BusInspectionsIn(BaseModel):
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
    bus_id: str  # maps to bus_id / vin
    bus_number: Optional[str]  # maps to fleet_number
    license_disk_scan_succeeded: Optional[bool] = None
    destination_displayed: Optional[bool] = None
    inspections: BusInspectionsIn


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


class SelfieMetaIn(PhotoMetaIn):
    pass


class InspectionItemPhotoMetaIn(BaseModel):
    timestamp: datetime
    lat: float
    lon: float


class InspectionItemMetaIn(BaseModel):
    pass_: bool = False
    reason: Optional[str] = None
    photos: list[InspectionItemPhotoMetaIn] = []


class InspectionBaseMetaIn(BaseModel):
    internal_inspection_id: str
    inspection_time: datetime
    inspection_lat: float
    inspection_lon: float


class ExteriorInspectionMetaIn(InspectionBaseMetaIn):
    tyres: InspectionItemMetaIn
    windows: InspectionItemMetaIn
    other: InspectionItemMetaIn


class InteriorInspectionMetaIn(InspectionBaseMetaIn):
    fire_extinguisher_present: bool
    seats: InspectionItemMetaIn
    aisle: InspectionItemMetaIn
    other: InspectionItemMetaIn


class DriverInspectionMetaIn(InspectionBaseMetaIn):
    prdp_scan_succeeded: Optional[bool] = None
    prdp_expiry_date: Optional[datetime] = None
    driver_identified: Optional[bool] = None
    driver_fail_reason: Optional[str] = None
    driver_name: Optional[str] = None


class PassengerCountMetaIn(InspectionBaseMetaIn):
    number_seated: int
    number_standing: int


class BehindScheduleReportMetaIn(InspectionBaseMetaIn):
    behind_schedule_interval: BehindScheduleInterval


class BusInspectionsMetaIn(BaseModel):
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
    bus_id: str
    bus_number: Optional[str] = None  # maps to fleet_number
    license_disk_scan_succeeded: Optional[bool] = None
    destination_displayed: Optional[bool] = None
    inspections: BusInspectionsMetaIn


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


class InspectionItemPhotoResponse(BaseModel):
    id: int
    timestamp: datetime
    lat: float
    lon: float
    photo: str
    created_at: datetime


class InspectionItemResponse(BaseModel):
    pass_: Optional[bool] = False
    reason: Optional[str] = None
    photos: list[InspectionItemPhotoResponse] = []


class InspectionEventResponse(BaseModel):
    inspection_id: int
    internal_inspection_id: str
    inspection_time: datetime
    inspection_lat: float
    inspection_lon: float
    pass_: Optional[bool] = False
    notes: Optional[str] = None


class ExteriorInspectionResponse(InspectionEventResponse):
    tyres: InspectionItemResponse
    windows: InspectionItemResponse
    other: InspectionItemResponse


class InteriorInspectionResponse(InspectionEventResponse):
    fire_extinguisher_present: Optional[bool] = None
    seats: InspectionItemResponse
    aisle: InspectionItemResponse
    other: InspectionItemResponse


class DriverInspectionResponse(InspectionEventResponse):
    prdp_scan_succeeded: Optional[bool] = None
    prdp_expiry_date: Optional[datetime] = None
    driver_identified: Optional[bool] = None
    driver_fail_reason: Optional[str] = None
    driver_name: Optional[str] = None


class PassengerCountInspectionResponse(InspectionEventResponse):
    count: Optional[int] = 0
    number_seated: Optional[int] = None
    number_standing: Optional[int] = None


class BehindScheduleInspectionResponse(InspectionEventResponse):
    behind_schedule_interval: Optional[str] = None


class BusInspectionGroupItemsResponse(BaseModel):
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
    shift_id: int
    user_id: str
    bus_id: str
    fleet_number: Optional[str] = None
    license_disk_scan_succeeded: Optional[bool] = None
    destination_displayed: Optional[bool] = None
    inspections: BusInspectionGroupItemsResponse


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
    start_date: Optional[date] = Field(
        None,
        description="Start date filter",
        examples=["2026-05-01"],
    )
    end_date: Optional[date] = Field(
        None,
        description="End date filter",
        examples=["2026-05-15"],
    )
    start_time: Optional[time] = Field(
        None,
        description="Start time filter (defaults to 00:00:00 when start_date is set)",
        examples=["08:00:00"],
    )
    end_time: Optional[time] = Field(
        None,
        description="End time filter (defaults to 23:59:59 when end_date is set)",
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
        None, description="Start date filter", examples=["2026-05-01"]
    ),
    end_date: Optional[date] = Query(
        None, description="End date filter", examples=["2026-05-15"]
    ),
    start_time: Optional[time] = Query(
        None,
        description="Start time filter (defaults to 00:00:00 when start_date is set)",
        examples=["08:00:00"],
    ),
    end_time: Optional[time] = Query(
        None,
        description="End time filter (defaults to 23:59:59 when end_date is set)",
        examples=["16:00:00"],
    ),
    limit: Optional[int] = Query(
        100, description="Maximum number of records to return", examples=[100]
    ),
) -> DateRangeLimitQueryParams:
    return DateRangeLimitQueryParams(
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
