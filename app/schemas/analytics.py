from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class AnalyticsMetricTileResponse(BaseModel):
    title: str
    icon: str
    color: str
    primary: str
    secondary: str | None = None


class AnalyticsGaugeScoreResponse(BaseModel):
    label: str
    score: float
    color: str


class AnalyticsVehiclePerformanceResponse(BaseModel):
    fleet_no: str
    registration: str
    operator: str
    distance: str
    trip_duration: str
    speed_duration: str
    idle_duration: str
    high_risk_trips: int
    score: float


class AnalyticsLastEventResponse(BaseModel):
    bus: str
    location: str
    time: datetime
    event_type: str
    measurement: str
    operator: str


class AnalyticsVehicleScoreResponse(BaseModel):
    fleet_no: str
    registration: str
    operator: str
    score: float


class AnalyticsSummaryItemResponse(BaseModel):
    label: str
    value: int | str
    drill_key: str | None = None


class AnalyticsTrendSeriesResponse(BaseModel):
    name: str
    data: list[int]


class AnalyticsTrendResponse(BaseModel):
    dates: list[str]
    series: list[AnalyticsTrendSeriesResponse]


class AnalyticsTopKpiResponse(BaseModel):
    id: str
    value: str
    secondary_text: str | None = None
    status: str = "good"
    summary_items: list[AnalyticsSummaryItemResponse] = []
    trend: AnalyticsTrendResponse | None = None


class AnalyticsTableColumnResponse(BaseModel):
    field: str
    header: str


class AnalyticsDrilldownResponse(BaseModel):
    title: str
    columns: list[AnalyticsTableColumnResponse]
    data: list[dict[str, Any]]


class AnalyticsReportingTileResponse(BaseModel):
    id: str
    title: str
    metric: str
    value: int | str
    status: str = "good"
    icon: str
    summary_items: list[AnalyticsSummaryItemResponse] = []
    trend: AnalyticsTrendResponse | None = None
    chart_series: list[AnalyticsTrendSeriesResponse] = []


class AnalyticsSummaryResponse(BaseModel):
    generated_at: datetime = Field(..., description="UTC timestamp for this summary.")
    source_date_from: date | None = None
    source_date_to: date | None = None
    top_kpis: list[AnalyticsTopKpiResponse]
    gauge_scores: list[AnalyticsGaugeScoreResponse]
    metric_tiles: list[AnalyticsMetricTileResponse]
    last_events: list[AnalyticsLastEventResponse]
    vehicle_performance: list[AnalyticsVehiclePerformanceResponse]
    vehicle_scores: list[AnalyticsVehicleScoreResponse]


class AnalyticsReportingSummaryResponse(BaseModel):
    generated_at: datetime = Field(..., description="UTC timestamp for this report summary.")
    source_date_from: date | None = None
    source_date_to: date | None = None
    tiles: list[AnalyticsReportingTileResponse]
    drilldowns: dict[str, AnalyticsDrilldownResponse]
