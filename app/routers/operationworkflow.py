from typing import List, Optional

from fastapi import Depends, HTTPException, APIRouter, Query, status
from firebase_admin import db
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user
from app.database import get_db
from app.models.app_auth import AppUser
from app.models.master_data import Operator, Route, Vehicle
from app.models.operations import (
    Inspection,
    InspectionCheck,
    InspectionPhoto,
    PassengerCount,
)
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
    InspectionPhotoCreate,
    InspectionPhotoCreatedResponse,
    InspectionPhotoResponse,
    InspectionPhotosEnvelope,
    InspectionResponse,
    PassengerCountCreate,
    PassengerCountCreatedResponse,
    PassengerCountEnvelope,
    PassengerCountResponse,
    OperatorSummary,
    RouteEnvelope,
    RouteListEnvelope,
    RouteResponse,
    VehicleEnvelope,
    VehicleListEnvelope,
    VehicleResponse,
)

operation_router = APIRouter()

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
    app_user = (
        db.query(AppUser).filter(AppUser.firebase_uid == current_user.sub).first()
    )
    if app_user is None:
        app_user = AppUser(
            firebase_uid=current_user.sub,
            email=current_user.email,
            full_name=current_user.name,
            role=current_user.role,
            is_active=True,
        )
        db.add(app_user)
        db.commit()
        db.refresh(app_user)
    return app_user.user_id


