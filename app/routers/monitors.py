import datetime
"""Routes and helpers for creating and listing monitor shifts.

This module turns the nested shift contract used by the mobile/web clients into
the flatter database rows stored in the existing schema.
"""

from datetime import date, time
from typing import Annotated, List, Optional

import base64
from fastapi import Depends, HTTPException, APIRouter, Query, Request, Form, status
from firebase_admin import db
from sqlalchemy.exc import IntegrityError, DataError, OperationalError
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user
from app.database import get_db
from app.models.app_auth import AppUser
from app.models.master_data import Vehicle
from app.models.photo import Selfie, Photo
from app.models.shift import Shift
from app.models import BusInspection
from app.schemas.shift import (
    ShiftCreate,
    ShiftCreateMeta,
    ShiftCreatedResponse,
    ShiftResponse,
    ErrorResponse,
    PhotoIn,
    SelfieIn,
    BusIn,
    DateRangeLimitQueryParams,
    date_range_params,
)

monitor_router = APIRouter()

_401 = {
    401: {
        "model": ErrorResponse,
        "description": "Unauthorized – invalid or missing token",
    }
}
_403 = {403: {"model": ErrorResponse, "description": "Forbidden – insufficient role"}}
_404 = {404: {"model": ErrorResponse, "description": "Resource not found"}}
_422 = {
    422: {
        "model": ErrorResponse,
        "description": "Validation error – malformed request body",
    }
}
_500 = {500: {"model": ErrorResponse, "description": "Internal server error"}}


def _combine_reasons(*reasons: str | None) -> str | None:
    """Join multiple optional failure reasons into one readable string."""
    combined = [reason for reason in reasons if reason]
    return "; ".join(combined) if combined else None


def _photo_payloads_from_inline(photo_groups: dict[str, list]) -> list[dict]:
    """Flatten grouped inline photo models into rows ready for ``Photo`` inserts.

    The request schema groups photos under inspection items like ``tyres`` or
    ``seats``. The database stores one photo row at a time, so this helper
    expands the nested structure into a simple list of dictionaries.
    """
    payloads = []
    for inspection_item, photos in photo_groups.items():
        for photo in photos:
            payloads.append(
                {
                    "timestamp": photo.timestamp,
                    "lat": photo.lat,
                    "lon": photo.lon,
                    "inspection_item": inspection_item,
                    "photo": photo.photo,
                }
            )
    return payloads


async def _photo_payloads_from_multipart(
    form,
    key_prefix: str,
    photo_groups: dict[str, list],
) -> list[dict]:
    """Build photo payloads from multipart uploads and matching metadata.

    Multipart requests send image bytes separately from the JSON metadata. This
    helper looks up each uploaded file by its expected form key, reads the file,
    base64-encodes it, and returns the same row structure used by the JSON flow.
    """
    payloads = []
    for inspection_item, photos in photo_groups.items():
        for index, photo_meta in enumerate(photos):
            file_key = f"{key_prefix}_{inspection_item}_photo_{index}"
            file = form.get(file_key)
            if file is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Missing file: {file_key}",
                )
            photo_bytes = await file.read()
            payloads.append(
                {
                    "timestamp": photo_meta.timestamp,
                    "lat": photo_meta.lat,
                    "lon": photo_meta.lon,
                    "inspection_item": inspection_item,
                    "photo": base64.b64encode(photo_bytes).decode(),
                }
            )
    return payloads


def _persist_inspection(
    db: Session,
    inspection_payload: dict,
    photo_payloads: list[dict] | None = None,
):
    """Insert one inspection row and any child photo rows linked to it.

    ``db.flush()`` is important here because it asks SQLAlchemy to send the
    inspection insert immediately so the database-generated inspection ID becomes
    available for related photo rows in the same transaction.
    """
    new_inspection = BusInspection(**inspection_payload)
    db.add(new_inspection)
    db.flush()
    db.refresh(new_inspection)

    for photo_payload in photo_payloads or []:
        db.add(Photo(inspection_id=new_inspection.id, **photo_payload))


