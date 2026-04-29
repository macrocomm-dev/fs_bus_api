from typing import List

from fastapi import Depends, HTTPException, APIRouter, status
from firebase_admin import db
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user
from app.database import get_db
from app.models.app_auth import AppUser
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
            count_type=payload.count_type,
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
    inspection = (
        db.query(Inspection).filter(Inspection.inspection_id == inspection_id).first()
    )
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
    inspections = db.query(Inspection).all()
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

        checks = (
            db.query(InspectionCheck)
            .filter(InspectionCheck.inspection_id == inspection_id)
            .order_by(InspectionCheck.display_order)
            .all()
        )
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
        photos = (
            db.query(InspectionPhoto)
            .filter(InspectionPhoto.inspection_id == inspection_id)
            .all()
        )
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
        count = (
            db.query(PassengerCount).filter(PassengerCount.count_id == count_id).first()
        )
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
        count = (
            db.query(PassengerCount).filter(PassengerCount.user_id == user_id).first()
        )
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
