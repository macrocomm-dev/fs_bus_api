"""
FS Bus API — main application entry-point.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.exception_handlers import (
    http_exception_handler as _default_http_handler,
    request_validation_exception_handler as _default_validation_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.auth import (
    decode_access_token,
    expand_role_permissions,
    get_current_user,
    normalize_role,
    split_user_name,
    TokenData,
)
from app.config import Settings, get_settings
from app.firebase_identity import (
    FirebaseIdentityError,
    FirebaseInvalidCredentialsError,
    FirebasePasswordSignInRequest,
    FirebasePasswordSignInResult,
    FirebaseRefreshRequest,
    FirebaseRefreshResult,
    refresh_id_token,
    sign_in_with_email_password,
)
from app.database import get_db
from app.models.app_auth import AppUser
from app.routers.router_config import register_routers
from app.schemas.authentication import UserRefreshResponse
from app.services.audit_service import log_api_error
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FS Bus API",
    description="API for capturing data for the FS bus tracking application.",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.openapi_version = "3.0.3"


def _get_cors_origins(settings: Settings) -> list[str]:
    return [o.strip() for o in settings.cors_origins.split(",") if o.strip()]


# ---------------------------------------------------------------------------
# Exception handlers — log every error to audit.api_error_log
# ---------------------------------------------------------------------------


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    await log_api_error(
        request=request,
        status_code=exc.status_code,
        error_category="HTTP_ERROR",
        error_message=str(exc.detail),
        error_code=str(exc.status_code),
        exc=exc,
    )
    return await _default_http_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    await log_api_error(
        request=request,
        status_code=422,
        error_category="VALIDATION_ERROR",
        error_message="Request validation failed",
        error_code="VALIDATION_ERROR",
        validation_errors={"errors": exc.errors()},
        exc=exc,
    )
    return await _default_validation_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    await log_api_error(
        request=request,
        status_code=500,
        error_category="INTERNAL_ERROR",
        error_message=str(exc),
        error_code=type(exc).__name__,
        exc=exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


register_routers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(get_settings()),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth router
# ---------------------------------------------------------------------------

auth_router = APIRouter(prefix="/auth", tags=["auth"])
DOCS_TEMPLATE_PATH = Path(__file__).with_name("templates") / "docs.html"
SWAGGER_UI_CSS_CDN = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"
SWAGGER_UI_BUNDLE_CDN = (
    "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"
)


def _get_local_swagger_ui_dir() -> Path | None:
    try:
        import swagger_ui_bundle  # noqa: PLC0415
    except ImportError:
        return None

    package_dir = Path(swagger_ui_bundle.__file__).resolve().parent
    vendor_root = package_dir / "vendor"
    candidates = sorted(vendor_root.glob("swagger-ui-*"))
    if not candidates:
        return None
    return candidates[-1]


LOCAL_SWAGGER_UI_DIR = _get_local_swagger_ui_dir()

if LOCAL_SWAGGER_UI_DIR is not None:
    app.mount(
        "/_static/swagger-ui",
        StaticFiles(directory=str(LOCAL_SWAGGER_UI_DIR)),
        name="swagger-ui-static",
    )


def _serialize_user(current_user: TokenData) -> dict[str, object]:
    return {
        "sub": current_user.sub,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
        "permissions": list(expand_role_permissions(current_user.role)),
    }


def _require_docs_user(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenData:
    required_role = normalize_role(settings.docs_required_role)
    if required_role is None:
        return current_user
    if required_role not in expand_role_permissions(current_user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return current_user


@lru_cache
def _load_docs_template() -> str:
    return DOCS_TEMPLATE_PATH.read_text(encoding="utf-8")


def _build_docs_html(settings: Settings) -> str:
    required_role = escape(settings.docs_required_role or "any authenticated user")
    test_auth_enabled = settings.enable_test_auth_endpoints
    swagger_ui_css_url = (
        "/_static/swagger-ui/swagger-ui.css"
        if LOCAL_SWAGGER_UI_DIR is not None
        else SWAGGER_UI_CSS_CDN
    )
    swagger_ui_bundle_url = (
        "/_static/swagger-ui/swagger-ui-bundle.js"
        if LOCAL_SWAGGER_UI_DIR is not None
        else SWAGGER_UI_BUNDLE_CDN
    )
    return (
        _load_docs_template()
        .replace("__APP_TITLE__", escape(app.title))
        .replace("__REQUIRED_ROLE__", required_role)
        .replace("__SWAGGER_UI_CSS_URL__", swagger_ui_css_url)
        .replace("__SWAGGER_UI_BUNDLE_URL__", swagger_ui_bundle_url)
        .replace(
            "__TEST_AUTH_SECTION_CLASS__",
            "" if test_auth_enabled else "hidden",
        )
        .replace(
            "__TEST_AUTH_STATUS__",
            (
                "Use a Firebase test account to fetch a token automatically."
                if test_auth_enabled
                else "Test auth endpoint is disabled for this environment."
            ),
        )
    )


# /auth/token intentionally disabled for now.
# Use /authentication/get_token for the app-facing login flow.


@auth_router.post(
    "/refresh",
    response_model=UserRefreshResponse,
    summary="Refresh an expired access token",
    responses={
        401: {"description": "Invalid or expired refresh token"},
        503: {"description": "Service unavailable"},
    },
    include_in_schema=True,
)
def refresh_token(
    request: FirebaseRefreshRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Session = Depends(get_db),
):
    """Exchange a ``refresh_token`` for a new ``id_token`` and app user context.

    Call this when the bearer token has expired. The returned ``access_token``
    replaces the old token for subsequent requests and includes the same user
    context as ``/authentication/get_token``.
    """
    try:
        firebase_result = refresh_id_token(
            api_key=settings.firebase_web_api_key,
            refresh_token=request.refresh_token,
        )
    except FirebaseInvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        ) from exc
    except FirebaseIdentityError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    token_data = decode_access_token(firebase_result.id_token, settings)
    app_user = db.query(AppUser).filter(AppUser.firebase_uid == token_data.sub).first()
    if app_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found. Contact an administrator.",
        )

    name, surname = split_user_name(app_user.full_name)
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=firebase_result.expires_in
    )

    return UserRefreshResponse(
        access_token=firebase_result.id_token,
        refresh_token=firebase_result.refresh_token,
        token_type="bearer",
        role=app_user.role,
        user_id=app_user.firebase_uid,
        name=app_user.name or name,
        surname=app_user.surname or surname,
        expires_at=expires_at,
    )


@auth_router.get(
    "/test/whoami", summary="Validate Firebase bearer token", include_in_schema=False
)
def auth_test_whoami(
    current_user: Annotated[TokenData, Depends(get_current_user)],
):
    return {
        "provider": "firebase",
        "user": _serialize_user(current_user),
    }


@auth_router.post(
    "/test/token",
    summary="Exchange email/password for a Firebase ID token (testing only)",
    include_in_schema=False,
)
def auth_test_token(
    request: FirebasePasswordSignInRequest,
    settings: Annotated[Settings, Depends(get_settings)],
):
    if not settings.enable_test_auth_endpoints:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test auth endpoints are disabled.",
        )

    try:
        return sign_in_with_email_password(
            api_key=settings.firebase_web_api_key,
            email=request.email,
            password=request.password,
        )
    except FirebaseInvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        ) from exc
    except FirebaseIdentityError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


app.include_router(auth_router)


@app.get("/openapi.json", include_in_schema=False)
def openapi_schema(
    current_user: Annotated[TokenData, Depends(_require_docs_user)],
):
    return JSONResponse(
        get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            openapi_version=app.openapi_version,
            routes=app.routes,
        )
    )


@app.get("/docs", include_in_schema=False)
def docs_index(settings: Annotated[Settings, Depends(get_settings)]):
    return HTMLResponse(_build_docs_html(settings))


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["health"], summary="Health check", include_in_schema=False)
def health():
    """Returns ``{"status": "ok"}`` when the service is running."""
    return {"status": "ok"}


@app.get(
    "/health/db",
    tags=["health"],
    summary="Database connectivity check",
    include_in_schema=False,
)
def health_db(db: Annotated[Session, Depends(get_db)]):
    """Returns ``{"status": "ok"}`` if the database is reachable."""
    try:
        from sqlalchemy import text

        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unreachable: {exc}",
        )


# ---------------------------------------------------------------------------
# Protected example route
# ---------------------------------------------------------------------------


@app.get(
    "/me", tags=["users"], summary="Current authenticated user", include_in_schema=False
)
def read_current_user(
    current_user: Annotated[TokenData, Depends(get_current_user)],
):
    """Return the identity of the currently authenticated caller."""
    return _serialize_user(current_user)
