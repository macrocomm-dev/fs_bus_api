from collections import defaultdict
from datetime import date, datetime, time
from typing import Annotated, List, Optional

from fastapi import (
    Depends,
    File,
    Form,
    HTTPException,
    APIRouter,
    Path,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, selectinload

from app.auth import TokenData, get_current_user, split_user_name
from app.database import get_db
from app.models.app_auth import AppUser
from app.models.master_data import Operator, Route, Vehicle
from app.models.bus_inspection import BusInspection
from app.models.operations import (
    Inspection,
    InspectionCheck,
    InspectionPhoto,
    PassengerCount,
)
from app.schemas.shift import (
    DateRangeLimitQueryParams,
    GroupedBusInspectionResponse,
    date_range_params,
)

ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
from app.schemas.operations import (
    ErrorResponse,
    InspectionCheckCreate,
    InspectionCheckCreatedResponse,
    InspectionCheckResponse,
    InspectionChecksEnvelope,
    InspectionCreate,
    InspectionCreatedResponse,
    InspectionEnvelope,
    InspectionListEnvelope,
    InspectionResponse,
    MessageResponse,
    PassengerCountCreatedResponse,
    PassengerCountCreate,
    PassengerCountEnvelope,
    PassengerCountResponse,
    inspection_create_form,
)

inspection_router = APIRouter()

_401 = {
    401: {
        "model": ErrorResponse,
        "description": "Unauthorized – invalid or missing token",
    }
}
_403 = {403: {"model": ErrorResponse, "description": "Forbidden – insufficient role"}}
_404 = {404: {"model": ErrorResponse, "description": "Resource not found"}}
_500 = {500: {"model": ErrorResponse, "description": "Internal server error"}}
_BUS_INSPECTIONS_200 = {
    200: {
        "description": "Grouped bus inspections",
        "content": {
            "application/json": {
                "example": [
                    {
                        "shift_id": 10,
                        "user_id": "firebase_uid_abc123",
                        "bus_id": "VIN0001ZA",
                        "fleet_number": "GA 01 001 GP",
                        "license_disk_scan_succeeded": True,
                        "destination_displayed": True,
                        "inspections": {
                            "external_inspected": True,
                            "internal_inspected": True,
                            "driver_inspected": True,
                            "passenger_counts_done": True,
                            "behind_schedule_reports_done": True,
                            "external": {
                                "inspection_id": 1,
                                "internal_inspection_id": "ext-1",
                                "inspection_time": "2026-05-01T08:00:00",
                                "inspection_lat": -26.2045,
                                "inspection_lon": 28.048,
                                "pass_": False,
                                "notes": "Body damage on left rear panel",
                                "tyres": {"pass_": False, "reason": None, "photos": []},
                                "windows": {
                                    "pass_": False,
                                    "reason": None,
                                    "photos": [],
                                },
                                "other": {
                                    "pass_": False,
                                    "reason": "Body damage on left rear panel",
                                    "photos": [
                                        {
                                            "id": 101,
                                            "timestamp": "2026-05-01T08:02:00",
                                            "lat": -26.2045,
                                            "lon": 28.048,
                                            "photo": "<base64_encoded_image>",
                                            "created_at": "2026-05-01T08:03:00",
                                        }
                                    ],
                                },
                            },
                            "internal": {
                                "inspection_id": 2,
                                "internal_inspection_id": "int-1",
                                "inspection_time": "2026-05-01T08:05:00",
                                "inspection_lat": -26.2046,
                                "inspection_lon": 28.0481,
                                "pass_": False,
                                "notes": None,
                                "fire_extinguisher_present": True,
                                "seats": {"pass_": False, "reason": None, "photos": []},
                                "aisle": {"pass_": False, "reason": None, "photos": []},
                                "other": {"pass_": False, "reason": None, "photos": []},
                            },
                            "driver": {
                                "inspection_id": 3,
                                "internal_inspection_id": "drv-1",
                                "inspection_time": "2026-05-01T08:07:00",
                                "inspection_lat": -26.2047,
                                "inspection_lon": 28.0482,
                                "pass_": True,
                                "notes": None,
                                "prdp_scan_succeeded": True,
                                "prdp_expiry_date": "2027-03-15T00:00:00",
                                "driver_identified": True,
                                "driver_fail_reason": None,
                                "driver_name": "Sipho Nkosi",
                            },
                            "passenger_counts": [
                                {
                                    "inspection_id": 4,
                                    "internal_inspection_id": "cnt-1",
                                    "inspection_time": "2026-05-01T08:15:00",
                                    "inspection_lat": -26.205,
                                    "inspection_lon": 28.0488,
                                    "pass_": False,
                                    "notes": None,
                                    "count": 40,
                                    "number_seated": 32,
                                    "number_standing": 8,
                                }
                            ],
                            "behind_schedule_reports": [
                                {
                                    "inspection_id": 5,
                                    "internal_inspection_id": "sch-1",
                                    "inspection_time": "2026-05-01T08:20:00",
                                    "inspection_lat": -26.2052,
                                    "inspection_lon": 28.049,
                                    "pass_": False,
                                    "notes": None,
                                    "behind_schedule_interval": "5-10 mins",
                                }
                            ],
                        },
                    }
                ]
            }
        },
    }
}


# Helper function to get or create AppUser based on Firebase UID
async def get_user_id_from_token(current_user: TokenData, db: Session) -> int:
    app_user = (
        db.query(AppUser).filter(AppUser.firebase_uid == current_user.sub).first()
    )
    if app_user is None:
        name, surname = split_user_name(current_user.name)
        app_user = AppUser(
            firebase_uid=current_user.sub,
            email=current_user.email,
            full_name=current_user.name,
            name=name,
            surname=surname,
            role=current_user.role,
            is_active=True,
        )
        db.add(app_user)
        db.commit()
        db.refresh(app_user)
    return app_user.user_id


# Resolve the AppUser and their Operator from a Firebase token.
# Raises 401 if the user has never been provisioned in the database.
async def _resolve_app_user(current_user: TokenData, db: Session):
    app_user = (
        db.query(AppUser).filter(AppUser.firebase_uid == current_user.sub).first()
    )
    if app_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found. Contact an administrator.",
        )
    operator = None
    if app_user.operator_id is not None:
        operator = (
            db.query(Operator)
            .filter(Operator.operator_id == app_user.operator_id)
            .first()
        )
    return app_user, operator


