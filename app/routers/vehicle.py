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
from sqlalchemy import func, or_, text
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
    VehicleCurrentStatusResponse,
    VehicleDataQualityResponse,
    VehicleDetailEnvelope,
    VehicleDetailResponse,
    VehicleEventDetailResponse,
    VehicleEnvelope,
    VehicleInspectionHistoryResponse,
    VehicleListEnvelope,
    VehicleResponse,
    VehicleScorePointResponse,
    VehicleTripDetailResponse,
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


def _vehicle_sql_keys(*values: object) -> list[str]:
    return sorted(vehicle_identifier_keys(*values))


def _to_float(value, default: float = 0) -> float:
    if value is None:
        return default
    return float(value)


def _to_minutes(seconds) -> float:
    return round(_to_float(seconds) / 60, 1)


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


def _event_type(event_id: int | None) -> str:
    if event_id is None:
        return "Event"
    if event_id == 99:
        return "Speeding"
    return f"Event {event_id}"


def _event_measurement(row) -> str:
    if row.max_speed is not None and row.speed_limit is not None:
        return f"{row.max_speed} km/h in {row.speed_limit} km/h zone"
    if row.max_speed is not None:
        return f"Max speed {row.max_speed} km/h"
    if row.speed is not None:
        return f"Speed {row.speed} km/h"
    if row.duration is not None:
        return f"{row.duration} seconds"
    return "-"


def _event_count_for_trip(trip, event_rows) -> int:
    """Count real analytics events that occurred inside a trip window."""

    if trip.tripstart is None or trip.tripend is None:
        return 0
    return sum(
        1
        for event in event_rows
        if event.event_date is not None and trip.tripstart <= event.event_date <= trip.tripend
    )


def _failed_checks(inspection: BusInspection) -> list[str]:
    checks: list[str] = []
    if inspection.tyres_pass is False:
        checks.append("Tyres")
    if inspection.windows_pass is False:
        checks.append("Windows")
    if inspection.ext_other_pass is False:
        checks.append("Exterior Other")
    if inspection.fire_extinguisher_present is False:
        checks.append("Fire Extinguisher")
    if inspection.seats_pass is False:
        checks.append("Seats")
    if inspection.aisle_pass is False:
        checks.append("Aisle")
    if inspection.int_other_pass is False:
        checks.append("Interior Other")
    if inspection.license_disk_scan_succeeded is False:
        checks.append("Licence Disk Scan")
    if inspection.destination_displayed is False:
        checks.append("Destination Display")
    if inspection.prdp_scan_succeeded is False:
        checks.append("PRDP Scan")
    if inspection.driver_identified is False:
        checks.append("Driver Identified")
    if inspection.pass_ is False and not checks:
        checks.append("Inspection Failed")
    return checks


def _inspection_gps(inspection: BusInspection) -> str | None:
    if inspection.inspection_lat is None or inspection.inspection_lon is None:
        return None
    return f"{inspection.inspection_lat}, {inspection.inspection_lon}"


def _matching_text_condition(column_name: str) -> str:
    return (
        "exists (select 1 from unnest(cast(:keys as text[])) as vehicle_key "
        f"where lower(regexp_replace(coalesce({column_name}, ''), '[^A-Za-z0-9]', '', 'g')) "
        "like '%' || vehicle_key || '%')"
    )


