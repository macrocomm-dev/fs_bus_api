import logging
from typing import Annotated
from urllib.parse import urlencode

import requests as re

from fastapi import (
    HTTPException,
    APIRouter,
    Query,
    Depends,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user
from app.config import Settings, get_settings
from app.database import get_db
from app.schemas.smartfleet import (
    AddGeofence,
    SmartFleetIframeUrlResponse,
    SmartFleetOttTokenResponse,
)

logger = logging.getLogger(__name__)

smartfleet_router = APIRouter()


def _build_smart_fleet_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


@smartfleet_router.post("/create-geofence")
async def add_geofence(
    userapihash: Annotated[str, Query(..., alias="user_api_hash")],
    geofence: AddGeofence,
    db: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    """Add a geofence to the system."""

    try:
        url = "https://smart-fleet.co.za/api/add_geofence"

        querystring = {
            "lang": "en",
            "user_api_hash": userapihash,
        }
        payload = geofence.dict()
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        response = re.post(url, json=payload, headers=headers, params=querystring)

        print(response.json())
        return JSONResponse(content=response.json(), status_code=response.status_code)
    except Exception as e:
        logger.exception("Unexpected error in add_geofence: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@smartfleet_router.get("/iframe-login-url", response_model=SmartFleetIframeUrlResponse)
async def get_iframe_login_url(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SmartFleetIframeUrlResponse:
    """Return a Smart Fleet iframe login URL built from a server-side OTT exchange."""

    if not settings.smart_fleet_base_url or not settings.smart_fleet_email or not settings.smart_fleet_api_hash:
        logger.error(
            "Smart Fleet OTT configuration is incomplete: base_url_set=%s email_set=%s api_hash_set=%s",
            bool(settings.smart_fleet_base_url),
            bool(settings.smart_fleet_email),
            bool(settings.smart_fleet_api_hash),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Smart Fleet is not configured.",
        )

    token_url = _build_smart_fleet_url(settings.smart_fleet_base_url, "/api/one_time_token")
    try:
        response = re.post(
            token_url,
            params={"lang": "en", "user_api_hash": settings.smart_fleet_api_hash},
            json={"email": settings.smart_fleet_email},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=20,
        )
    except re.RequestException as exc:
        logger.exception("Smart Fleet OTT request failed for %s", current_user.sub)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Smart Fleet.",
        ) from exc

    try:
        response_body = response.json()
        payload = SmartFleetOttTokenResponse.model_validate(response_body)
    except ValueError as exc:
        logger.exception(
            "Smart Fleet OTT response was not valid JSON: status=%s body_prefix=%r",
            response.status_code,
            response.text[:500],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Smart Fleet returned an invalid response.",
        ) from exc

    if response.status_code >= 400 or not payload.token:
        detail = payload.message or "Could not create Smart Fleet login link."
        logger.warning(
            "Smart Fleet OTT request was rejected: http_status=%s smart_status=%s message=%r email=%s",
            response.status_code,
            payload.status,
            payload.message,
            settings.smart_fleet_email,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        )

    iframe_url = _build_smart_fleet_url(
        settings.smart_fleet_base_url,
        f"/login?{urlencode({'ott': payload.token})}",
    )
    return SmartFleetIframeUrlResponse(iframe_url=iframe_url)