def _is_internal(operator) -> bool:
    """Internal operator users can see data across all operators."""
    return operator is None or operator.operator_name == "Internal"


# create inspection endpoint, only accessible to Monitor, Supervisor, Admin roles. Auto-provision user on first login based on Firebase UID → DB user_id mapping
@inspection_router.post(
    "/create_inspection",
    status_code=status.HTTP_201_CREATED,
    response_model=InspectionCreatedResponse,
    responses={**_401, **_403, **_500},
    include_in_schema=False,
)
async def create_inspection(
    payload: InspectionCreate = Depends(inspection_create_form),
    file: UploadFile | None = File(None),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        if current_user.role not in ["Monitor", "Supervisor", "Admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to create inspections",
            )

        new_inspection = Inspection(
            vehicle_id=payload.vehicle_id,
            route_id=payload.route_id,
            route_text=payload.route_text,
            user_id=payload.user_id,
            inspection_type=payload.inspection_type,
            status=payload.status,
            latitude=payload.latitude,
            longitude=payload.longitude,
            notes=payload.notes,
            date_of_inspection=payload.date_of_inspection,
            device_id=payload.device_id,
        )
        db.add(new_inspection)
        db.commit()
        db.refresh(new_inspection)

        photo_id = None
        if file is not None:
            if file.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported file type '{file.content_type}'. Allowed: JPEG, PNG, WebP.",
                )
            data = await file.read()
            if len(data) > MAX_IMAGE_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Image exceeds the 10 MB size limit.",
                )
            new_photo = InspectionPhoto(
                inspection_id=new_inspection.inspection_id,
                image_data=data,
                content_type=file.content_type,
                user_id=payload.user_id,
            )
            db.add(new_photo)
            db.commit()
            db.refresh(new_photo)
            photo_id = new_photo.photo_id

        return {
            "message": MessageResponse.success,
            "inspection_id": new_inspection.inspection_id,
            "vehicle_id": new_inspection.vehicle_id,
            "route_id": new_inspection.route_id,
            "photo_id": photo_id,
        }
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": MessageResponse.fail,
                "detail": f"Error creating inspection: {exc}",
            },
        )


# Add inspection check endpoint, only accessible to Monitor, Supervisor, Admin roles
@inspection_router.post(
    "/inspection_check",
    status_code=status.HTTP_201_CREATED,
    response_model=InspectionCheckCreatedResponse,
    responses={**_401, **_500},
    include_in_schema=False,
)
async def add_inspection_check(
    payload: InspectionCheckCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:

        new_check = InspectionCheck(
            inspection_id=payload.inspection_id,
            section=payload.section,
            check_code=payload.check_code,
            check_label=payload.check_label,
            result=payload.result,
            notes=payload.notes,
            display_order=payload.display_order,
            date_of_inspectioncheck=payload.date_of_inspectioncheck,
            user_id=payload.user_id,
        )
        db.add(new_check)
        db.commit()
        db.refresh(new_check)

        return {
            "message": MessageResponse.success,
            "inspection_check_id": new_check.inspection_check_id,
            "inspection_id": new_check.inspection_id,
        }
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": MessageResponse.fail,
                "detail": f"Error adding inspection check: {exc}",
            },
        )