def _resolve_bus_reference(db: Session, bus) -> tuple[str, str]:
    """Resolve a bus request into the VIN and fleet number required by storage.

    Clients may send either ``bus_id`` (VIN) or ``bus_number`` (fleet number).
    This helper looks up the missing identifier from ``master_data.vehicle`` so
    the write path always inserts a complete, valid pair.
    """
    if bus.bus_id and bus.bus_number:
        return bus.bus_id, bus.bus_number

    vehicle = None
    if bus.bus_id:
        vehicle = db.query(Vehicle).filter(Vehicle.vin == bus.bus_id).first()
    elif bus.bus_number:
        vehicle = (
            db.query(Vehicle).filter(Vehicle.fleet_number == bus.bus_number).first()
        )

    if vehicle is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Bus could not be resolved from bus_id or bus_number.",
        )

    return vehicle.vin, vehicle.fleet_number or vehicle.vin


def _base_inspection_payload(
    db: Session,
    shift_id: int,
    user_id: str,
    bus,
    inspection,
    inspection_type: str,
) -> dict:
    """Create the common database payload shared by all inspection types.

    Every inspection row stores the same core fields such as shift, bus, user,
    time, and location. Type-specific helpers call this first and then add only
    the fields that are unique to their inspection category.
    """
    bus_id, fleet_number = _resolve_bus_reference(db, bus)
    return {
        "user_id": user_id,
        "shift_id": shift_id,
        "bus_id": bus_id,
        "fleet_number": fleet_number,
        "duty_number": bus.duty_number,
        "replacement_bus": bus.replacement_bus,
        "internal_inspection_id": inspection.internal_inspection_id,
        "inspection_type": inspection_type,
        "inspection_time": inspection.inspection_time,
        "inspection_lat": inspection.inspection_lat,
        "inspection_lon": inspection.inspection_lon,
        "license_disk_scan_succeeded": bus.license_disk_scan_succeeded,
        "destination_displayed": bus.destination_displayed,
    }


def _external_inspection_record(db: Session, shift_id: int, user_id: str, bus, inspection):
    """Convert one nested external inspection into a flat DB row payload."""
    payload = _base_inspection_payload(
        db, shift_id, user_id, bus, inspection, "external"
    )
    payload.update(
        {
            "pass_": all(
                [
                    inspection.tyres.pass_,
                    inspection.windows.pass_,
                    inspection.other.pass_,
                ]
            ),
            "notes": _combine_reasons(
                inspection.tyres.reason,
                inspection.windows.reason,
                inspection.other.reason,
            ),
            "tyres_pass": inspection.tyres.pass_,
            "tyres_notes": inspection.tyres.reason,
            "windows_pass": inspection.windows.pass_,
            "windows_notes": inspection.windows.reason,
            "ext_other_pass": inspection.other.pass_,
            "ext_other_notes": inspection.other.reason,
        }
    )
    photo_groups = {
        "tyres": inspection.tyres.photos,
        "windows": inspection.windows.photos,
        "ext_other": inspection.other.photos,
    }
    return payload, photo_groups


def _interior_inspection_record(db: Session, shift_id: int, user_id: str, bus, inspection):
    """Convert one nested internal inspection into a flat DB row payload."""
    payload = _base_inspection_payload(
        db, shift_id, user_id, bus, inspection, "internal"
    )
    payload.update(
        {
            "pass_": all(
                [
                    inspection.fire_extinguisher_present,
                    inspection.seats.pass_,
                    inspection.aisle.pass_,
                    inspection.other.pass_,
                ]
            ),
            "notes": _combine_reasons(
                None
                if inspection.fire_extinguisher_present
                else "Fire extinguisher missing",
                inspection.seats.reason,
                inspection.aisle.reason,
                inspection.other.reason,
            ),
            "fire_extinguisher_present": inspection.fire_extinguisher_present,
            "seats_pass": inspection.seats.pass_,
            "seats_notes": inspection.seats.reason,
            "aisle_pass": inspection.aisle.pass_,
            "aisle_notes": inspection.aisle.reason,
            "int_other_pass": inspection.other.pass_,
            "int_other_notes": inspection.other.reason,
        }
    )
    photo_groups = {
        "seats": inspection.seats.photos,
        "aisle": inspection.aisle.photos,
        "int_other": inspection.other.photos,
    }
    return payload, photo_groups


