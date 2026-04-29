"""
FS Bus API — main application entry-point.
"""

from __future__ import annotations

from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse

from app.auth import (
    expand_role_permissions,
    get_current_user,
    normalize_role,
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
from app.routers.router_config import register_routers

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


def _get_cors_origins(settings: Settings) -> list[str]:
    return [o.strip() for o in settings.cors_origins.split(",") if o.strip()]


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
    return (
        _load_docs_template()
        .replace("__APP_TITLE__", escape(app.title))
        .replace("__REQUIRED_ROLE__", required_role)
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


@auth_router.post(
    "/token",
    response_model=FirebasePasswordSignInResult,
    summary="Obtain an access token",
    responses={
        401: {"description": "Invalid email or password"},
        503: {"description": "Service unavailable"},
    },
)
def login(
    request: FirebasePasswordSignInRequest,
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Exchange email and password for a Firebase ID token.

    Use the returned ``id_token`` as a ``Bearer`` token on all protected endpoints.
    The ``refresh_token`` can be used to obtain a new ``id_token`` when it expires.
    """
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


@auth_router.post(
    "/refresh",
    response_model=FirebaseRefreshResult,
    summary="Refresh an expired access token",
    responses={
        401: {"description": "Invalid or expired refresh token"},
        503: {"description": "Service unavailable"},
    },
    include_in_schema=False,
)
def refresh_token(
    request: FirebaseRefreshRequest,
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Exchange a ``refresh_token`` for a new ``id_token``.

    Call this when the ``id_token`` from ``/auth/token`` has expired (after 1 hour).
    The returned ``id_token`` replaces the old one for subsequent requests.
    """
    try:
        return refresh_id_token(
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


# ---------------------------------------------------------------------------
# Protected example route
# ---------------------------------------------------------------------------


@app.get("/me", tags=["users"], summary="Current authenticated user")
def read_current_user(
    current_user: Annotated[TokenData, Depends(get_current_user)],
):
    """Return the identity of the currently authenticated caller."""
    return _serialize_user(current_user)