# Add passenger count endpoint
@inspection_router.post(
    "/passenger_count",
    status_code=status.HTTP_201_CREATED,
    response_model=PassengerCountCreatedResponse,
    responses={**_401, **_500},
    include_in_schema=False,
)
async def add_passenger_count(
    payload: PassengerCountCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        new_count = PassengerCount(
            vehicle_id=payload.vehicle_id,
            route_id=payload.route_id,
            route_text=payload.route_text,
            user_id=payload.user_id,
            passenger_count=payload.count,
            latitude=payload.latitude,
            longitude=payload.longitude,
            notes=payload.notes,
            date_of_passenger_count=payload.date_of_passenger_count,
        )
        db.add(new_count)
        db.commit()
        db.refresh(new_count)

        return {
            "message": MessageResponse.success,
            "count_id": new_count.count_id,
            "vehicle_id": new_count.vehicle_id,
            "route_id": new_count.route_id,
        }
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": MessageResponse.fail,
                "detail": f"Error adding passenger count: {exc}",
            },
        )


def _apply_date_range_limit(query, params: DateRangeLimitQueryParams):
    """Apply optional date-range and limit filters to a BusInspection query."""
    if params.start_date:
        start_dt = datetime.combine(params.start_date, params.start_time or time.min)
        query = query.filter(BusInspection.inspection_time >= start_dt)
    if params.end_date:
        end_dt = datetime.combine(params.end_date, params.end_time or time(23, 59, 59))
        query = query.filter(BusInspection.inspection_time <= end_dt)
    if params.limit is not None:
        query = query.limit(params.limit)
    return query


def _serialize_group_photo(photo) -> dict:
    return {
        "id": photo.id,
        "timestamp": photo.timestamp,
        "lat": photo.lat,
        "lon": photo.lon,
        "photo": photo.photo,
        "created_at": photo.created_at,
    }


def _inspection_item_response(pass_value, reason, photos_by_item, inspection_item: str):
    return {
        "pass_": pass_value,
        "reason": reason,
        "photos": photos_by_item.get(inspection_item, []),
    }


def _group_bus_inspection_rows(rows: list[BusInspection]) -> list[dict]:
    grouped: dict[tuple[int, str], dict] = {}

    for row in rows:
        key = (row.shift_id, row.bus_id)
        if key not in grouped:
            grouped[key] = {
                "shift_id": row.shift_id,
                "user_id": row.user_id,
                "bus_id": row.bus_id,
                "fleet_number": row.fleet_number,
                "license_disk_scan_succeeded": row.license_disk_scan_succeeded,
                "destination_displayed": row.destination_displayed,
                "inspections": {
                    "external_inspected": False,
                    "internal_inspected": False,
                    "driver_inspected": False,
                    "passenger_counts_done": False,
                    "behind_schedule_reports_done": False,
                    "external": None,
                    "internal": None,
                    "driver": None,
                    "passenger_counts": [],
                    "behind_schedule_reports": [],
                },
            }

        photos_by_item = defaultdict(list)
        for photo in row.photos:
            photos_by_item[photo.inspection_item].append(_serialize_group_photo(photo))

        base = {
            "inspection_id": row.id,
            "internal_inspection_id": row.internal_inspection_id,
            "inspection_time": row.inspection_time,
            "inspection_lat": row.inspection_lat,
            "inspection_lon": row.inspection_lon,
            "pass_": row.pass_,
            "notes": row.notes,
        }

        if row.inspection_type == "external":
            grouped[key]["inspections"]["external_inspected"] = True
            grouped[key]["inspections"]["external"] = {
                **base,
                "tyres": _inspection_item_response(
                    row.tyres_pass, row.tyres_notes, photos_by_item, "tyres"
                ),
                "windows": _inspection_item_response(
                    row.windows_pass, row.windows_notes, photos_by_item, "windows"
                ),
                "other": _inspection_item_response(
                    row.ext_other_pass,
                    row.ext_other_notes,
                    photos_by_item,
                    "ext_other",
                ),
            }
        elif row.inspection_type == "internal":
            grouped[key]["inspections"]["internal_inspected"] = True
            grouped[key]["inspections"]["internal"] = {
                **base,
                "fire_extinguisher_present": row.fire_extinguisher_present,
                "seats": _inspection_item_response(
                    row.seats_pass, row.seats_notes, photos_by_item, "seats"
                ),
                "aisle": _inspection_item_response(
                    row.aisle_pass, row.aisle_notes, photos_by_item, "aisle"
                ),
                "other": _inspection_item_response(
                    row.int_other_pass,
                    row.int_other_notes,
                    photos_by_item,
                    "int_other",
                ),
            }
        elif row.inspection_type == "driver":
            grouped[key]["inspections"]["driver_inspected"] = True
            grouped[key]["inspections"]["driver"] = {
                **base,
                "prdp_scan_succeeded": row.prdp_scan_succeeded,
                "prdp_expiry_date": row.prdp_expiry_date,
                "driver_identified": row.driver_identified,
                "driver_fail_reason": row.driver_fail_reason,
                "driver_name": row.driver_name,
            }

        if grouped[key]["license_disk_scan_succeeded"] is None:
            grouped[key][
                "license_disk_scan_succeeded"
            ] = row.license_disk_scan_succeeded
        if grouped[key]["destination_displayed"] is None:
            grouped[key]["destination_displayed"] = row.destination_displayed

        if row.inspection_type == "count":
            grouped[key]["inspections"]["passenger_counts_done"] = True
            grouped[key]["inspections"]["passenger_counts"].append(
                {
                    **base,
                    "count": row.count,
                    "number_seated": row.number_seated,
                    "number_standing": row.number_standing,
                }
            )
        elif row.inspection_type in {"behind_schedule", "technical"}:
            grouped[key]["inspections"]["behind_schedule_reports_done"] = True
            grouped[key]["inspections"]["behind_schedule_reports"].append(
                {
                    **base,
                    "behind_schedule_interval": row.behind_schedule_interval,
                }
            )

    return list(grouped.values())


