import datetime

"""Routes and helpers for creating and listing monitor shifts.

This module turns the nested shift contract used by the mobile/web clients into
the flatter database rows stored in the existing schema.
"""

from datetime import date, time
from typing import Annotated, List, Optional

import base64
import json
from fastapi import (
    BackgroundTasks,
    Depends,
    HTTPException,
    APIRouter,
    Query,
    Request,
    Form,
    status,
)
from firebase_admin import db
from sqlalchemy import String, cast, func, or_
from sqlalchemy.exc import IntegrityError, DataError, OperationalError
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.app_auth import AppUser
from app.services.audit_service import build_request_audit_context, log_api_success

# from app.models.master_data import Vehicle  # re-enable if _resolve_bus_reference is un-commented
from app.models.photo import Selfie, Photo
from app.models.shift import Shift
from app.models import BusInspection
from app.schemas.shift import (
    ShiftCreate,
    ShiftCreateMeta,
    ShiftCreatedResponse,
    MonitorSummaryResponse,
    ShiftPageResponse,
    ShiftResponse,
    ErrorResponse,
    PhotoIn,
    SelfieIn,
    BusIn,
    DateRangeLimitQueryParams,
    date_range_params,
    _DEFAULT_BEHIND_SCHEDULE_INTERVAL,
    _VALID_BEHIND_SCHEDULE_INTERVALS,
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


def _behind_schedule_interval_repairs_from_payload(payload) -> list[dict]:
    """Return behind-schedule intervals that were defaulted for compatibility."""
    repairs: list[dict] = []
    busses = payload.get("busses") if isinstance(payload, dict) else None
    if not isinstance(busses, list):
        return repairs

    for bus_index, bus in enumerate(busses):
        if not isinstance(bus, dict):
            continue
        inspections = bus.get("inspections")
        if not isinstance(inspections, dict):
            continue
        reports = inspections.get("behind_schedule_reports")
        if not isinstance(reports, list):
            continue

        for report_index, report in enumerate(reports):
            if not isinstance(report, dict):
                continue
            original_value = report.get("behind_schedule_interval")
            if original_value in _VALID_BEHIND_SCHEDULE_INTERVALS:
                continue
            repairs.append(
                {
                    "path": f"busses[{bus_index}].inspections.behind_schedule_reports[{report_index}].behind_schedule_interval",
                    "bus_id": bus.get("bus_id"),
                    "bus_number": bus.get("bus_number"),
                    "duty_number": bus.get("duty_number"),
                    "internal_inspection_id": report.get("internal_inspection_id"),
                    "inspection_time": report.get("inspection_time"),
                    "original_value": original_value,
                    "defaulted_to": _DEFAULT_BEHIND_SCHEDULE_INTERVAL,
                }
            )
    return repairs


async def _behind_schedule_interval_repairs(request: Request) -> list[dict]:
    """Inspect the original JSON body for defaulted behind-schedule intervals."""
    try:
        payload = await request.json()
    except Exception:
        return []
    return _behind_schedule_interval_repairs_from_payload(payload)


def _shift_response(shift: Shift, user: AppUser | None = None) -> ShiftResponse:
    """Serialize a shift with the monitor's display name when available."""
    return ShiftResponse.model_validate(shift).model_copy(
        update={
            "user_id": shift.user_id,
            "user_name": user.name if user else None,
            "user_surname": user.surname if user else None,
        }
    )


def _monitor_summary_label(user: AppUser | None, user_id: str) -> str:
    """Return the best available display label for a monitor option."""
    if not user:
        return user_id
    full_name = user.full_name or " ".join(
        part for part in [user.name, user.surname] if part
    ).strip()
    return full_name or user.email or user_id


def _shift_page_sort_expression(
    sort_field: str | None,
    inspection_count,
    failed_inspection_count,
):
    """Map UI sort names to safe SQLAlchemy expressions."""

    if sort_field == "id":
        return Shift.id
    if sort_field == "loggedBy":
        return func.coalesce(AppUser.full_name, "")
    if sort_field == "start_time":
        return Shift.start_time
    if sort_field == "end_time":
        return Shift.end_time
    if sort_field == "duration":
        return Shift.end_time - Shift.start_time
    if sort_field == "inspectionCount":
        return inspection_count
    if sort_field == "failedInspectionCount":
        return failed_inspection_count
    if sort_field == "device_id":
        return Shift.device_id
    if sort_field == "created_at":
        return Shift.created_at
    return Shift.created_at


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


# def _resolve_bus_reference(db: Session, bus) -> tuple[str, str]:
#     """Resolve a bus request into the VIN and fleet number required by storage.
#
#     Clients may send either ``bus_id`` (VIN) or ``bus_number`` (fleet number).
#     This helper looks up the missing identifier from ``master_data.vehicle`` so
#     the write path always inserts a complete, valid pair.  When the vehicle is
#     not found in master data the supplied identifiers are used as-is so that
#     inspections can still be recorded for buses not yet registered.
#     """
#     if bus.bus_id and bus.bus_number:
#         return bus.bus_id, bus.bus_number
#
#     vehicle = None
#     if bus.bus_id:
#         vehicle = db.query(Vehicle).filter(Vehicle.vin == bus.bus_id).first()
#     elif bus.bus_number:
#         vehicle = (
#             db.query(Vehicle).filter(Vehicle.fleet_number == bus.bus_number).first()
#         )
#
#     if vehicle is not None:
#         return vehicle.vin, vehicle.fleet_number or vehicle.vin
#
#     # Vehicle not in master data — use the supplied values directly
#     if bus.bus_id:
#         return bus.bus_id, bus.bus_number or bus.bus_id
#     if bus.bus_number:
#         return bus.bus_number, bus.bus_number
#
#     raise HTTPException(
#         status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
#         detail="Bus could not be resolved: neither bus_id nor bus_number was provided.",
#     )


def _validate_bus_identifier(bus) -> None:
    """Raise 422 if neither bus_id nor bus_number is provided."""
    if not bus.bus_id and not bus.bus_number:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one of bus_id or bus_number must be provided.",
        )


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
    # bus_id, fleet_number = _resolve_bus_reference(db, bus)  # un-comment to enable DB-based resolution
    _validate_bus_identifier(bus)
    return {
        "user_id": user_id,
        "shift_id": shift_id,
        "bus_id": bus.bus_id or bus.bus_number,
        "fleet_number": bus.bus_number or bus.bus_id,
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


def _external_inspection_record(
    db: Session, shift_id: int, user_id: str, bus, inspection
):
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


def _interior_inspection_record(
    db: Session, shift_id: int, user_id: str, bus, inspection
):
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
                (
                    None
                    if inspection.fire_extinguisher_present
                    else "Fire extinguisher missing"
                ),
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


def _driver_inspection_record(
    db: Session, shift_id: int, user_id: str, bus, inspection
):
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
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Create a shift, then attach its selfies and nested bus inspections.

    The shift row is written first because child rows need the database-assigned
    ``shift_id``. After that, selfies and inspections are persisted using the
    nested request payload supplied by the client.
    """

    try:
        request_audit_context = build_request_audit_context(request)

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

        interval_repairs = await _behind_schedule_interval_repairs(request)
        if interval_repairs:
            background_tasks.add_task(
                log_api_success,
                request,
                status_code=status.HTTP_201_CREATED,
                success_category="PAYLOAD_NORMALIZED",
                success_code="BEHIND_SCHEDULE_INTERVAL_DEFAULTED",
                success_message=(
                    "Invalid behind_schedule_interval value defaulted to "
                    f"{_DEFAULT_BEHIND_SCHEDULE_INTERVAL}: shift_id={create_shif.id}"
                ),
                request_context=request_audit_context,
                request_body={
                    "shift_id": create_shif.id,
                    "user_id": shift_data.user_id,
                    "defaulted_to": _DEFAULT_BEHIND_SCHEDULE_INTERVAL,
                    "repairs": interval_repairs,
                },
            )

        if get_settings().audit_success_payloads_enabled:
            background_tasks.add_task(
                log_api_success,
                request,
                status_code=status.HTTP_201_CREATED,
                success_category="SUCCESS",
                success_code="SHIFT_CREATED",
                success_message=f"Shift created successfully: shift_id={create_shif.id}",
                request_context=request_audit_context,
                request_body=shift_data.model_dump(mode="json"),
            )

    except HTTPException as e:

        raise e
    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while creating the shift. Please try again. Error: {e}",
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
    background_tasks: BackgroundTasks,
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
        request_audit_context = build_request_audit_context(request)
        raw_metadata = json.loads(data)
        interval_repairs = _behind_schedule_interval_repairs_from_payload(raw_metadata)
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
        if interval_repairs:
            background_tasks.add_task(
                log_api_success,
                request,
                status_code=status.HTTP_201_CREATED,
                success_category="PAYLOAD_NORMALIZED",
                success_code="BEHIND_SCHEDULE_INTERVAL_DEFAULTED",
                success_message=(
                    "Invalid behind_schedule_interval value defaulted to "
                    f"{_DEFAULT_BEHIND_SCHEDULE_INTERVAL}: shift_id={new_shift.id}"
                ),
                request_context=request_audit_context,
                request_body={
                    "shift_id": new_shift.id,
                    "user_id": shift_data.user_id,
                    "defaulted_to": _DEFAULT_BEHIND_SCHEDULE_INTERVAL,
                    "repairs": interval_repairs,
                },
            )
        return ShiftCreatedResponse(
            status=201, message="success", shift_id=new_shift.id
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the shift: {str(e)}",
        )


@monitor_router.get(
    "/monitors/summary",
    response_model=List[MonitorSummaryResponse],
    responses={**_401, **_500},
    summary="Get monitor options with aggregate shift and inspection counts",
)
async def get_monitor_summaries(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Return lightweight monitor rows for dropdowns before loading details.

    The Monitors page should not need to load every shift, inspection, and
    selfie before the selector is usable. This endpoint returns one row per
    monitor-like app user, plus any unknown user ID that already has shift rows.
    """
    try:
        inspection_counts = (
            db.query(
                BusInspection.shift_id.label("shift_id"),
                func.count(BusInspection.id).label("inspection_count"),
                func.count(BusInspection.id)
                .filter(BusInspection.pass_.is_(False))
                .label("failed_inspection_count"),
            )
            .group_by(BusInspection.shift_id)
            .subquery()
        )

        shift_summary = (
            db.query(
                Shift.user_id.label("user_id"),
                func.count(Shift.id).label("shift_count"),
                func.coalesce(func.sum(inspection_counts.c.inspection_count), 0).label(
                    "inspection_count"
                ),
                func.coalesce(
                    func.sum(inspection_counts.c.failed_inspection_count), 0
                ).label("failed_inspection_count"),
                func.max(Shift.start_time).label("last_shift_at"),
            )
            .outerjoin(inspection_counts, inspection_counts.c.shift_id == Shift.id)
            .group_by(Shift.user_id)
            .subquery()
        )

        rows = (
            db.query(
                AppUser,
                shift_summary.c.shift_count,
                shift_summary.c.inspection_count,
                shift_summary.c.failed_inspection_count,
                shift_summary.c.last_shift_at,
            )
            .outerjoin(shift_summary, shift_summary.c.user_id == AppUser.firebase_uid)
            .filter(
                or_(
                    func.lower(AppUser.role).like("%monitor%"),
                    func.lower(AppUser.role).like("%supervisor%"),
                    shift_summary.c.shift_count.isnot(None),
                )
            )
            .filter(
                or_(
                    AppUser.is_active.is_(True),
                    shift_summary.c.shift_count.isnot(None),
                )
            )
            .all()
        )

        summaries = [
            MonitorSummaryResponse(
                user_id=user.firebase_uid,
                user_name=user.name,
                user_surname=user.surname,
                full_name=_monitor_summary_label(user, user.firebase_uid),
                email=user.email,
                role=user.role,
                shift_count=int(shift_count or 0),
                inspection_count=int(inspection_count or 0),
                failed_inspection_count=int(failed_inspection_count or 0),
                last_shift_at=last_shift_at,
            )
            for (
                user,
                shift_count,
                inspection_count,
                failed_inspection_count,
                last_shift_at,
            ) in rows
        ]

        unknown_rows = (
            db.query(
                shift_summary.c.user_id,
                shift_summary.c.shift_count,
                shift_summary.c.inspection_count,
                shift_summary.c.failed_inspection_count,
                shift_summary.c.last_shift_at,
            )
            .outerjoin(AppUser, AppUser.firebase_uid == shift_summary.c.user_id)
            .filter(AppUser.firebase_uid.is_(None))
            .all()
        )
        summaries.extend(
            MonitorSummaryResponse(
                user_id=user_id,
                full_name=user_id,
                shift_count=int(shift_count or 0),
                inspection_count=int(inspection_count or 0),
                failed_inspection_count=int(failed_inspection_count or 0),
                last_shift_at=last_shift_at,
            )
            for (
                user_id,
                shift_count,
                inspection_count,
                failed_inspection_count,
                last_shift_at,
            ) in unknown_rows
            if user_id
        )

        return sorted(
            summaries,
            key=lambda summary: (
                summary.full_name or summary.email or summary.user_id
            ).lower(),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving monitor summaries: {exc}",
        )


@monitor_router.get(
    "/shifts",
    response_model=List[ShiftResponse],
    responses={**_401, **_500},
    summary="Get all shifts with optional date range and limit",
)
async def get_all_shifts(
    params: DateRangeLimitQueryParams = Depends(date_range_params),
    user_id: str | None = Query(
        None, description="Limit shifts to one monitor user ID"
    ),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Return shift rows with optional date-range filtering and pagination size.

    Despite the name ``limit``, this endpoint still returns a plain list of
    shift records. The filters are applied directly at the database query level
    to avoid loading unnecessary rows into memory.
    """
    try:
        query = (
            db.query(Shift, AppUser)
            .outerjoin(AppUser, AppUser.firebase_uid == Shift.user_id)
            .order_by(Shift.created_at.desc())
        )

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
        if user_id:
            query = query.filter(Shift.user_id == user_id)

        if params.limit:
            query = query.limit(params.limit)

        rows = query.all()
        return [_shift_response(shift, user) for shift, user in rows]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving shifts: {exc}",
        )


@monitor_router.get(
    "/shifts/paged",
    response_model=ShiftPageResponse,
    responses={**_401, **_500},
    summary="Get shifts using server-side pagination, search, and sorting",
)
async def get_shifts_paged(
    first: int = Query(0, ge=0, description="Zero-based row offset"),
    rows: int = Query(25, ge=1, le=100, description="Number of rows to return"),
    search: str | None = Query(None, description="Global table search value"),
    sort_field: str | None = Query(
        "created_at", description="PrimeNG sort field name"
    ),
    sort_order: int = Query(
        -1, description="PrimeNG sort order: 1 for ascending, -1 for descending"
    ),
    params: DateRangeLimitQueryParams = Depends(date_range_params),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Return one server-side page of shift rows for the PrimeNG lazy table."""

    try:
        inspection_counts = (
            db.query(
                BusInspection.shift_id.label("shift_id"),
                func.count(BusInspection.id).label("inspection_count"),
                func.count(BusInspection.id)
                .filter(BusInspection.pass_.is_(False))
                .label("failed_inspection_count"),
            )
            .group_by(BusInspection.shift_id)
            .subquery()
        )

        inspection_count = func.coalesce(inspection_counts.c.inspection_count, 0)
        failed_inspection_count = func.coalesce(
            inspection_counts.c.failed_inspection_count, 0
        )

        query = (
            db.query(Shift, AppUser, inspection_count, failed_inspection_count)
            .outerjoin(AppUser, AppUser.firebase_uid == Shift.user_id)
            .outerjoin(inspection_counts, inspection_counts.c.shift_id == Shift.id)
        )

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

        if search and search.strip():
            value = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    cast(Shift.id, String).ilike(value),
                    func.lower(func.coalesce(AppUser.full_name, "")).like(value),
                    func.lower(func.coalesce(AppUser.name, "")).like(value),
                    func.lower(func.coalesce(AppUser.surname, "")).like(value),
                    func.lower(func.coalesce(Shift.user_id, "")).like(value),
                    func.lower(func.coalesce(Shift.device_id, "")).like(value),
                    cast(Shift.start_time, String).ilike(value),
                    cast(Shift.end_time, String).ilike(value),
                    cast(Shift.created_at, String).ilike(value),
                    cast(Shift.start_lat, String).ilike(value),
                    cast(Shift.start_lon, String).ilike(value),
                    cast(Shift.end_lat, String).ilike(value),
                    cast(Shift.end_lon, String).ilike(value),
                )
            )

        total = query.count()
        sort_expression = _shift_page_sort_expression(
            sort_field,
            inspection_count,
            failed_inspection_count,
        )
        ordered_query = query.order_by(
            sort_expression.asc() if sort_order == 1 else sort_expression.desc(),
            Shift.id.desc(),
        )
        page_rows = ordered_query.offset(first).limit(rows).all()

        return ShiftPageResponse(
            items=[
                _shift_response(shift, user).model_copy(
                    update={
                        "inspection_count": int(count or 0),
                        "failed_inspection_count": int(failed_count or 0),
                    }
                )
                for shift, user, count, failed_count in page_rows
            ],
            total=total,
            first=first,
            rows=rows,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving paged shifts: {exc}",
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
        rows = (
            db.query(Shift, AppUser)
            .outerjoin(AppUser, AppUser.firebase_uid == Shift.user_id)
            .filter(Shift.id.in_(ids))
            .all()
        )
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No shifts found for the provided IDs",
            )
        return [_shift_response(shift, user) for shift, user in rows]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving shifts: {exc}",
        )
