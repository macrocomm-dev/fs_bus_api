from typing import List, Optional

import base64
from fastapi import Depends, HTTPException, APIRouter, Query, Request, Form, status
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
    ShiftCreateMeta,
    ShiftCreatedResponse,
    PhotoIn,
    SelfieIn,
    BusIn,
)

monitor_router = APIRouter()


# We store all the shifts we will be receiving from the FE for the day
@monitor_router.post("/create_shift/")
async def create_shift(
    shift_data: ShiftCreate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):

    try:
        create_shif = Shift(
            user_id=shift_data.user_id,
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
        selfies = await add_shift_selfies(create_shif.id, shift_data.selfies, db)
        inspections = await add_inspections(create_shif.id, shift_data.busses, db)
        if selfies and inspections:
            return ShiftCreatedResponse(shift_id=create_shif.id, message="success")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while processing selfies or inspections",
            )

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
                    tyres_pass=inspection.tyres_pass,
                    tyres_notes=inspection.tyres_notes,
                    windows_pass=inspection.windows_pass,
                    windows_notes=inspection.windows_notes,
                    ext_other_pass=inspection.ext_other_pass,
                    ext_other_notes=inspection.ext_other_notes,
                    seats_pass=inspection.seats_pass,
                    seats_notes=inspection.seats_notes,
                    aisle_pass=inspection.aisle_pass,
                    aisle_notes=inspection.aisle_notes,
                    int_other_pass=inspection.int_other_pass,
                    int_other_notes=inspection.int_other_notes,
                    number_seated=inspection.number_seated,
                    number_standing=inspection.number_standing,
                    behind_schedule_interval=inspection.behind_schedule_interval,
                    license_disk_scan_succeeded=bus.license_disk_scan_succeeded,
                    destination_displayed=bus.destination_displayed,
                    prdp_scan_succeeded=bus.prdp_scan_succeeded,
                    prdp_expiry_date=bus.prdp_expiry_date,
                    driver_identified=bus.driver_identified,
                    driver_fail_reason=bus.driver_fail_reason,
                    driver=bus.driver,
                )
                db.add(new_inspection)
                db.flush()  # Get the ID of the newly created inspection
                db.refresh(new_inspection)

                # Add photos for this inspection
                for photo in inspection.photos:
                    new_photo = Photo(
                        inspection_id=new_inspection.id,
                        timestamp=photo.timestamp,
                        lat=photo.lat,
                        lon=photo.lon,
                        inspection_item=photo.inspection_item,
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


# ---------------------------------------------------------------------------
# Multipart version
#
# Send as multipart/form-data:
#   data          — JSON string of ShiftCreateMeta (no photo bytes)
#   selfie_{i}    — image file for selfies[i]
#   bus_{i}_inspection_{j}_photo_{k} — image file for that photo
# ---------------------------------------------------------------------------


@monitor_router.post("/create_shift_multipart/")
async def create_shift_multipart(
    request: Request,
    data: str = Form(...),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    try:
        shift_data = ShiftCreateMeta.model_validate_json(data)
        form = await request.form()

        new_shift = Shift(
            user_id=shift_data.user_id,
            start_time=shift_data.start_time,
            end_time=shift_data.end_time,
            start_lat=shift_data.start_lat,
            start_lon=shift_data.start_lon,
            end_lat=shift_data.end_lat,
            end_lon=shift_data.end_lon,
            device_id=shift_data.device_id,
        )
        db.add(new_shift)
        db.commit()
        db.refresh(new_shift)

        # Selfies — file key: selfie_{i}
        for i, selfie in enumerate(shift_data.selfies):
            file = form.get(f"selfie_{i}")
            if file is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Missing file: selfie_{i}",
                )
            photo_bytes = await file.read()
            db.add(
                Selfie(
                    shift_id=new_shift.id,
                    timestamp=selfie.timestamp,
                    lat=selfie.lat,
                    lon=selfie.lon,
                    photo=base64.b64encode(photo_bytes).decode(),
                )
            )

        # Inspections + photos — file key: bus_{i}_inspection_{j}_photo_{k}
        for i, bus in enumerate(shift_data.busses):
            for j, inspection in enumerate(bus.inspections):
                new_inspection = BusInspection(
                    shift_id=new_shift.id,
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
                    tyres_pass=inspection.tyres_pass,
                    tyres_notes=inspection.tyres_notes,
                    windows_pass=inspection.windows_pass,
                    windows_notes=inspection.windows_notes,
                    ext_other_pass=inspection.ext_other_pass,
                    ext_other_notes=inspection.ext_other_notes,
                    seats_pass=inspection.seats_pass,
                    seats_notes=inspection.seats_notes,
                    aisle_pass=inspection.aisle_pass,
                    aisle_notes=inspection.aisle_notes,
                    int_other_pass=inspection.int_other_pass,
                    int_other_notes=inspection.int_other_notes,
                    number_seated=inspection.number_seated,
                    number_standing=inspection.number_standing,
                    behind_schedule_interval=inspection.behind_schedule_interval,
                    license_disk_scan_succeeded=bus.license_disk_scan_succeeded,
                    destination_displayed=bus.destination_displayed,
                    prdp_scan_succeeded=bus.prdp_scan_succeeded,
                    prdp_expiry_date=bus.prdp_expiry_date,
                    driver_identified=bus.driver_identified,
                    driver_fail_reason=bus.driver_fail_reason,
                    driver=bus.driver,
                )
                db.add(new_inspection)
                db.flush()
                db.refresh(new_inspection)

                for k, photo_meta in enumerate(inspection.photos):
                    file = form.get(f"bus_{i}_inspection_{j}_photo_{k}")
                    if file is None:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Missing file: bus_{i}_inspection_{j}_photo_{k}",
                        )
                    photo_bytes = await file.read()
                    db.add(
                        Photo(
                            inspection_id=new_inspection.id,
                            timestamp=photo_meta.timestamp,
                            lat=photo_meta.lat,
                            lon=photo_meta.lon,
                            inspection_item=photo_meta.inspection_item,
                            photo=base64.b64encode(photo_bytes).decode(),
                        )
                    )

        db.commit()
        return ShiftCreatedResponse(shift_id=new_shift.id, message="success")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the shift: {str(e)}",
        )
