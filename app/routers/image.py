from datetime import date, datetime, time
from typing import Annotated, List, Optional

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
from app.schemas.shift import DateRangeLimitQueryParams, PhotoResponse, SelfieResponse, date_range_params

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
    inspection_id: int = Path(
        description="ID of the bus inspection to retrieve photos for"
    ),
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
    photo_id: int = Path(description="ID of the inspection photo to download"),
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
    summary="Get all selfies with optional date range and limit",
)
async def get_all_selfies(
    params: DateRangeLimitQueryParams = Depends(date_range_params),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return every selfie record across all shifts."""
    try:
        query = db.query(Selfie).order_by(Selfie.timestamp.desc())
        if params.start_date:
            start_dt = datetime.combine(
                params.start_date, params.start_time or time.min
            )
            query = query.filter(Selfie.timestamp >= start_dt)
        if params.end_date:
            end_dt = datetime.combine(
                params.end_date, params.end_time or time(23, 59, 59)
            )
            query = query.filter(Selfie.timestamp <= end_dt)
        if params.limit is not None:
            query = query.limit(params.limit)
        return [SelfieResponse.model_validate(s) for s in query.all()]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving selfies: {exc}",
        )


@image_router.get(
    "/selfies/by_shift_ids",
    response_model=List[SelfieResponse],
    responses={**_401, **_404, **_500},
    summary="Get selfies by shift IDs",
)
async def get_selfies_by_shift(
    shift_ids: List[int] = Query(
        ..., description="One or more shift IDs to retrieve selfies for"
    ),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all selfies recorded during the specified shifts. At least one ID is required."""
    if not shift_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one shift ID must be provided",
        )
    try:
        selfies = (
            db.query(Selfie)
            .filter(Selfie.shift_id.in_(shift_ids))
            .order_by(Selfie.timestamp)
            .all()
        )
        if not selfies:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No selfies found for the provided shift IDs",
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
    summary="Get all inspection photos with optional date range and limit",
)
async def get_all_photos(
    params: DateRangeLimitQueryParams = Depends(date_range_params),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return every inspection photo record across all inspections with optional date range and limit."""
    try:
        query = db.query(Photo).order_by(Photo.timestamp.desc())
        if params.start_date:
            start_dt = datetime.combine(
                params.start_date, params.start_time or time.min
            )
            query = query.filter(Photo.timestamp >= start_dt)
        if params.end_date:
            end_dt = datetime.combine(
                params.end_date, params.end_time or time(23, 59, 59)
            )
            query = query.filter(Photo.timestamp <= end_dt)
        if params.limit is not None:
            query = query.limit(params.limit)
        return [PhotoResponse.model_validate(p) for p in query.all()]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving photos: {exc}",
        )


@image_router.get(
    "/photos/by_inspection_ids",
    response_model=List[PhotoResponse],
    responses={**_401, **_404, **_500},
    summary="Get inspection photos by inspection IDs",
)
async def get_photos_by_inspection(
    inspection_ids: List[int] = Query(
        ..., description="One or more inspection IDs to retrieve photos for"
    ),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all photos attached to the specified bus inspections. At least one ID is required."""
    if not inspection_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one inspection ID must be provided",
        )
    try:
        photos = (
            db.query(Photo)
            .filter(Photo.inspection_id.in_(inspection_ids))
            .order_by(Photo.timestamp)
            .all()
        )
        if not photos:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No photos found for the provided inspection IDs",
            )
        return [PhotoResponse.model_validate(p) for p in photos]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving photos: {exc}",
        )
