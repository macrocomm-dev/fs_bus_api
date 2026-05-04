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
from fastapi.responses import JSONResponse
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


# Get passenger count details endpoint
@inspection_router.get(
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
                Vehicle, PassengerCount.vehicle_id == Vehicle.vin
            ).filter(Vehicle.operator_id == app_user.operator_id)
        count = query.first()

        if count is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Passenger count not found",
            )
        return {
            "message": MessageResponse.success,
            "passenger_count": PassengerCountResponse.model_validate(count),
        }
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": MessageResponse.fail,
                "detail": f"Error retrieving passenger count: {exc}",
            },
        )


# Get passenger counts for a user endpoint
@inspection_router.get(
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
                Vehicle, PassengerCount.vehicle_id == Vehicle.vin
            ).filter(Vehicle.operator_id == app_user.operator_id)
        count = query.first()

        if count is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Passenger count not found",
            )
        return {
            "message": MessageResponse.success,
            "passenger_count": PassengerCountResponse.model_validate(count),
        }
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": MessageResponse.fail,
                "detail": f"Error retrieving passenger count: {exc}",
            },
        )


# Get inspection by id details endpoint
@inspection_router.get(
    "/inspection/{inspection_id}",
    response_model=InspectionEnvelope,
    responses={**_401, **_404, **_500},
)
async def get_inspection(
    inspection_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        app_user, operator = await _resolve_app_user(current_user, db)

        query = db.query(Inspection).filter(Inspection.inspection_id == inspection_id)
        if not _is_internal(operator):
            query = query.join(Vehicle, Inspection.vehicle_id == Vehicle.vin).filter(
                Vehicle.operator_id == app_user.operator_id
            )
        inspection = query.first()

        if inspection is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found"
            )
        return {
            "message": MessageResponse.success,
            "inspection": InspectionResponse.model_validate(inspection),
        }
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": MessageResponse.fail,
                "detail": f"Error retrieving inspection: {exc}",
            },
        )


# Get all inspections endpoint
@inspection_router.get(
    "/inspections/",
    response_model=InspectionListEnvelope,
    responses={**_401, **_404, **_500},
)
async def get_all_inspections(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        app_user, operator = await _resolve_app_user(current_user, db)

        query = db.query(Inspection)
        if not _is_internal(operator):
            query = query.join(Vehicle, Inspection.vehicle_id == Vehicle.vin).filter(
                Vehicle.operator_id == app_user.operator_id
            )
        inspections = query.all()

        if not inspections:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No inspections found"
            )
        return {
            "message": MessageResponse.success,
            "inspections": [
                InspectionResponse.model_validate(inspection)
                for inspection in inspections
            ],
        }
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": MessageResponse.fail,
                "detail": f"Error retrieving inspections: {exc}",
            },
        )


# Get inspection checks for an inspection endpoint
@inspection_router.get(
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
                .join(Vehicle, Inspection.vehicle_id == Vehicle.vin)
                .filter(Vehicle.operator_id == app_user.operator_id)
            )
        checks = query.order_by(InspectionCheck.display_order).all()

        return {
            "message": MessageResponse.success,
            "checks": [
                InspectionCheckResponse.model_validate(check) for check in checks
            ],
        }
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": MessageResponse.fail,
                "detail": f"Error retrieving inspection checks: {exc}",
            },
        )