def _driver_inspection_record(db: Session, shift_id: int, user_id: str, bus, inspection):
    """Convert one nested driver inspection into a flat DB row payload."""
    boolean_checks = [
        inspection.prdp_scan_succeeded,
        inspection.driver_identified,
    ]
    payload = _base_inspection_payload(db, shift_id, user_id, bus, inspection, "driver")
    payload.update(
        {
            "pass_": all(value for value in boolean_checks if value is not None),
            "notes": inspection.driver_fail_reason,
            "prdp_scan_succeeded": inspection.prdp_scan_succeeded,
            "prdp_expiry_date": inspection.prdp_expiry_date,
            "driver_identified": inspection.driver_identified,
            "driver_fail_reason": inspection.driver_fail_reason,
            "driver_name": inspection.driver_name,
        }
    )
    return payload, {"driver": inspection.photos}


def _passenger_count_record(db: Session, shift_id: int, user_id: str, bus, inspection):
    """Convert one passenger count event into the flat inspection storage shape."""
    payload = _base_inspection_payload(db, shift_id, user_id, bus, inspection, "count")
    payload.update(
        {
            "count": inspection.number_seated + inspection.number_standing,
            "number_seated": inspection.number_seated,
            "number_standing": inspection.number_standing,
        }
    )
    return payload, {}


def _behind_schedule_record(db: Session, shift_id: int, user_id: str, bus, inspection):
    """Convert one behind-schedule report into the flat inspection storage shape."""
    payload = _base_inspection_payload(
        db, shift_id, user_id, bus, inspection, "behind_schedule"
    )
    payload.update(
        {
            "behind_schedule_interval": inspection.behind_schedule_interval,
        }
    )
    return payload, {}


