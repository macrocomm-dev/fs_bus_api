"""Vehicle lookup endpoints and related access-control helpers."""

from datetime import datetime
from typing import List, Optional

from collections.abc import Iterable
from fastapi import (
    Depends,
    File,
    Form,
    HTTPException,
    APIRouter,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, Response
from firebase_admin import db
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user, split_user_name
from app.config import Settings, get_settings
from app.database import get_db
from app.models.app_auth import AppUser
from app.models.bus_inspection import BusInspection
from app.models.master_data import Operator, Route, Vehicle
from app.models.operations import (
    Inspection,
    InspectionCheck,
    InspectionPhoto,
    PassengerCount,
)
from app.schemas.operations import (
    ErrorResponse,
    MessageResponse,
    OperatorSummary,
    VehicleEnvelope,
    VehicleListEnvelope,
    VehicleResponse,
)
from app.services.smartfleet_service import (
    SmartFleetVehiclePosition,
    get_latest_vehicle_positions,
    vehicle_identifier_keys,
)

vehicle_router = APIRouter()

_401 = {
    401: {
        "model": ErrorResponse,
        "description": "Unauthorized – invalid or missing token",
    }
}
_403 = {403: {"model": ErrorResponse, "description": "Forbidden – insufficient role"}}
_404 = {404: {"model": ErrorResponse, "description": "Resource not found"}}
_500 = {500: {"model": ErrorResponse, "description": "Internal server error"}}


# Helper function to get or create AppUser based on Firebase UID
async def get_user_id_from_token(current_user: TokenData, db: Session) -> int:
    """Get or auto-create the local ``AppUser`` row for the authenticated user."""
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


ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


# Resolve the AppUser and their Operator from a Firebase token.
# Raises 401 if the user has never been provisioned in the database.
async def _resolve_app_user(current_user: TokenData, db: Session):
    """Load the caller's app user row and optional operator context.

    Many endpoints need both pieces of data to decide whether the caller should
    see all data or only the rows owned by their operator.
    """
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


def _vehicle_raw_identifiers(vehicle: Vehicle) -> set[str]:
    """Return lowercase raw identifiers useful for SQL filtering."""

    return {
        value.strip().lower()
        for value in (
            vehicle.vin,
            vehicle.registration_number,
            vehicle.fleet_number,
        )
        if value and value.strip()
    }


def _vehicle_lookup_keys(vehicle: Vehicle) -> set[str]:
    """Return normalized identifiers used to merge enrichment data."""

    return vehicle_identifier_keys(
        vehicle.vin,
        vehicle.registration_number,
        vehicle.fleet_number,
    )


def _vehicle_smart_fleet_lookup_keys(vehicle: Vehicle) -> set[str]:
    """Return normalized local identifiers used to match Smart Fleet objects."""

    return vehicle_identifier_keys(
        vehicle.vin,
        vehicle.registration_number,
        vehicle.fleet_number,
    )


def _get_latest_inspections_by_vehicle_key(
    vehicles: Iterable[Vehicle], db: Session
) -> dict[str, BusInspection]:
    """Load the latest inspection for each vehicle identifier represented in *vehicles*."""

    raw_identifiers: set[str] = set()
    for vehicle in vehicles:
        raw_identifiers.update(_vehicle_raw_identifiers(vehicle))

    if not raw_identifiers:
        return {}

    rows = (
        db.query(BusInspection)
        .filter(
            or_(
                func.lower(BusInspection.bus_id).in_(raw_identifiers),
                func.lower(BusInspection.fleet_number).in_(raw_identifiers),
            )
        )
        .order_by(BusInspection.inspection_time.desc())
        .all()
    )

    latest_by_key: dict[str, BusInspection] = {}
    for inspection in rows:
        for key in vehicle_identifier_keys(inspection.bus_id, inspection.fleet_number):
            latest_by_key.setdefault(key, inspection)
    return latest_by_key


def _first_matching_position(
    vehicle: Vehicle, positions: dict[str, SmartFleetVehiclePosition]
) -> SmartFleetVehiclePosition | None:
    for key in _vehicle_smart_fleet_lookup_keys(vehicle):
        position = positions.get(key)
        if position is not None:
            return position
    return None


def _first_matching_inspection(
    vehicle: Vehicle, inspections: dict[str, BusInspection]
) -> BusInspection | None:
    for key in _vehicle_lookup_keys(vehicle):
        inspection = inspections.get(key)
        if inspection is not None:
            return inspection
    return None


def _build_vehicle_response(
    vehicle: Vehicle,
    operator: Optional[Operator],
    smart_fleet_positions: dict[str, SmartFleetVehiclePosition] | None = None,
    latest_inspections: dict[str, BusInspection] | None = None,
) -> VehicleResponse:
    """Convert ORM vehicle rows into the API response schema."""
    smart_fleet_position = _first_matching_position(vehicle, smart_fleet_positions or {})
    latest_inspection = _first_matching_inspection(vehicle, latest_inspections or {})

    return VehicleResponse(
        vehicle_id=vehicle.vehicle_id,
        vin=vehicle.vin,
        registration_number=vehicle.registration_number,
        fleet_number=vehicle.fleet_number,
        operator_id=vehicle.operator_id,
        operator_name=vehicle.operator_name,
        # operator=OperatorSummary.model_validate(operator) if operator else None,
        make=vehicle.make,
        year=vehicle.year,
        engine_number=vehicle.engine_number,
        gvm=vehicle.gvm,
        tare=vehicle.tare,
        chassis_no=vehicle.chassis_no,
        date_of_1st_reg=vehicle.date_of_1st_reg,
        is_active=vehicle.is_active,
        created_at=vehicle.created_at,
        smart_fleet_device_id=(
            smart_fleet_position.smart_fleet_device_id
            if smart_fleet_position
            else None
        ),
        smart_fleet_last_address=(
            smart_fleet_position.last_address if smart_fleet_position else None
        ),
        smart_fleet_last_response_time=(
            smart_fleet_position.last_response_time if smart_fleet_position else None
        ),
        last_inspection_at=(
            latest_inspection.inspection_time if latest_inspection else None
        ),
        last_inspection_passed=latest_inspection.pass_ if latest_inspection else None,
    )


@vehicle_router.get(
    "/vehicles/",
    response_model=VehicleListEnvelope,
    responses={**_401, **_403, **_500},
)
async def get_vehicles(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    operator_id: Optional[int] = Query(
        None, description="Filter by operator (internal users only)"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=1, le=500, description="Results per page"),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Return a filtered, paginated list of vehicles visible to the caller."""
    try:
        app_user, operator = await _resolve_app_user(current_user, db)

        query = db.query(Vehicle, Operator).outerjoin(
            Operator, Vehicle.operator_id == Operator.operator_id
        )

        if not _is_internal(operator):
            query = query.filter(Vehicle.operator_id == app_user.operator_id)
        elif operator_id is not None:
            query = query.filter(Vehicle.operator_id == operator_id)

        if is_active is not None:
            query = query.filter(Vehicle.is_active == is_active)

        total = query.count()
        rows = (
            query.order_by(Vehicle.vehicle_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        vehicles = [vehicle for vehicle, _operator in rows]
        smart_fleet_positions = get_latest_vehicle_positions(settings)
        latest_inspections = _get_latest_inspections_by_vehicle_key(vehicles, db)

        return {
            "message": MessageResponse.success,
            "total": total,
            "page": page,
            "page_size": page_size,
            "vehicles": [
                _build_vehicle_response(
                    v,
                    op,
                    smart_fleet_positions=smart_fleet_positions,
                    latest_inspections=latest_inspections,
                )
                for v, op in rows
            ],
        }
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": MessageResponse.fail,
                "detail": f"Error retrieving vehicles: {exc}",
            },
        )


@vehicle_router.get(
    "/vehicle/{vin}",
    response_model=VehicleEnvelope,
    responses={**_401, **_404, **_500},
)
async def get_vehicle(
    vin: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Return one vehicle identified by VIN, enforcing operator scoping rules."""
    try:
        app_user, operator = await _resolve_app_user(current_user, db)

        query = (
            db.query(Vehicle, Operator)
            .outerjoin(Operator, Vehicle.operator_id == Operator.operator_id)
            .filter(Vehicle.vin == vin)
        )

        if not _is_internal(operator):
            query = query.filter(Vehicle.operator_id == app_user.operator_id)

        row = query.first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found"
            )

        vehicle, op = row
        smart_fleet_positions = get_latest_vehicle_positions(settings)
        latest_inspections = _get_latest_inspections_by_vehicle_key([vehicle], db)
        return {
            "message": MessageResponse.success,
            "vehicle": _build_vehicle_response(
                vehicle,
                op,
                smart_fleet_positions=smart_fleet_positions,
                latest_inspections=latest_inspections,
            ),
        }
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": MessageResponse.fail,
                "detail": f"Error retrieving vehicle: {exc}",
            },
        )
