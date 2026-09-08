"""Query contract and the typed columns in a departure CSV download."""

from uuid import UUID

from pydantic import BaseModel, Field


class DepartureDownloadRequest(BaseModel):
    """GET query parameters, not a JSON request body.

    Authorization and If-None-Match are HTTP headers documented by the route.
    """

    operator_id: int | None = Field(
        default=None, gt=0,
        description="Operator to download (1 = Interstate Bus Lines). Omit for all operators' current schedules.",
        examples=[1],
    )


class DepartureCsvRow(BaseModel):
    """One parsed CSV row. The HTTP response is a CSV file, not JSON."""

    uid: UUID = Field(description="Departure record UUID within this schedule version.")
    schedule_uid: UUID = Field(description="Published schedule version UUID; links this row to its retained history.")
    operator_id: int = Field(gt=0, description="Operator owning this departure.", examples=[1])
    duty_no: str = Field(min_length=1, description="Duty number as text. Preserve leading zeros; it is not a route code.", examples=["504"])
    departure: str = Field(
        pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$",
        description="Scheduled local Africa/Johannesburg time in HH:MM. Do not convert it to UTC.",
        examples=["04:40"],
    )
    origin: str = Field(min_length=1, description="Starting location.", examples=["Freedomsquare"])
    destination: str = Field(min_length=1, description="Destination location.", examples=["Central Park"])
    direction: str = Field(min_length=1, description="Source direction label; currently Forward or Reverse.")
    valid_days: str = Field(min_length=1, description="Source operating-day group; currently Monday to Friday, Saturday, or Sunday.")
    bus_type: str = Field(min_length=1, description="Source bus-type label; currently Standard or Train. Preserve the source label.")