# We store all the shifts we will be receiving from the FE for the day
@monitor_router.post(
    "/create_shift/",
    status_code=201,
    response_model=ShiftCreatedResponse,
    responses={**_401, **_422, **_500},
)
async def create_shift(
    shift_data: ShiftCreate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Create a shift, then attach its selfies and nested bus inspections.

    The shift row is written first because child rows need the database-assigned
    ``shift_id``. After that, selfies and inspections are persisted using the
    nested request payload supplied by the client.
    """

    try:
        create_shif = Shift(
            user_id=shift_data.user_id,
            start_time=shift_data.start_time,
            end_time=shift_data.end_time,
            start_lat=shift_data.start_lat,
            start_lon=shift_data.start_lon,
            end_lat=shift_data.end_lat,
            end_lon=shift_data.end_lon,
            device_id=shift_data.device_id,
        )

        db.add(create_shif)
        db.commit()
        db.refresh(create_shif)
        selfies = await add_shift_selfies(create_shif.id, shift_data.selfies, db)
        inspections = await add_inspections(
            create_shif.id, shift_data.user_id, shift_data.busses, db
        )
        if not selfies or not inspections:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while processing selfies or inspections",
            )

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the shift. Please try again.",
        )
    return ShiftCreatedResponse(status=201, message="success", shift_id=create_shif.id)


# We add selfies captured during the shift to the selfies table, linked to the shift_id
async def add_shift_selfies(shift_id: int, selfies: List[SelfieIn], db: Session):
    """Insert all selfie rows that belong to one newly created shift."""
    if not selfies:
        return True  # No selfies to add, but not an error

    try:
        for selfie in selfies:
            new_selfie = Selfie(
                shift_id=shift_id,
                timestamp=selfie.timestamp,
                lat=selfie.lat,
                lon=selfie.lon,
                photo=selfie.photo,
            )
            db.add(new_selfie)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save selfie photos. Please check the photo data and try again.",
        )


async def add_inspections(shift_id: int, user_id: str, buses: List[BusIn], db: Session):
    """Flatten and insert every inspection event contained in a shift payload.

    Each bus may contain several logical sections, but the database stores those
    sections as separate rows in the inspections table. This function walks the
    nested contract and persists each concrete inspection event one by one.
    """
    if not buses:
        return True  # No inspections to add, but not an error

    current_bus_id = None
    try:
        for bus in buses:
            if bus.inspections.external is not None:
                inspection_payload, photo_groups = _external_inspection_record(
                    db, shift_id, user_id, bus, bus.inspections.external
                )
                _persist_inspection(
                    db,
                    inspection_payload,
                    _photo_payloads_from_inline(photo_groups),
                )

            if bus.inspections.internal is not None:
                inspection_payload, photo_groups = _interior_inspection_record(
                    db, shift_id, user_id, bus, bus.inspections.internal
                )
                _persist_inspection(
                    db,
                    inspection_payload,
                    _photo_payloads_from_inline(photo_groups),
                )

            if bus.inspections.driver is not None:
                inspection_payload, photo_groups = _driver_inspection_record(
                    db, shift_id, user_id, bus, bus.inspections.driver
                )
                _persist_inspection(
                    db,
                    inspection_payload,
                    _photo_payloads_from_inline(photo_groups),
                )

            for passenger_count in bus.inspections.passenger_counts:
                inspection_payload, _ = _passenger_count_record(
                    db, shift_id, user_id, bus, passenger_count
                )
                _persist_inspection(db, inspection_payload)

            for behind_schedule_report in bus.inspections.behind_schedule_reports:
                inspection_payload, _ = _behind_schedule_record(
                    db, shift_id, user_id, bus, behind_schedule_report
                )
                _persist_inspection(db, inspection_payload)

        db.commit()
        return True
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as e:
        db.rollback()
        orig = getattr(e, "orig", None)
        pgcode = getattr(orig, "pgcode", "") if orig else ""
        pg_diag = getattr(orig, "diag", None) if orig else None
        column = getattr(pg_diag, "column_name", None) if pg_diag else None
        constraint = getattr(pg_diag, "constraint_name", None) if pg_diag else None

        if pgcode == "23503":  # foreign_key_violation
            fk_messages = {
                "inspections_bus_id_fkey": f"Bus ID '{current_bus_id}' does not exist in the vehicle registry. Please verify the bus ID and try again.",
                "inspections_shift_id_fkey": "The referenced shift does not exist. Please verify the shift and try again.",
                "inspections_user_id_fkey": "The user account was not found. Please ensure the user is registered and try again.",
            }
            detail = fk_messages.get(
                constraint,
                f"A referenced record does not exist{f' (constraint: {constraint})' if constraint else ''}. Please verify all IDs and try again.",
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=detail,
            )
        if pgcode == "23505":  # unique_violation
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"A duplicate inspection record was detected{f' (constraint: {constraint})' if constraint else ''}. This inspection may have already been submitted.",
            )
        if pgcode == "23502":  # not_null_violation
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"A required field is missing{f': {column}' if column else ''}. Please check all required inspection fields are provided.",
            )
        if pgcode == "23514":  # check_violation
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"A field value is invalid{f' (constraint: {constraint})' if constraint else ''}. Please check the inspection values and try again.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database integrity error occurred while saving the inspection.",
        )
    except DataError as e:
        db.rollback()
        orig = getattr(e, "orig", None)
        pg_diag = getattr(orig, "diag", None) if orig else None
        column = getattr(pg_diag, "column_name", None) if pg_diag else None
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid data type or value{f' in field: {column}' if column else ''}. Please check the inspection data and try again.",
        )
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The database is temporarily unavailable. Please try again shortly.",
        )
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while saving the inspection data.",
        )


# ---------------------------------------------------------------------------
# Multipart version
#
# Send as multipart/form-data:
#   data          — JSON string of ShiftCreateMeta (no photo bytes)
#   selfie_{i}    — image file for selfies[i]
#   bus_{i}_external_{item}_photo_{k} — image file for an exterior item photo
#   bus_{i}_internal_{item}_photo_{k} — image file for an interior item photo
#   bus_{i}_driver_photo_{k} — image file for a driver inspection photo
# ---------------------------------------------------------------------------


# We are hiding this endpoint for now but might need it later
@monitor_router.post(
    "/create_shift_multipart/",
    status_code=201,
    response_model=ShiftCreatedResponse,
    responses={**_401, **_422, **_500},
    include_in_schema=False,
)
async def create_shift_multipart(
    request: Request,
    data: str = Form(...),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Create a shift from multipart form-data instead of a pure JSON body.

    This endpoint exists for clients that prefer uploading raw image files in
    the same request rather than base64 strings inside JSON. The metadata still
    follows the same nested shift contract.
    """
    try:
        shift_data = ShiftCreateMeta.model_validate_json(data)
        form = await request.form()

        new_shift = Shift(
            user_id=shift_data.user_id,
            start_time=shift_data.start_time,
            end_time=shift_data.end_time,
            start_lat=shift_data.start_lat,
            start_lon=shift_data.start_lon,
            end_lat=shift_data.end_lat,
            end_lon=shift_data.end_lon,
            device_id=shift_data.device_id,
        )
        db.add(new_shift)
        db.commit()
        db.refresh(new_shift)

        # Selfies — file key: selfie_{i}
        for i, selfie in enumerate(shift_data.selfies):
            file = form.get(f"selfie_{i}")
            if file is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Missing file: selfie_{i}",
                )
            photo_bytes = await file.read()
            db.add(
                Selfie(
                    shift_id=new_shift.id,
                    timestamp=selfie.timestamp,
                    lat=selfie.lat,
                    lon=selfie.lon,
                    photo=base64.b64encode(photo_bytes).decode(),
                )
            )

        # Inspections + item photos — file keys are scoped by bus, section and item.
        for i, bus in enumerate(shift_data.busses):
            if bus.inspections.external is not None:
                inspection_payload, photo_groups = _external_inspection_record(
                    db, new_shift.id, shift_data.user_id, bus, bus.inspections.external
                )
                photo_payloads = await _photo_payloads_from_multipart(
                    form, f"bus_{i}_external", photo_groups
                )
                _persist_inspection(db, inspection_payload, photo_payloads)

            if bus.inspections.internal is not None:
                inspection_payload, photo_groups = _interior_inspection_record(
                    db, new_shift.id, shift_data.user_id, bus, bus.inspections.internal
                )
                photo_payloads = await _photo_payloads_from_multipart(
                    form, f"bus_{i}_internal", photo_groups
                )
                _persist_inspection(db, inspection_payload, photo_payloads)

            if bus.inspections.driver is not None:
                inspection_payload, photo_groups = _driver_inspection_record(
                    db, new_shift.id, shift_data.user_id, bus, bus.inspections.driver
                )
                photo_payloads = await _photo_payloads_from_multipart(
                    form, f"bus_{i}", photo_groups
                )
                _persist_inspection(db, inspection_payload, photo_payloads)

            for passenger_count in bus.inspections.passenger_counts:
                inspection_payload, _ = _passenger_count_record(
                    db, new_shift.id, shift_data.user_id, bus, passenger_count
                )
                _persist_inspection(db, inspection_payload)

            for behind_schedule_report in bus.inspections.behind_schedule_reports:
                inspection_payload, _ = _behind_schedule_record(
                    db, new_shift.id, shift_data.user_id, bus, behind_schedule_report
                )
                _persist_inspection(db, inspection_payload)

        db.commit()
        return ShiftCreatedResponse(status=201, message="success", shift_id=new_shift.id)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the shift: {str(e)}",
        )


