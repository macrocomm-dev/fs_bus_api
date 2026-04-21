"""
FS Bus API — main application entry-point.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.auth import (
    Token,
    create_access_token,
    get_current_user,
    TokenData,
)
from app.config import Settings, get_settings

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FS Bus API",
    description="API for capturing data for the FS bus tracking application.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


def _get_cors_origins(settings: Settings) -> list[str]:
    return [o.strip() for o in settings.cors_origins.split(",") if o.strip()]


@app.on_event("startup")
def configure_cors() -> None:
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_get_cors_origins(settings),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ---------------------------------------------------------------------------
# Auth router
# ---------------------------------------------------------------------------

from fastapi import APIRouter
from fastapi.security import OAuth2PasswordRequestForm

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/token", response_model=Token, summary="Obtain an access token")
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Exchange credentials for a JWT Bearer token.

    **Note:** This endpoint is a development convenience.  Replace the stub
    user-lookup below with a real database query and password verification
    before deploying to production.

    In production, tokens may also be issued by an external OAuth2 identity
    provider; this API validates them via the ``Authorization: Bearer`` scheme.
    """
    # TODO: look up the user in the database and verify credentials.
    # Example:
    #   user = db.query(User).filter(User.username == form_data.username).first()
    #   if not user or not verify_password(form_data.password, user.hashed_password):
    #       raise HTTPException(status_code=400, detail="Incorrect username or password")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "User authentication is not yet configured. "
            "Implement user lookup in app/main.py login()."
        ),
    )
    # Once user lookup is implemented, replace the raise above with:
    # access_token = create_access_token(data={"sub": user.username}, settings=settings)
    # return Token(access_token=access_token, token_type="bearer")


app.include_router(auth_router)

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["health"], summary="Health check")
def health():
    """Returns ``{"status": "ok"}`` when the service is running."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Protected example route
# ---------------------------------------------------------------------------


@app.get("/me", tags=["users"], summary="Current authenticated user")
def read_current_user(
    current_user: Annotated[TokenData, Depends(get_current_user)],
):
    """Return the identity of the currently authenticated caller."""
    return {"sub": current_user.sub}
