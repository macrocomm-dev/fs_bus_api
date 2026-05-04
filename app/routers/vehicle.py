from datetime import datetime
from typing import List, Optional

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
from fastapi.responses import Response
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
    InspectionPhotoResponse,
    InspectionPhotosEnvelope,
    InspectionResponse,
    PassengerCountCreate,
    PassengerCountCreatedResponse,
    PassengerCountEnvelope,
    PassengerCountResponse,
    OperatorSummary,
    PhotoUploadResponse,
    RouteEnvelope,
    RouteListEnvelope,
    RouteResponse,
    VehicleEnvelope,
    VehicleListEnvelope,
    VehicleResponse,
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


ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


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


@vehicle_router.get(
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


@vehicle_router.get(
    "/vehicle/{vin}",
    response_model=VehicleEnvelope,
    responses={**_401, **_404},
)
async def get_vehicle(
    vin: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
    return {
        "message": "Vehicle retrieved successfully",
        "vehicle": _build_vehicle_response(vehicle, op),
    }
