from fastapi import Depends, HTTPException, APIRouter, status
from fastapi.responses import Response
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
    InspectionCheckCreate,
    InspectionCreate,
    InspectionPhotoCreate,
    PassengerCountCreate,
)


operation_router = APIRouter()


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


# create inspection endpoint, only accessible to Monitor, Supervisor, Admin roles. Auto-provision user on first login based on Firebase UID → DB user_id mapping
@operation_router.post("/create_inspection", status_code=status.HTTP_201_CREATED)
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

    return Response(status_code=status.HTTP_201_CREATED)


# Add inspection check endpoint, only accessible to Monitor, Supervisor, Admin roles
@operation_router.post("/inspection_check")
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

        return Response(status_code=status.HTTP_201_CREATED)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding inspection check: {exc}",
        )


# Add inspection photo endpoint
@operation_router.post("/inspection_photo")
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

        return Response(status_code=status.HTTP_201_CREATED)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding inspection photo: {exc}",
        )


# Add passenger count endpoint
@operation_router.post("/passenger_count")
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

        return Response(status_code=status.HTTP_201_CREATED)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding passenger count: {exc}",
        )
