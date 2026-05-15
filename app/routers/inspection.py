from datetime import datetime
from typing import List, Optional

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
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user
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
from app.schemas.shift import BusInspectionResponse, DateRangeLimitQueryParams

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
    if params.daterange:
        try:
            start_str, end_str = params.daterange.split(",")
            start_dt = datetime.strptime(start_str.strip(), "%Y-%m-%d")
            end_dt = datetime.strptime(end_str.strip(), "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="daterange must be in the format 'YYYY-MM-DD,YYYY-MM-DD'",
            )
        query = query.filter(
            BusInspection.inspection_time >= start_dt,
            BusInspection.inspection_time <= end_dt,
        )
    if params.limit is not None:
        query = query.limit(params.limit)
    return query


@inspection_router.get(
    "/bus_inspections",
    response_model=List[BusInspectionResponse],
    responses={**_401, **_500},
    summary="Get all bus inspections with optional date range and limit",
)
async def get_all_bus_inspections(
    params: DateRangeLimitQueryParams = Depends(),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    try:
        query = db.query(BusInspection)
        query = _apply_date_range_limit(query, params)
        return query.all()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching inspections: {exc}",
        )


@inspection_router.get(
    "/bus_inspections/by_shift/{shift_id}",
    response_model=List[BusInspectionResponse],
    responses={**_401, **_404, **_500},
    summary="Get bus inspections by shift ID with optional date range and limit",
)
async def get_bus_inspections_by_shift(
    shift_id: int = Path(description="ID of the shift to retrieve inspections for"),
    params: DateRangeLimitQueryParams = Depends(),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    try:
        query = db.query(BusInspection).filter(BusInspection.shift_id == shift_id)
        query = _apply_date_range_limit(query, params)
        results = query.all()
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No inspections found for shift {shift_id}",
            )
        return results
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching inspections for shift {shift_id}: {exc}",
        )


@inspection_router.get(
    "/bus_inspections/by_bus/{bus_id}",
    response_model=List[BusInspectionResponse],
    responses={**_401, **_404, **_500},
    summary="Get bus inspections by bus ID/Vin number with optional date range and limit",
)
async def get_bus_inspections_by_bus(
    bus_id: str = Path(description="Vehicle VIN / bus_id to retrieve inspections for"),
    params: DateRangeLimitQueryParams = Depends(),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    try:
        query = db.query(BusInspection).filter(BusInspection.bus_id == bus_id)
        query = _apply_date_range_limit(query, params)
        results = query.all()
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No inspections found for bus {bus_id}",
            )
        return results
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching inspections for bus {bus_id}: {exc}",
        )


@inspection_router.get(
    "/bus_inspections/by_user/{user_id}",
    response_model=List[BusInspectionResponse],
    responses={**_401, **_404, **_500},
    summary="Get bus inspections by user ID with optional date range and limit",
)
async def get_bus_inspections_by_user(
    user_id: str = Path(
        description="User ID of the monitor who recorded the inspections"
    ),
    params: DateRangeLimitQueryParams = Depends(),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    try:
        query = db.query(BusInspection).filter(BusInspection.user_id == user_id)
        query = _apply_date_range_limit(query, params)
        results = query.all()
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No inspections found for user {user_id}",
            )
        return results
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching inspections for user {user_id}: {exc}",
        )
