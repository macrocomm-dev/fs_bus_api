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
from fastapi.responses import JSONResponse, Response
from firebase_admin import db
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user
from app.database import get_db
from app.models.app_auth import AppUser
from app.models.master_data import Operator, Route, Vehicle
from app.models.operations import (
    Inspection,
    InspectionPhoto,
    UserVerificationPhoto,
)
from app.models.photo import Photo, Selfie
from app.schemas.operations import (
    ErrorResponse,
    InspectionPhotoResponse,
    InspectionPhotosEnvelope,
    MessageResponse,
    PhotoUploadResponse,
)
from app.schemas.shift import DateRangeLimitQueryParams, PhotoResponse, SelfieResponse

image_router = APIRouter()

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


# Upload photo and store directly in the database
@image_router.post(
    "/upload_inspection_photo",
    status_code=status.HTTP_201_CREATED,
    response_model=PhotoUploadResponse,
    responses={
        **_401,
        **_403,
        **_500,
        413: {"model": ErrorResponse, "description": "Image exceeds size limit"},
    },
    include_in_schema=False,
)
async def upload_inspection_photo(
    file: UploadFile = File(...),
    inspection_id: int = Form(...),
    inspection_check_id: int | None = Form(None),
    date_of_inspectionphoto: datetime | None = Form(None),
    user_id: int = Form(...),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        if current_user.role not in ["Monitor", "Supervisor", "Admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to upload photos",
            )

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
            inspection_id=inspection_id,
            inspection_check_id=inspection_check_id,
            image_data=data,
            content_type=file.content_type,
            date_of_inspectionphoto=date_of_inspectionphoto,
            user_id=user_id,
        )
        db.add(new_photo)
        db.commit()
        db.refresh(new_photo)

        return {
            "message": MessageResponse.success,
            "photo_id": new_photo.photo_id,
            "inspection_id": new_photo.inspection_id,
        }
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": MessageResponse.fail,
                "detail": f"Failed to store image: {exc}",
            },
        )


# Upload photo and store directly in the database
@image_router.post(
    "/upload_user_verification_photo",
    status_code=status.HTTP_201_CREATED,
    response_model=PhotoUploadResponse,
    responses={
        **_401,
        **_403,
        **_500,
        413: {"model": ErrorResponse, "description": "Image exceeds size limit"},
    },
    include_in_schema=False,
)
async def upload_user_verification_photo(
    file: UploadFile = File(...),
    date_of_inspectionphoto: datetime | None = Form(None),
    user_id: int = Form(...),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        if current_user.role not in ["Monitor", "Supervisor", "Admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to upload photos",
            )

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

        new_photo = UserVerificationPhoto(
            image_data=data,
            content_type=file.content_type,
            date_of_verification=date_of_inspectionphoto,
            user_id=user_id,
        )
        db.add(new_photo)
        db.commit()
        db.refresh(new_photo)

        return {
            "message": MessageResponse.success,
            "photo_id": new_photo.photo_id,
            "inspection_id": new_photo.photo_id,
        }
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": MessageResponse.fail,
                "detail": f"Failed to store image: {exc}",
            },
        )


# Get inspection photos for an inspection endpoint
@image_router.get(
    "/inspection/{inspection_id}/photos",
    response_model=InspectionPhotosEnvelope,
    responses={**_401, **_500},
    include_in_schema=False,
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
                .join(Vehicle, Inspection.vehicle_id == Vehicle.vin)
                .filter(Vehicle.operator_id == app_user.operator_id)
            )
        photos = query.all()

        return {
            "message": MessageResponse.success,
            "photos": [
                InspectionPhotoResponse.model_validate(photo) for photo in photos
            ],
        }
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": MessageResponse.fail,
                "detail": f"Error retrieving inspection photos: {exc}",
            },
        )


# Download inspection photo — serves image bytes stored in the database.
@image_router.get(
    "/inspection_photo/{photo_id}/download",
    responses={
        **_401,
        **_404,
        **_500,
        200: {
            "content": {
                "image/jpeg": {},
                "image/png": {},
                "image/webp": {},
                "image/gif": {},
            }
        },
    },
    include_in_schema=False,
)
async def download_photo(
    photo_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        app_user, operator = await _resolve_app_user(current_user, db)

        query = db.query(InspectionPhoto).filter(InspectionPhoto.photo_id == photo_id)
        if not _is_internal(operator):
            query = (
                query.join(
                    Inspection,
                    InspectionPhoto.inspection_id == Inspection.inspection_id,
                )
                .join(Vehicle, Inspection.vehicle_id == Vehicle.vin)
                .filter(Vehicle.operator_id == app_user.operator_id)
            )
        photo = query.first()
        if photo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found"
            )

        return Response(content=photo.image_data, media_type=photo.content_type)
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": MessageResponse.fail,
                "detail": f"Error downloading photo: {exc}",
            },
        )


# ---------------------------------------------------------------------------
# Shift selfies
# ---------------------------------------------------------------------------


@image_router.get(
    "/selfies",
    response_model=List[SelfieResponse],
    responses={**_401, **_500},
    summary="Get all selfies",
)
async def get_all_selfies(
    params: DateRangeLimitQueryParams = Depends(),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return every selfie record across all shifts."""
    try:
        query = db.query(Selfie).order_by(Selfie.timestamp.desc())
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
                Selfie.timestamp >= start_dt,
                Selfie.timestamp <= end_dt,
            )
        if params.limit is not None:
            query = query.limit(params.limit)
        return [SelfieResponse.model_validate(s) for s in query.all()]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving selfies: {exc}",
        )


@image_router.get(
    "/selfies/shift/{shift_id}",
    response_model=List[SelfieResponse],
    responses={**_401, **_404, **_500},
    summary="Get selfies by shift ID",
)
async def get_selfies_by_shift(
    shift_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all selfies recorded during a specific shift."""
    try:
        selfies = (
            db.query(Selfie)
            .filter(Selfie.shift_id == shift_id)
            .order_by(Selfie.timestamp)
            .all()
        )
        if not selfies:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No selfies found for shift {shift_id}",
            )
        return [SelfieResponse.model_validate(s) for s in selfies]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving selfies: {exc}",
        )


# ---------------------------------------------------------------------------
# Inspection photos
# ---------------------------------------------------------------------------


@image_router.get(
    "/photos",
    response_model=List[PhotoResponse],
    responses={**_401, **_500},
    summary="Get all inspection photos",
)
async def get_all_photos(
    params: DateRangeLimitQueryParams = Depends(),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return every inspection photo record across all inspections."""
    try:
        query = db.query(Photo).order_by(Photo.timestamp.desc())
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
                Photo.timestamp >= start_dt,
                Photo.timestamp <= end_dt,
            )
        if params.limit is not None:
            query = query.limit(params.limit)
        return [PhotoResponse.model_validate(p) for p in query.all()]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving photos: {exc}",
        )


@image_router.get(
    "/photos/inspection/{inspection_id}",
    response_model=List[PhotoResponse],
    responses={**_401, **_404, **_500},
    summary="Get inspection photos by inspection ID",
)
async def get_photos_by_inspection(
    inspection_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all photos attached to a specific bus inspection."""
    try:
        photos = (
            db.query(Photo)
            .filter(Photo.inspection_id == inspection_id)
            .order_by(Photo.timestamp)
            .all()
        )
        if not photos:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No photos found for inspection {inspection_id}",
            )
        return [PhotoResponse.model_validate(p) for p in photos]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving photos: {exc}",
        )