@inspection_router.get(
    "/bus_inspections",
    response_model=List[GroupedBusInspectionResponse],
    responses={**_BUS_INSPECTIONS_200, **_401, **_500},
    summary="Get all bus inspections with optional date range and limit",
)
async def get_all_bus_inspections(
    params: DateRangeLimitQueryParams = Depends(date_range_params),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    try:
        query = db.query(BusInspection).options(selectinload(BusInspection.photos))
        query = _apply_date_range_limit(query, params)
        return _group_bus_inspection_rows(query.all())
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching inspections: {exc}",
        )


@inspection_router.get(
    "/bus_inspections/by_shift_ids",
    response_model=List[GroupedBusInspectionResponse],
    responses={**_BUS_INSPECTIONS_200, **_401, **_404, **_500},
    summary="Get bus inspections by shift IDs with optional date range and limit",
)
async def get_bus_inspections_by_shift(
    params: DateRangeLimitQueryParams = Depends(date_range_params),
    shift_ids: List[int] = Query(
        ..., description="One or more shift IDs to retrieve inspections for"
    ),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    if not shift_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one shift ID must be provided",
        )
    try:
        query = db.query(BusInspection).options(selectinload(BusInspection.photos))
        query = query.filter(BusInspection.shift_id.in_(shift_ids))
        query = _apply_date_range_limit(query, params)
        results = _group_bus_inspection_rows(query.all())
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No inspections found for the provided shift IDs",
            )
        return results
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching inspections: {exc}",
        )


@inspection_router.get(
    "/bus_inspections/by_bus_ids",
    response_model=List[GroupedBusInspectionResponse],
    responses={**_BUS_INSPECTIONS_200, **_401, **_404, **_500},
    summary="Get bus inspections by bus IDs/VINs with optional date range and limit",
)
async def get_bus_inspections_by_bus(
    params: DateRangeLimitQueryParams = Depends(date_range_params),
    bus_ids: List[str] = Query(
        ...,
        description="One or more vehicle VINs / bus IDs to retrieve inspections for",
    ),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    if not bus_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one bus ID must be provided",
        )
    try:
        query = db.query(BusInspection).options(selectinload(BusInspection.photos))
        query = query.filter(BusInspection.bus_id.in_(bus_ids))
        query = _apply_date_range_limit(query, params)
        results = _group_bus_inspection_rows(query.all())
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No inspections found for the provided bus IDs",
            )
        return results
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching inspections: {exc}",
        )


@inspection_router.get(
    "/bus_inspections/by_user_ids",
    response_model=List[GroupedBusInspectionResponse],
    responses={**_BUS_INSPECTIONS_200, **_401, **_404, **_500},
    summary="Get bus inspections by user IDs with optional date range and limit",
)
async def get_bus_inspections_by_user(
    params: DateRangeLimitQueryParams = Depends(date_range_params),
    user_ids: List[str] = Query(
        ...,
        description="One or more Firebase UIDs of monitors who recorded the inspections",
    ),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    if not user_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one user ID must be provided",
        )
    try:
        query = db.query(BusInspection).options(selectinload(BusInspection.photos))
        query = query.filter(BusInspection.user_id.in_(user_ids))
        query = _apply_date_range_limit(query, params)
        results = _group_bus_inspection_rows(query.all())
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No inspections found for the provided user IDs",
            )
        return results
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching inspections: {exc}",
        )
