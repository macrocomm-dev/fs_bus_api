from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, APIRouter, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.firebase_identity import (
    FirebaseIdentityError,
    FirebaseInvalidCredentialsError,
    sign_in_with_email_password,
)
from app.auth import split_user_name
from app.models.app_auth import AppUser
from app.schemas.authentication import UserLoginRequest, UserLoginResponse

authentication_router = APIRouter()


@authentication_router.post(
    "/get_token", response_model=UserLoginResponse, include_in_schema=False
)
async def get_token(
    payload: UserLoginRequest,
    db: Session = Depends(get_db),
) -> UserLoginResponse:
    settings = get_settings()

    try:
        firebase_result = sign_in_with_email_password(
            api_key=settings.firebase_web_api_key,
            email=payload.email,
            password=payload.password,
        )
    except FirebaseInvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    except FirebaseIdentityError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Authentication service error: {exc}",
        )

    app_user = (
        db.query(AppUser)
        .filter(AppUser.firebase_uid == firebase_result.local_id)
        .first()
    )
    if app_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found. Contact an administrator.",
        )

    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=firebase_result.expires_in
    )
    name, surname = split_user_name(app_user.full_name)

    return UserLoginResponse(
        access_token=firebase_result.id_token,
        token_type="bearer",
        role=app_user.role,
        user_id=app_user.firebase_uid,
        name=app_user.name or name,
        surname=app_user.surname or surname,
        expires_at=expires_at,
    )