def _resolve_vehicle_by_key(
    vehicle_key: str,
    query,
) -> tuple[Vehicle, Operator | None] | None:
    keys = _vehicle_sql_keys(vehicle_key)
    if not keys:
        return None
    return query.filter(
        or_(
            func.lower(func.regexp_replace(Vehicle.vin, "[^A-Za-z0-9]", "", "g")).in_(keys),
            func.lower(
                func.regexp_replace(
                    func.coalesce(Vehicle.registration_number, ""),
                    "[^A-Za-z0-9]",
                    "",
                    "g",
                )
            ).in_(keys),
            func.lower(
                func.regexp_replace(
                    func.coalesce(Vehicle.fleet_number, ""),
                    "[^A-Za-z0-9]",
                    "",
                    "g",
                )
            ).in_(keys),
        )
    ).first()


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
    "/vehicle-detail/{vehicle_key}",
    response_model=VehicleDetailEnvelope,
    responses={**_401, **_404, **_500},
)
async def get_vehicle_detail(
    vehicle_key: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Return a complete vehicle drilldown using VIN, registration, fleet or chart label."""
    try:
        app_user, operator = await _resolve_app_user(current_user, db)

        query = db.query(Vehicle, Operator).outerjoin(
            Operator, Vehicle.operator_id == Operator.operator_id
        )

        if not _is_internal(operator):
            query = query.filter(Vehicle.operator_id == app_user.operator_id)

        row = _resolve_vehicle_by_key(vehicle_key, query)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found",
            )

        vehicle, op = row
        keys = _vehicle_sql_keys(
            vehicle.vin,
            vehicle.registration_number,
            vehicle.fleet_number,
            vehicle_key,
        )
        raw_identifiers = list(_vehicle_raw_identifiers(vehicle))

        smart_fleet_positions = get_latest_vehicle_positions(settings)
        latest_inspections = _get_latest_inspections_by_vehicle_key([vehicle], db)
        smart_fleet_position = _first_matching_position(vehicle, smart_fleet_positions)
        latest_inspection = _first_matching_inspection(vehicle, latest_inspections)
        vehicle_response = _build_vehicle_response(
            vehicle,
            op,
            smart_fleet_positions=smart_fleet_positions,
            latest_inspections=latest_inspections,
        )

        trip_rows = db.execute(
            text(
                f"""
                select
                    vehiclereg,
                    vehiclealias,
                    vehiclegroup,
                    tripstart,
                    tripend,
                    tripdur,
                    distance,
                    speeddur,
                    startloc,
                    endloc,
                    routescore,
                    stylescore,
                    riskfactor,
                    driver
                from analytics.trip_data
                where {_matching_text_condition("vehiclereg")}
                order by tripstart desc nulls last
                limit 200
                """
            ),
            {"keys": keys},
        ).mappings().all()

        event_rows = db.execute(
            text(
                f"""
                select
                    vehiclereg,
                    event_date,
                    vehiclealias,
                    vehiclegroup,
                    driver,
                    location_name,
                    event_id,
                    duration,
                    speed,
                    max_speed,
                    speed_limit
                from analytics.events
                where (
                    {_matching_text_condition("vehiclereg")}
                    or {_matching_text_condition("vin_no")}
                )
                order by event_date desc nulls last
                limit 200
                """
            ),
            {"keys": keys},
        ).mappings().all()

        bi_score_count = db.execute(
            text(
                f"""
                select count(*) as score_count
                from analytics.bi_data
                where {_matching_text_condition("vehiclereg")}
                """
            ),
            {"keys": keys},
        ).mappings().one()

        inspection_query = (
            db.query(BusInspection, AppUser)
            .outerjoin(AppUser, AppUser.firebase_uid == BusInspection.user_id)
            .filter(
                or_(
                    func.lower(BusInspection.bus_id).in_(raw_identifiers),
                    func.lower(BusInspection.fleet_number).in_(raw_identifiers),
                )
            )
            .order_by(BusInspection.inspection_time.desc())
            .limit(200)
        )
        inspection_rows = inspection_query.all()

        trips = []
        for trip in trip_rows:
            event_count = _event_count_for_trip(trip, event_rows)
            trips.append(
                VehicleTripDetailResponse(
                    trip_start=trip.tripstart,
                    trip_end=trip.tripend,
                    driver=trip.driver,
                    start_location=trip.startloc,
                    end_location=trip.endloc,
                    distance_km=round(_to_float(trip.distance), 2),
                    duration_minutes=_to_minutes(trip.tripdur),
                    speed_duration_minutes=_to_minutes(trip.speeddur),
                    route_score=round(_to_float(trip.routescore), 1)
                    if trip.routescore is not None
                    else None,
                    style_score=round(_to_float(trip.stylescore), 1)
                    if trip.stylescore is not None
                    else None,
                    risk_factor=round(_to_float(trip.riskfactor), 2)
                    if trip.riskfactor is not None
                    else None,
                    event_count=event_count,
                    high_risk=event_count >= 3,
                )
            )

        score_points = [
            VehicleScorePointResponse(
                label=(
                    trip.tripstart.strftime("%d/%m %H:%M")
                    if trip.tripstart is not None
                    else f"Trip {index + 1}"
                ),
                trip_start=trip.tripstart,
                style_score=round(_to_float(trip.stylescore), 1)
                if trip.stylescore is not None
                else None,
                route_score=round(_to_float(trip.routescore), 1)
                if trip.routescore is not None and _to_float(trip.routescore) > 0
                else None,
            )
            for index, trip in enumerate(reversed(trip_rows[:50]))
        ]

        events = [
            VehicleEventDetailResponse(
                event_time=event.event_date,
                event_type=_event_type(event.event_id),
                location=event.location_name,
                measurement=_event_measurement(event),
                driver=event.driver,
            )
            for event in event_rows
        ]

        inspection_history = [
            VehicleInspectionHistoryResponse(
                inspection_time=inspection.inspection_time,
                inspection_type=inspection.inspection_type,
                passed=inspection.pass_,
                inspector=user.full_name if user else inspection.user_id,
                notes=inspection.notes,
                failed_checks=_failed_checks(inspection),
                gps=_inspection_gps(inspection),
            )
            for inspection, user in inspection_rows
        ]

        current_status = VehicleCurrentStatusResponse(
            smart_fleet_device_id=(
                smart_fleet_position.smart_fleet_device_id
                if smart_fleet_position
                else None
            ),
            current_location=(
                smart_fleet_position.last_address if smart_fleet_position else None
            ),
            last_ping_time=(
                smart_fleet_position.last_response_time
                if smart_fleet_position
                else None
            ),
            latest_inspection_at=(
                latest_inspection.inspection_time if latest_inspection else None
            ),
            latest_inspection_type=(
                latest_inspection.inspection_type if latest_inspection else None
            ),
            latest_inspection_passed=(
                latest_inspection.pass_ if latest_inspection else None
            ),
        )

        data_quality = VehicleDataQualityResponse(
            matched_vehicle_master=True,
            matched_smart_fleet=smart_fleet_position is not None,
            matched_trip_data=len(trip_rows) > 0,
            matched_bi_data=bi_score_count.score_count > 0,
            matched_events=len(event_rows) > 0,
            matched_inspections=len(inspection_rows) > 0,
            trip_count=len(trip_rows),
            event_count=len(event_rows),
            inspection_count=len(inspection_rows),
            bi_score_count=bi_score_count.score_count,
        )

        return {
            "message": MessageResponse.success,
            "detail": VehicleDetailResponse(
                vehicle=vehicle_response,
                current_status=current_status,
                trips=trips,
                events=events,
                score_points=score_points,
                inspection_history=inspection_history,
                data_quality=data_quality,
            ),
        }
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": MessageResponse.fail,
                "detail": f"Error retrieving vehicle detail: {exc}",
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