# Placeholder function for photo storage - in real implementation, this would handle uploading to a service like AWS S3 or Google Cloud Storage and return the URL
async def add_photo_to_storage(photo_data: bytes) -> str:

    return "https://storage.example.com/path/to/photo.jpg"


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
@operation_router.post(
    "/create_inspection",
    status_code=status.HTTP_201_CREATED,
    response_model=InspectionCreatedResponse,
    responses={**_401, **_403},
)
async def create_inspection(
    payload: InspectionCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ["Monitor", "Supervisor", "Admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create inspections",
        )

    # Resolve Firebase UID → DB user_id, auto-provisioning on first login
    app_user = (
        db.query(AppUser).filter(AppUser.firebase_uid == current_user.sub).first()
    )
    if app_user is None:
        app_user = await get_user_id_from_token(current_user, db)

    new_inspection = Inspection(
        vehicle_id=payload.vehicle_id,
        route_id=payload.route_id,
        route_text=payload.route_text,
        user_id=app_user.user_id,
        inspection_type=payload.inspection_type,
        latitude=payload.latitude,
        longitude=payload.longitude,
        notes=payload.notes,
        status=payload.status,
    )
    db.add(new_inspection)
    db.commit()
    db.refresh(new_inspection)

    return {
        "message": "Inspection created successfully",
        "inspection_id": new_inspection.inspection_id,
        "vehicle_id": new_inspection.vehicle_id,
        "route_id": new_inspection.route_id,
    }


# Add inspection check endpoint, only accessible to Monitor, Supervisor, Admin roles
@operation_router.post(
    "/inspection_check",
    status_code=status.HTTP_201_CREATED,
    response_model=InspectionCheckCreatedResponse,
    responses={**_401, **_500},
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
        )
        db.add(new_check)
        db.commit()
        db.refresh(new_check)

        return {
            "message": "Inspection check added successfully",
            "inspection_check_id": new_check.inspection_check_id,
            "inspection_id": new_check.inspection_id,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding inspection check: {exc}",
        )


# Add inspection photo endpoint
@operation_router.post(
    "/inspection_photo",
    status_code=status.HTTP_201_CREATED,
    response_model=InspectionPhotoCreatedResponse,
    responses={**_401, **_500},
)
async def add_inspection_photo(
    payload: InspectionPhotoCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        new_photo = InspectionPhoto(
            inspection_id=payload.inspection_id,
            inspection_check_id=payload.inspection_check_id,
            storage_url=payload.storage_url,
        )
        db.add(new_photo)
        db.commit()
        db.refresh(new_photo)

        return {
            "message": "Inspection photo added successfully",
            "photo_id": new_photo.photo_id,
            "inspection_id": new_photo.inspection_id,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding inspection photo: {exc}",
        )


# Add passenger count endpoint
@operation_router.post(
    "/passenger_count",
    status_code=status.HTTP_201_CREATED,
    response_model=PassengerCountCreatedResponse,
    responses={**_401, **_500},
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
            user_id=await get_user_id_from_token(current_user, db),
            passenger_count=payload.count,
            latitude=payload.latitude,
            longitude=payload.longitude,
            notes=payload.notes,
        )
        db.add(new_count)
        db.commit()
        db.refresh(new_count)

        return {
            "message": "Passenger count added successfully",
            "count_id": new_count.count_id,
            "vehicle_id": new_count.vehicle_id,
            "route_id": new_count.route_id,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding passenger count: {exc}",
        )


# Get inspection by id details endpoint
@operation_router.get(
    "/inspection/{inspection_id}",
    response_model=InspectionEnvelope,
    responses={**_401, **_404},
)
async def get_inspection(
    inspection_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app_user, operator = await _resolve_app_user(current_user, db)

    query = db.query(Inspection).filter(Inspection.inspection_id == inspection_id)
    if not _is_internal(operator):
        query = query.join(Vehicle, Inspection.vehicle_id == Vehicle.vehicle_id).filter(
            Vehicle.operator_id == app_user.operator_id
        )
    inspection = query.first()

    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found"
        )
    return {
        "message": "Inspection retrieved successfully",
        "inspection": InspectionResponse.model_validate(inspection),
    }


# Get all inspections endpoint
@operation_router.get(
    "/inspections/",
    response_model=InspectionListEnvelope,
    responses={**_401, **_404},
)
async def get_all_inspections(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app_user, operator = await _resolve_app_user(current_user, db)

    query = db.query(Inspection)
    if not _is_internal(operator):
        query = query.join(Vehicle, Inspection.vehicle_id == Vehicle.vehicle_id).filter(
            Vehicle.operator_id == app_user.operator_id
        )
    inspections = query.all()

    if not inspections:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No inspections found"
        )
    return {
        "message": "Inspections retrieved successfully",
        "inspections": [
            InspectionResponse.model_validate(inspection) for inspection in inspections
        ],
    }


# Get inspection checks for an inspection endpoint
@operation_router.get(
    "/inspection/{inspection_id}/checks",
    response_model=InspectionChecksEnvelope,
    responses={**_401, **_500},
)
async def get_inspection_checks(
    inspection_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        app_user, operator = await _resolve_app_user(current_user, db)

        query = db.query(InspectionCheck).filter(
            InspectionCheck.inspection_id == inspection_id
        )
        if not _is_internal(operator):
            query = (
                query.join(
                    Inspection,
                    InspectionCheck.inspection_id == Inspection.inspection_id,
                )
                .join(Vehicle, Inspection.vehicle_id == Vehicle.vehicle_id)
                .filter(Vehicle.operator_id == app_user.operator_id)
            )
        checks = query.order_by(InspectionCheck.display_order).all()

        return {
            "message": "Inspection checks retrieved successfully",
            "checks": [
                InspectionCheckResponse.model_validate(check) for check in checks
            ],
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving inspection checks: {exc}",
        )


# Get inspection photos for an inspection endpoint
@operation_router.get(
    "/inspection/{inspection_id}/photos",
    response_model=InspectionPhotosEnvelope,
    responses={**_401, **_500},
)
async def get_inspection_photos(
    inspection_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        app_user, operator = await _resolve_app_user(current_user, db)

        query = db.query(InspectionPhoto).filter(
            InspectionPhoto.inspection_id == inspection_id
        )
        if not _is_internal(operator):
            query = (
                query.join(
                    Inspection,
                    InspectionPhoto.inspection_id == Inspection.inspection_id,
                )
                .join(Vehicle, Inspection.vehicle_id == Vehicle.vehicle_id)
                .filter(Vehicle.operator_id == app_user.operator_id)
            )
        photos = query.all()

        return {
            "message": "Inspection photos retrieved successfully",
            "photos": [
                InspectionPhotoResponse.model_validate(photo) for photo in photos
            ],
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving inspection photos: {exc}",
        )


# Get passenger count details endpoint
@operation_router.get(
    "/passenger_count/{count_id}",
    response_model=PassengerCountEnvelope,
    responses={**_401, **_404, **_500},
)
async def get_passenger_count(
    count_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        app_user, operator = await _resolve_app_user(current_user, db)

        query = db.query(PassengerCount).filter(PassengerCount.count_id == count_id)
        if not _is_internal(operator):
            query = query.join(
                Vehicle, PassengerCount.vehicle_id == Vehicle.vehicle_id
            ).filter(Vehicle.operator_id == app_user.operator_id)
        count = query.first()

        if count is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Passenger count not found",
            )
        return {
            "message": "Passenger count retrieved successfully",
            "passenger_count": PassengerCountResponse.model_validate(count),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving passenger count: {exc}",
        )


# Get passenger counts for a user endpoint
@operation_router.get(
    "/passenger_count_user/{user_id}",
    response_model=PassengerCountEnvelope,
    responses={**_401, **_404, **_500},
)
async def get_passenger_count_user_user(
    user_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        app_user, operator = await _resolve_app_user(current_user, db)

        query = db.query(PassengerCount).filter(PassengerCount.user_id == user_id)
        if not _is_internal(operator):
            query = query.join(
                Vehicle, PassengerCount.vehicle_id == Vehicle.vehicle_id
            ).filter(Vehicle.operator_id == app_user.operator_id)
        count = query.first()

        if count is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Passenger count not found",
            )
        return {
            "message": "Passenger count retrieved successfully",
            "passenger_count": PassengerCountResponse.model_validate(count),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving passenger count: {exc}",
        )


# ── Master data: vehicles ─────────────────────────────────────────────────────


def _build_vehicle_response(
    vehicle: Vehicle, operator: Optional[Operator]
) -> VehicleResponse:
    return VehicleResponse(
        vehicle_id=vehicle.vehicle_id,
        vin=vehicle.vin,
        registration_number=vehicle.registration_number,
        fleet_number=vehicle.fleet_number,
        operator_id=vehicle.operator_id,
        operator_name=vehicle.operator_name,
        operator=OperatorSummary.model_validate(operator) if operator else None,
        make=vehicle.make,
        year=vehicle.year,
        engine_number=vehicle.engine_number,
        gvm=vehicle.gvm,
        tare=vehicle.tare,
        chassis_no=vehicle.chassis_no,
        date_of_1st_reg=vehicle.date_of_1st_reg,
        is_active=vehicle.is_active,
        created_at=vehicle.created_at,
    )


def _build_route_response(route: Route, operator: Optional[Operator]) -> RouteResponse:
    return RouteResponse(
        route_id=route.route_id,
        route_code=route.route_code,
        route_name=route.route_name,
        operator_id=route.operator_id,
        operator_name=route.operator_name,
        operator=OperatorSummary.model_validate(operator) if operator else None,
        description=route.description,
        is_active=route.is_active,
        created_at=route.created_at,
    )


@operation_router.get(
    "/vehicles/",
    response_model=VehicleListEnvelope,
    responses={**_401, **_403},
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
):
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

    return {
        "message": "Vehicles retrieved successfully",
        "total": total,
        "page": page,
        "page_size": page_size,
        "vehicles": [_build_vehicle_response(v, op) for v, op in rows],
    }


@operation_router.get(
    "/vehicle/{vehicle_id}",
    response_model=VehicleEnvelope,
    responses={**_401, **_404},
)
async def get_vehicle(
    vehicle_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app_user, operator = await _resolve_app_user(current_user, db)

    query = (
        db.query(Vehicle, Operator)
        .outerjoin(Operator, Vehicle.operator_id == Operator.operator_id)
        .filter(Vehicle.vehicle_id == vehicle_id)
    )

    if not _is_internal(operator):
        query = query.filter(Vehicle.operator_id == app_user.operator_id)

    row = query.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found"
        )

    vehicle, op = row
    return {
        "message": "Vehicle retrieved successfully",
        "vehicle": _build_vehicle_response(vehicle, op),
    }


# ── Master data: routes ───────────────────────────────────────────────────────


@operation_router.get(
    "/routes/",
    response_model=RouteListEnvelope,
    responses={**_401, **_403},
)
async def get_routes(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    operator_id: Optional[int] = Query(
        None, description="Filter by operator (internal users only)"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=1, le=500, description="Results per page"),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app_user, operator = await _resolve_app_user(current_user, db)

    query = db.query(Route, Operator).outerjoin(
        Operator, Route.operator_id == Operator.operator_id
    )

    if not _is_internal(operator):
        query = query.filter(Route.operator_id == app_user.operator_id)
    elif operator_id is not None:
        query = query.filter(Route.operator_id == operator_id)

    if is_active is not None:
        query = query.filter(Route.is_active == is_active)

    total = query.count()
    rows = (
        query.order_by(Route.route_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "message": "Routes retrieved successfully",
        "total": total,
        "page": page,
        "page_size": page_size,
        "routes": [_build_route_response(r, op) for r, op in rows],
    }


@operation_router.get(
    "/route/{route_id}",
    response_model=RouteEnvelope,
    responses={**_401, **_404},
)
async def get_route(
    route_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app_user, operator = await _resolve_app_user(current_user, db)

    query = (
        db.query(Route, Operator)
        .outerjoin(Operator, Route.operator_id == Operator.operator_id)
        .filter(Route.route_id == route_id)
    )

    if not _is_internal(operator):
        query = query.filter(Route.operator_id == app_user.operator_id)

    row = query.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Route not found"
        )

    route, op = row
    return {
        "message": "Route retrieved successfully",
        "route": _build_route_response(route, op),
    }
