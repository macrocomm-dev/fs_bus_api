import logging
from collections import defaultdict
from datetime import date, datetime, time
from typing import Annotated, List, Optional
import requests as re

from fastapi import (
    Depends,
    File,
    Form,
    HTTPException,
    APIRouter,
    Path,
    Query,
    UploadFile,
    requests,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.schemas.smartfleet import AddGeofence

logger = logging.getLogger(__name__)

smartfleet_router = APIRouter()


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
