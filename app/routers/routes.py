"""Authenticated timetable downloads for clients that cache routes offline."""

import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user
from app.database import get_db
from app.models.departure import Departure, ScheduleVersion
from app.schemas.departure import DepartureCsvRow, DepartureDownloadRequest
from app.schemas.operations import ErrorResponse
from app.services.departure_service import render_departures_csv

routes_router = APIRouter()

CSV_EXAMPLE = (
    "uid,schedule_uid,operator_id,duty_no,departure,origin,destination,direction,valid_days,bus_type\r\n"
    "c084710e-e075-432c-bca6-04ba59c697e5,b6e73094-3936-499f-869b-1f688b8b0f94,1,504,04:40,Freedomsquare,Central Park,Forward,Monday to Friday,Standard\r\n"
)
CACHE_RESPONSE_HEADERS = {
    "ETag": {
        "description": "Fingerprint of this exact CSV. Save the whole value, including quotation marks, and send it as If-None-Match on the next request to the same URL/filter.",
        "schema": {"type": "string"},
    },
    "Cache-Control": {
        "description": "private, no-cache: the client may store the schedule, but must revalidate when checking for updates online.",
        "schema": {"type": "string", "example": "private, no-cache"},
    },
}


@routes_router.get(
    "/departures.csv",
    operation_id="downloadRouteDeparturesCsv",
    response_class=Response,
    responses={
        200: {
            "description": "Complete current timetable as UTF-8 CSV. Parse the header and replace the matching local cache only after the whole download is validated. Header-only CSV means no published departures for this selection.",
            "content": {"text/csv": {
                "schema": {"type": "string", "format": "binary"},
                "example": CSV_EXAMPLE,
            }},
            "headers": {
                **CACHE_RESPONSE_HEADERS,
                "Content-Disposition": {
                    "description": "Suggested download filename.",
                    "schema": {"type": "string", "example": 'attachment; filename="route-departures.csv"'},
                },
            },
        },
        304: {"description": "No response body. Keep the saved CSV and ETag; this is a successful update check, not an error.", "headers": CACHE_RESPONSE_HEADERS},
        401: {"model": ErrorResponse, "description": "Missing, expired, or invalid Firebase bearer token. Retain the cache, obtain a valid token through the existing login/refresh flow, then retry."},
        500: {"model": ErrorResponse, "description": "Server error. Retain the existing cache and retry later."},
    },
    # A CSV file stays a binary/string response in standard OpenAPI. This
    # extension supplies the parsed-row contract without advertising JSON.
    openapi_extra={"x-csv-row-schema": DepartureCsvRow.model_json_schema()},
)
def download_departures_csv(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    query: Annotated[DepartureDownloadRequest, Query()],
    if_none_match: Annotated[str | None, Header(description="Optional saved ETag, including quotes. Omit on the first download or if no usable local CSV exists. Send it only for the same URL/operator selection.")] = None,
):
    """Download current route departures for offline mobile use.

    **Request:** GET with no request body. Set `Authorization: Bearer <Firebase
    ID token>`. Use `operator_id=1` for IBL, or omit the query parameter for all
    operators. `Accept: text/csv` is recommended.

    **First download:** omit `If-None-Match`. HTTP 200 contains a UTF-8 CSV file,
    not JSON. Parse it using a CSV library, validate it, then save both the
    complete timetable and the response `ETag` together on the device. Never
    split rows on commas: quoted location names may contain commas.

    **Next online check:** send the saved ETag, including its quotes, in
    `If-None-Match`, using the same URL and operator filter. HTTP 304 has no body
    and means keep the existing cache. HTTP 200 means validate and replace the
    entire matching cache and save the new ETag. Do not append downloaded rows.

    **Offline or failed request:** keep using the saved schedule. If no cache
    exists, show that a first online download is required; do not send a saved
    ETag without its matching CSV. After a 401, use the existing auth refresh or
    login flow and retry once with a valid token. Invalid query values return
    422; fix the request rather than retrying it unchanged.

    **Columns:** `uid`, `schedule_uid`, `operator_id`, `duty_no`, `departure`,
    `origin`, `destination`, `direction`, `valid_days`, `bus_type`. UUIDs are text
    identifiers for records and versions. Keep duty numbers as text. Departure
    is local `Africa/Johannesburg` time formatted as `HH:MM`, not a UTC timestamp.
    Day groups and bus types are source labels. An empty published selection
    returns the CSV header with zero data rows, still HTTP 200.

    **Versions:** only active schedules are downloaded. Previous versions stay
    in the database. New versions have new departure UUIDs; already-captured
    offline records must not be relabelled. The existing shift submission body
    is unchanged. Keep each URL/operator selection's CSV and ETag separately.
    """
    # A single SELECT sees one committed snapshot even during publication.
    statement = select(
        Departure.uid, Departure.schedule_uid, ScheduleVersion.operator_id,
        Departure.duty_no, Departure.departure, Departure.origin,
        Departure.destination, Departure.direction, Departure.valid_days, Departure.bus_type,
    ).join(ScheduleVersion, Departure.schedule_uid == ScheduleVersion.uid).where(ScheduleVersion.is_active.is_(True))
    if query.operator_id is not None:
        statement = statement.where(ScheduleVersion.operator_id == query.operator_id)
    statement = statement.order_by(ScheduleVersion.operator_id, Departure.duty_no, Departure.departure, Departure.uid)
    content = render_departures_csv(db.execute(statement).all())
    etag = '"' + hashlib.sha256(content).hexdigest() + '"'
    headers = {"ETag": etag, "Cache-Control": "private, no-cache"}
    if if_none_match and any(tag.strip().removeprefix("W/") in (etag, "*") for tag in if_none_match.split(",")):
        return Response(status_code=304, headers=headers)
    headers["Content-Disposition"] = 'attachment; filename="route-departures.csv"'
    return Response(content=content, media_type="text/csv", headers=headers)
