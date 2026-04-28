from fastapi import Depends, HTTPException, APIRouter, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user
from app.database import get_db
from app.models.app_auth import AppUser
from app.models.operations import Inspection, InspectionCheck, InspectionPhoto
from app.schemas.operations import InspectionCreate


operation_router = APIRouter()


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


@operation_router.post("/inspection_check")
async def add_inspection_check():
    pass
