from typing import List, Optional

from fastapi import Depends, HTTPException, APIRouter, Query, status
from firebase_admin import db
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user
from app.database import get_db
from app.models.app_auth import AppUser
from app.models.photo import Selfie, Photo
from app.models.shift import Shift
from app.models import BusInspection
from app.schemas.shift import (
    ShiftCreate,
    ShiftCreatedResponse,
    PhotoIn,
    SelfieIn,
    BusIn,
)

monitor_router = APIRouter()


# We store all the shifts we will be receiving from the FE for the day
@monitor_router.post("/create_shift/")
def create_shift(
    shift_data: ShiftCreate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):

    try:
        create_shif = Shift(
            user_id=current_user.firebase_uid,
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

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the shift: {str(e)}",
        )


# We add selfies captured during the shift to the selfies table, linked to the shift_id
async def add_shift_selfies(shift_id: int, selfies: List[SelfieIn], db: Session):

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
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while adding selfies: {str(e)}",
        )


async def add_inspections(shift_id: int, buses: List[BusIn], db: Session):

    try:
        for bus in buses:
            for inspection in bus.inspections:
                new_inspection = BusInspection(
                    shift_id=shift_id,
                    bus_id=bus.bus_id,
                    fleet_number=bus.bus_number,
                    internal_inspection_id=inspection.internal_inspection_id,
                    inspection_type=inspection.inspection_type,
                    inspection_time=inspection.inspection_time,
                    inspection_lat=inspection.inspection_lat,
                    inspection_lon=inspection.inspection_lon,
                    count=inspection.count,
                    pass_=inspection.pass_,
                    notes=inspection.notes,
                )
                db.add(new_inspection)
                db.flush()  # Get the ID of the newly created inspection

                # Add photos for this inspection
                for photo in inspection.photos:
                    new_photo = Photo(
                        inspection_id=new_inspection.id,
                        timestamp=photo.timestamp,
                        lat=photo.lat,
                        lon=photo.lon,
                        photo=photo.photo,
                    )
                    db.add(new_photo)

        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while adding inspections: {str(e)}",
        )