@monitor_router.get(
    "/shifts",
    response_model=List[ShiftResponse],
    responses={**_401, **_500},
    summary="Get all shifts with optional date range and limit",
)
async def get_all_shifts(
    params: DateRangeLimitQueryParams = Depends(date_range_params),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Return shift rows with optional date-range filtering and pagination size.

    Despite the name ``limit``, this endpoint still returns a plain list of
    shift records. The filters are applied directly at the database query level
    to avoid loading unnecessary rows into memory.
    """
    try:
        query = db.query(Shift).order_by(Shift.created_at.desc())

        if params.start_date:
            start_dt = datetime.datetime.combine(
                params.start_date, params.start_time or time.min
            )
            query = query.filter(Shift.created_at >= start_dt)
        if params.end_date:
            end_dt = datetime.datetime.combine(
                params.end_date, params.end_time or time(23, 59, 59)
            )
            query = query.filter(Shift.created_at <= end_dt)

        if params.limit:
            query = query.limit(params.limit)

        shifts = query.all()
        return [ShiftResponse.model_validate(s) for s in shifts]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving shifts: {exc}",
        )


@monitor_router.get(
    "/shifts/by_ids",
    response_model=List[ShiftResponse],
    responses={**_401, **_404, **_500},
    summary="Get shifts by one or more IDs",
)
async def get_shifts_by_ids(
    ids: List[int] = Query(..., description="One or more shift IDs to retrieve"),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Return only the shifts whose database IDs were explicitly requested."""
    if not ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one shift ID must be provided",
        )
    try:
        shifts = db.query(Shift).filter(Shift.id.in_(ids)).all()
        if not shifts:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No shifts found for the provided IDs",
            )
        return [ShiftResponse.model_validate(s) for s in shifts]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving shifts: {exc}",
        )
