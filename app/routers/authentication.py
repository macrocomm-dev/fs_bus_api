from fastapi import Depends, HTTPException, APIRouter, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.firebase_identity import (
    FirebaseIdentityError,
    FirebaseInvalidCredentialsError,
    sign_in_with_email_password,
)
from app.models.app_auth import AppUser
from app.schemas.authentication import UserLoginRequest, UserLoginResponse

authentication_router = APIRouter()


@authentication_router.post("/get_token", response_model=UserLoginResponse)
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

    return UserLoginResponse(
        access_token=firebase_result.id_token,
        token_type="bearer",
        role=app_user.role,
        user_id=app_user.user_id,
    )
