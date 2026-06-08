from datetime import date, datetime, time
from enum import Enum
from typing import List, Optional
from fastapi import Query
from pydantic import BaseModel, Field, field_validator, model_validator


class GeofenceType(str, Enum):
    circle = "circle"
    polygon = "polygon"


class Cordinates(BaseModel):
    lat: float
    lng: float


class AddGeofence(BaseModel):
    name: str
    active: bool = True
    device_id: int = 0
    group_id: int = 0
    type: GeofenceType = GeofenceType.circle
    polygon: Optional[List[Cordinates]] = None
    radius: Optional[float] = None
    center: Optional[Cordinates] = None
    polygon_color: str
    speed_limit: Optional[float] = None

    @model_validator(mode="after")
    def validate_circle_fields(self) -> "AddGeofence":
        if self.type == GeofenceType.circle:
            if self.radius is None:
                raise ValueError("radius is required when type is 'circle'")
            if self.center is None:
                raise ValueError("center is required when type is 'circle'")
        if self.type == GeofenceType.polygon:
            if not self.polygon:
                raise ValueError("polygon is required when type is 'polygon'")
        return self
