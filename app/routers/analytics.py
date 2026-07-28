from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user
from app.database import get_db
from app.schemas.analytics import (
    AnalyticsGaugeScoreResponse,
    AnalyticsLastEventResponse,
    AnalyticsDrilldownResponse,
    AnalyticsMetricTileResponse,
    AnalyticsReportingSummaryResponse,
    AnalyticsReportingTileResponse,
    AnalyticsSummaryResponse,
    AnalyticsSummaryItemResponse,
    AnalyticsTableColumnResponse,
    AnalyticsTopKpiResponse,
    AnalyticsTrendResponse,
    AnalyticsTrendSeriesResponse,
    AnalyticsVehiclePerformanceResponse,
    AnalyticsVehicleScoreResponse,
)
from app.schemas.shift import ErrorResponse

analytics_router = APIRouter()
logger = logging.getLogger(__name__)

ROUTE_START_INTERVALS = ("0-5 mins", "5-10 mins", "10-15 mins", "15+ mins")
ON_TIME_ROUTE_START_INTERVALS = {"0-5 mins"}
MAJOR_DELAY_INTERVALS = {"10-15 mins", "15+ mins"}
COMPLETED_INSPECTION_TYPES = ("external", "internal", "driver", "count", "technical")
FAILED_INSPECTION_LABELS = {
    "external": "External Inspections",
    "internal": "Internal Inspections",
    "driver": "Driver Inspections",
    "count": "Passenger Counts",
    "technical": "Technical Inspections",
}


def _to_float(value: Any, default: float = 0) -> float:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    return int(value)


def _score(value: Any) -> float:
    return round(_to_float(value), 1)


def _format_duration(seconds: Any) -> str:
    total_seconds = max(_to_int(seconds), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    return f"{hours:,} hrs {minutes:02d} mins"


def _format_distance(kilometres: Any) -> str:
    return f"{_to_float(kilometres):,.2f} km"


def _format_percent(numerator: int | float, denominator: int | float) -> str:
    if denominator <= 0:
        return "N/A"
    return f"{(numerator / denominator * 100):.1f}%"


def _route_start_interval_counts(
    counts_by_interval: dict[str, int],
) -> tuple[int, int, int]:
    total = sum(counts_by_interval.get(interval, 0) for interval in ROUTE_START_INTERVALS)
    on_time = sum(
        counts_by_interval.get(interval, 0) for interval in ON_TIME_ROUTE_START_INTERVALS
    )
    late = max(total - on_time, 0)
    return on_time, late, total


def _status_for_percent(value: str, inverse: bool = False) -> str:
    if value == "N/A":
        return "warning"
    numeric = float(value.rstrip("%"))
    if inverse:
        if numeric <= 5:
            return "good"
        if numeric <= 15:
            return "warning"
        return "critical"
    if numeric >= 90:
        return "good"
    if numeric >= 80:
        return "warning"
    return "critical"


def _operator_label(group: str | None) -> str:
    value = (group or "").strip().upper()
    if value == "INTERSTATE":
        return "Interstate Bus Lines"
    if value == "MALUTI":
        return "Maluti Bus Services"
    return group or "Unassigned"


def _split_vehicle_label(value: str | None, alias: str | None = None) -> tuple[str, str]:
    raw = (value or "").strip()
    if " - " in raw:
        registration, fleet_no = raw.split(" - ", 1)
        return fleet_no.strip() or raw, registration.strip() or raw
    fallback = (alias or raw or "Unknown").strip()
    return fallback, raw or fallback


def _event_type(event_id: int | None) -> str:
    if event_id is None:
        return "Event"
    if event_id == 99:
        return "Speeding"
    return f"Event {event_id}"


def _event_measurement(row) -> str:
    max_speed = row.max_speed
    speed_limit = row.speed_limit
    duration = row.duration
    if max_speed is not None and speed_limit is not None:
        return f"{max_speed} km/h in {speed_limit} km/h zone"
    if max_speed is not None:
        return f"Max speed {max_speed} km/h"
    if duration is not None:
        return f"{duration} seconds"
    return "-"


def _date_params(start_date: date | None, end_date: date | None) -> dict[str, date | None]:
    return {"start_date": start_date, "end_date": end_date}


def _report_columns(*columns: tuple[str, str]) -> list[AnalyticsTableColumnResponse]:
    return [AnalyticsTableColumnResponse(field=field, header=header) for field, header in columns]


def _drilldown(
    title: str,
    columns: list[AnalyticsTableColumnResponse],
    data: list[dict[str, Any]] | None = None,
) -> AnalyticsDrilldownResponse:
    return AnalyticsDrilldownResponse(title=title, columns=columns, data=data or [])


def _status_for_count(count: int) -> str:
    return "good" if count == 0 else "warning" if count < 10 else "critical"


def _bool_label(value: bool | None, pass_label: str = "Pass", fail_label: str = "Fail") -> str:
    if value is None:
        return "-"
    return pass_label if value else fail_label


def _bus_label_from_parts(
    registration: str | None,
    fleet_number: str | None,
    bus_id: str | None,
) -> tuple[str, str]:
    return registration or bus_id or "-", fleet_number or "-"


def _inspection_has_failed_checks(row) -> bool:
    if row.inspection_type == "count":
        return _to_int(row.number_standing) > 0
    check_values = [
        row.pass_,
        row.tyres_pass,
        row.windows_pass,
        row.ext_other_pass,
        row.fire_extinguisher_present,
        row.seats_pass,
        row.aisle_pass,
        row.int_other_pass,
        row.prdp_scan_succeeded,
        row.driver_identified,
    ]
    return any(value is False for value in check_values)


def _inspection_row(row) -> dict[str, Any]:
    registration, fleet_no = _bus_label_from_parts(
        row.registration_number, row.fleet_number, row.bus_id
    )
    inspector = row.full_name or row.user_id or "-"
    return {
        "busReg": registration,
        "fleetNo": fleet_no,
        "operator": row.operator_name or "Unassigned",
        "inspector": inspector,
        "driver": row.driver_name or "-",
        "terminal": "-",
        "route": row.duty_number or "-",
        "date": row.inspection_time.date().isoformat() if row.inspection_time else "-",
        "time": row.inspection_time.strftime("%H:%M") if row.inspection_time else "-",
        "gps": (
            f"{row.inspection_lat}, {row.inspection_lon}"
            if row.inspection_lat is not None and row.inspection_lon is not None
            else ""
        ),
        "status": "Fail" if _inspection_has_failed_checks(row) else "Pass",
        "inspectionType": row.inspection_type,
    }


def _inspection_filter(rows: list[Any], inspection_type: str) -> list[Any]:
    return [row for row in rows if row.inspection_type == inspection_type]


def _bus_attempt_key(row) -> tuple[str, str, str, str, str]:
    return (
        str(row.shift_id or ""),
        str(row.bus_id or "").strip().lower(),
        str(row.fleet_number or "").strip().lower(),
        str(row.duty_number or "").strip().lower(),
        str(row.replacement_bus or False).lower(),
    )


def _defect_rows(rows: list[Any], category: str | None = None) -> list[dict[str, Any]]:
    defects: list[dict[str, Any]] = []
    for row in rows:
        base = _inspection_row(row)
        checks = [
            ("Fire Extinguisher", row.fire_extinguisher_present, row.notes),
            ("Seats", row.seats_pass, row.seats_notes),
            ("Aisle", row.aisle_pass, row.aisle_notes),
            ("Tyres", row.tyres_pass, row.tyres_notes),
            ("Windows", row.windows_pass, row.windows_notes),
            ("Exterior Other", row.ext_other_pass, row.ext_other_notes),
            ("Interior Other", row.int_other_pass, row.int_other_notes),
        ]
        for defect_type, passed, notes in checks:
            if passed is False and (category is None or category == defect_type):
                defects.append(
                    {
                        **base,
                        "defectType": defect_type,
                        "defectDescription": notes or defect_type,
                        "severity": "Failed",
                    }
                )
        if row.inspection_type == "technical" and row.pass_ is False and category in {None, "Technical"}:
            defects.append(
                {
                    **base,
                    "defectType": "Technical",
                    "defectDescription": row.notes or "Technical inspection failed",
                    "severity": "Failed",
                }
            )
    return defects


def _count_by_operator(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        operator = str(row.get("operator") or "Unassigned")
        counts[operator] = counts.get(operator, 0) + 1
    return counts


@analytics_router.get(
    "/reporting-summary",
    response_model=AnalyticsReportingSummaryResponse,
    responses={500: {"model": ErrorResponse}},
    operation_id="get_reporting_summary",
)
def get_reporting_summary(
    start_date: date | None = Query(None, description="Optional inclusive report start date."),
    end_date: date | None = Query(None, description="Optional inclusive report end date."),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> AnalyticsReportingSummaryResponse:
    """Return the Reporting dashboard tiles and drilldowns from real stored data."""

    del current_user
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date.",
        )

    params = _date_params(start_date, end_date)

    try:
        inspection_rows = db.execute(
            text(
                """
                select
                    i.id,
                    i.shift_id,
                    i.user_id,
                    i.bus_id,
                    i.fleet_number,
                    i.duty_number,
                    i.replacement_bus,
                    i.inspection_type,
                    i.inspection_time,
                    i.inspection_lat,
                    i.inspection_lon,
                    i.count,
                    i.pass as pass_,
                    i.notes,
                    i.tyres_pass,
                    i.tyres_notes,
                    i.windows_pass,
                    i.windows_notes,
                    i.ext_other_pass,
                    i.ext_other_notes,
                    i.fire_extinguisher_present,
                    i.seats_pass,
                    i.seats_notes,
                    i.aisle_pass,
                    i.aisle_notes,
                    i.int_other_pass,
                    i.int_other_notes,
                    i.number_seated,
                    i.number_standing,
                    i.behind_schedule_interval,
                    i.license_disk_scan_succeeded,
                    i.destination_displayed,
                    i.prdp_scan_succeeded,
                    i.prdp_expiry_date,
                    i.driver_identified,
                    i.driver_fail_reason,
                    i.driver_name,
                    coalesce(v.registration_number, i.bus_id) as registration_number,
                    coalesce(v.fleet_number, i.fleet_number) as vehicle_fleet_number,
                    v.operator_name,
                    u.full_name
                from inspections.inspections i
                left join master_data.vehicle v
                  on lower(coalesce(v.fleet_number, '')) = lower(coalesce(i.fleet_number, ''))
                  or lower(coalesce(v.registration_number, '')) = lower(coalesce(i.bus_id, ''))
                  or lower(coalesce(v.vin, '')) = lower(coalesce(i.bus_id, ''))
                left join app_auth.app_user u on u.firebase_uid = i.user_id
                where (cast(:start_date as date) is null or i.inspection_time::date >= cast(:start_date as date))
                  and (cast(:end_date as date) is null or i.inspection_time::date <= cast(:end_date as date))
                order by i.inspection_time desc, i.id desc
                """
            ),
            params,
        ).mappings().all()

        shift_rows = db.execute(
            text(
                """
                select
                    s.id,
                    s.user_id,
                    s.start_time,
                    s.end_time,
                    s.start_lat,
                    s.start_lon,
                    s.end_lat,
                    s.end_lon,
                    s.device_id,
                    u.full_name,
                    o.operator_name
                from shifts.shifts s
                left join app_auth.app_user u on u.firebase_uid = s.user_id
                left join master_data.operator o on o.operator_id = u.operator_id
                where (cast(:start_date as date) is null or s.start_time::date >= cast(:start_date as date))
                  and (cast(:end_date as date) is null or s.start_time::date <= cast(:end_date as date))
                order by s.start_time desc
                """
            ),
            params,
        ).mappings().all()

        route_deviation_rows = db.execute(
            text(
                """
                select
                    vehiclereg,
                    vehiclealias,
                    vehiclegroup,
                    driver,
                    tripstart,
                    routevar,
                    routescore,
                    startloc,
                    startlat,
                    startlon
                from analytics.trip_data
                where coalesce(routevar, 0) > 0
                  and (cast(:start_date as date) is null or tripstart::date >= cast(:start_date as date))
                  and (cast(:end_date as date) is null or tripstart::date <= cast(:end_date as date))
                order by tripstart desc
                limit 500
                """
            ),
            params,
        ).mappings().all()

        fleet_bucket_rows = db.execute(
            text(
                """
                with filtered as (
                    select *
                    from analytics.bi_data
                    where (cast(:start_date as date) is null or bi_date >= cast(:start_date as date))
                      and (cast(:end_date as date) is null or bi_date <= cast(:end_date as date))
                ),
                latest_bi as (
                    select distinct on (vehiclereg) vehiclereg, bi_total
                    from filtered
                    order by vehiclereg, bi_date desc
                )
                select
                    count(*) as total,
                    count(*) filter (where bi_total < 50) as under_50,
                    count(*) filter (where bi_total >= 50) as over_50,
                    count(*) filter (where bi_total >= 80) as over_80,
                    count(*) filter (where bi_total >= 95) as over_95,
                    avg(bi_total) as avg_score
                from latest_bi
                """
            ),
            params,
        ).mappings().one()

        report_date_row = db.execute(
            text(
                """
                select min(source_date) as source_date_from, max(source_date) as source_date_to
                from (
                    select inspection_time::date as source_date
                    from inspections.inspections
                    where (cast(:start_date as date) is null or inspection_time::date >= cast(:start_date as date))
                      and (cast(:end_date as date) is null or inspection_time::date <= cast(:end_date as date))
                    union all
                    select start_time::date as source_date
                    from shifts.shifts
                    where (cast(:start_date as date) is null or start_time::date >= cast(:start_date as date))
                      and (cast(:end_date as date) is null or start_time::date <= cast(:end_date as date))
                    union all
                    select tripstart::date as source_date
                    from analytics.trip_data
                    where (cast(:start_date as date) is null or tripstart::date >= cast(:start_date as date))
                      and (cast(:end_date as date) is null or tripstart::date <= cast(:end_date as date))
                ) source_dates
                """
            ),
            params,
        ).mappings().one()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not load reporting summary")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load reporting summary.",
        ) from exc

    inspections_by_type = {
        "external": _inspection_filter(inspection_rows, "external"),
        "internal": _inspection_filter(inspection_rows, "internal"),
        "driver": _inspection_filter(inspection_rows, "driver"),
        "count": _inspection_filter(inspection_rows, "count"),
        "technical": _inspection_filter(inspection_rows, "technical"),
        "behind_schedule": _inspection_filter(inspection_rows, "behind_schedule"),
    }

    inspection_columns = _report_columns(
        ("busReg", "Bus Reg"),
        ("fleetNo", "Fleet No"),
        ("operator", "Operator"),
        ("inspector", "Inspector"),
        ("date", "Date"),
        ("time", "Time"),
        ("status", "Status"),
        ("gps", "GPS"),
    )
    external_columns = inspection_columns + _report_columns(
        ("tyres", "Tyres"),
        ("windows", "Windows"),
        ("other", "Other"),
    )
    internal_columns = inspection_columns + _report_columns(
        ("fireExtinguisher", "Fire Extinguisher"),
        ("seats", "Seats"),
        ("aisle", "Aisle"),
    )
    driver_columns = _report_columns(
        ("busReg", "Bus Reg"),
        ("fleetNo", "Fleet No"),
        ("operator", "Operator"),
        ("driver", "Driver"),
        ("inspector", "Inspector"),
        ("date", "Date"),
        ("time", "Time"),
        ("pdpExpiry", "PDP Expiry"),
        ("driverIdentified", "Identified"),
        ("status", "Status"),
    )
    passenger_columns = _report_columns(
        ("busReg", "Bus Reg"),
        ("fleetNo", "Fleet No"),
        ("operator", "Operator"),
        ("route", "Route / Duty"),
        ("date", "Date"),
        ("time", "Time"),
        ("seated", "Seated"),
        ("standing", "Standing"),
        ("total", "Total Pax"),
    )
    delay_columns = _report_columns(
        ("busReg", "Bus Reg"),
        ("fleetNo", "Fleet No"),
        ("operator", "Operator"),
        ("route", "Route / Duty"),
        ("driver", "Driver"),
        ("date", "Date"),
        ("time", "Time"),
        ("interval", "Delay Interval"),
    )
    defect_columns = _report_columns(
        ("busReg", "Bus Reg"),
        ("fleetNo", "Fleet No"),
        ("operator", "Operator"),
        ("defectType", "Defect Type"),
        ("defectDescription", "Description"),
        ("inspector", "Inspector"),
        ("date", "Date"),
        ("time", "Time"),
        ("gps", "GPS"),
    )

    def rows_for_inspection_type(inspection_type: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in inspections_by_type[inspection_type]:
            base = _inspection_row(row)
            if inspection_type == "external":
                base.update(
                    {
                        "tyres": _bool_label(row.tyres_pass),
                        "windows": _bool_label(row.windows_pass),
                        "other": _bool_label(row.ext_other_pass),
                    }
                )
            elif inspection_type == "internal":
                base.update(
                    {
                        "fireExtinguisher": _bool_label(
                            row.fire_extinguisher_present, "Present", "Missing"
                        ),
                        "seats": _bool_label(row.seats_pass),
                        "aisle": _bool_label(row.aisle_pass),
                    }
                )
            elif inspection_type == "driver":
                base.update(
                    {
                        "pdpExpiry": (
                            row.prdp_expiry_date.date().isoformat()
                            if row.prdp_expiry_date
                            else "-"
                        ),
                        "driverIdentified": _bool_label(row.driver_identified, "Yes", "No"),
                    }
                )
            rows.append(base)
        return rows

    external_rows = rows_for_inspection_type("external")
    internal_rows = rows_for_inspection_type("internal")
    driver_rows = rows_for_inspection_type("driver")
    technical_rows = rows_for_inspection_type("technical")

    passenger_rows = []
    for row in inspections_by_type["count"]:
        base = _inspection_row(row)
        seated = _to_int(row.number_seated)
        standing = _to_int(row.number_standing)
        total = _to_int(row.count, seated + standing)
        passenger_rows.append(
            {
                **base,
                "seated": seated,
                "standing": standing,
                "total": total,
                "overloadedCount": standing,
            }
        )

    delayed_rows_by_interval: dict[str, list[dict[str, Any]]] = {
        "0-5 mins": [],
        "5-10 mins": [],
        "10-15 mins": [],
        "15+ mins": [],
    }
    for row in inspections_by_type["behind_schedule"]:
        base = _inspection_row(row)
        delay_row = {**base, "interval": row.behind_schedule_interval or "Unknown"}
        if row.behind_schedule_interval in delayed_rows_by_interval:
            delayed_rows_by_interval[row.behind_schedule_interval].append(delay_row)

    all_defects = _defect_rows(inspection_rows)
    defect_groups = {
        "Fire Extinguisher": _defect_rows(inspection_rows, "Fire Extinguisher"),
        "Seats": _defect_rows(inspection_rows, "Seats"),
        "Aisle": _defect_rows(inspection_rows, "Aisle"),
        "Tyres": _defect_rows(inspection_rows, "Tyres"),
        "Windows": _defect_rows(inspection_rows, "Windows"),
        "Other": _defect_rows(inspection_rows, "Exterior Other")
        + _defect_rows(inspection_rows, "Interior Other"),
        "Technical": _defect_rows(inspection_rows, "Technical"),
    }

    failed_inspection_groups = {
        "External Inspections": [row for row in external_rows if row["status"] == "Fail"],
        "Internal Inspections": [row for row in internal_rows if row["status"] == "Fail"],
        "Driver Inspections": [row for row in driver_rows if row["status"] == "Fail"],
        "Passenger Counts": [row for row in passenger_rows if _to_int(row["overloadedCount"]) > 0],
        "Technical Inspections": [row for row in technical_rows if row["status"] == "Fail"],
    }

    route_deviation_data: list[dict[str, Any]] = []
    for row in route_deviation_rows:
        fleet_no, registration = _split_vehicle_label(row.vehiclereg, row.vehiclealias)
        route_deviation_data.append(
            {
                "busReg": registration,
                "fleetNo": fleet_no,
                "operator": _operator_label(row.vehiclegroup),
                "route": "-",
                "driver": row.driver or "-",
                "date": row.tripstart.date().isoformat() if row.tripstart else "-",
                "time": row.tripstart.strftime("%H:%M") if row.tripstart else "-",
                "deviation": f"{_to_float(row.routevar):.1f}",
                "routeScore": f"{_to_float(row.routescore):.1f}%",
                "gps": (
                    f"{row.startlat}, {row.startlon}"
                    if row.startlat is not None and row.startlon is not None
                    else ""
                ),
            }
        )

    license_disk_fail_rows = []
    pdp_fail_rows = []
    seen_license_disk_failures: set[tuple[str, str, str, str, str]] = set()
    for row in inspection_rows:
        base = _inspection_row(row)
        if row.license_disk_scan_succeeded is False:
            bus_key = _bus_attempt_key(row)
            if bus_key not in seen_license_disk_failures:
                seen_license_disk_failures.add(bus_key)
                license_disk_fail_rows.append(
                    {**base, "diskStatus": "Scan failed", "daysOverdue": "-"}
                )
        if row.prdp_scan_succeeded is False or (
            row.prdp_expiry_date and row.prdp_expiry_date.date() < datetime.now(timezone.utc).date()
        ):
            pdp_fail_rows.append(
                {
                    **base,
                    "pdpExpiry": (
                        row.prdp_expiry_date.date().isoformat()
                        if row.prdp_expiry_date
                        else "-"
                    ),
                    "daysOverdue": (
                        (datetime.now(timezone.utc).date() - row.prdp_expiry_date.date()).days
                        if row.prdp_expiry_date
                        else "-"
                    ),
                }
            )

    shift_operator_counts: dict[str, dict[str, int]] = {}
    for row in shift_rows:
        operator = row.operator_name or "Unassigned"
        shift_operator_counts.setdefault(operator, {"shifts": 0, "inspections": 0, "passed": 0, "failed": 0})
        shift_operator_counts[operator]["shifts"] += 1
    for row in inspection_rows:
        operator = row.operator_name or "Unassigned"
        shift_operator_counts.setdefault(operator, {"shifts": 0, "inspections": 0, "passed": 0, "failed": 0})
        shift_operator_counts[operator]["inspections"] += 1
        if row.pass_ is False:
            shift_operator_counts[operator]["failed"] += 1
        else:
            shift_operator_counts[operator]["passed"] += 1

    operator_drill_rows = [
        {
            "operator": operator,
            "shifts": values["shifts"],
            "inspections": values["inspections"],
            "passed": values["passed"],
            "failed": values["failed"],
        }
        for operator, values in sorted(shift_operator_counts.items())
    ]

    inspection_trend_by_date: dict[str, dict[str, int]] = {}
    type_labels = {
        "external": "External",
        "internal": "Internal",
        "driver": "Driver",
        "count": "Passenger",
        "technical": "Technical",
    }
    for row in inspection_rows:
        if row.inspection_type not in type_labels:
            continue
        date_key = row.inspection_time.date().isoformat()
        inspection_trend_by_date.setdefault(date_key, {label: 0 for label in type_labels.values()})
        inspection_trend_by_date[date_key][type_labels[row.inspection_type]] += 1
    trend_dates = sorted(inspection_trend_by_date)
    inspection_trend = AnalyticsTrendResponse(
        dates=trend_dates,
        series=[
            AnalyticsTrendSeriesResponse(
                name=label,
                data=[inspection_trend_by_date[day].get(label, 0) for day in trend_dates],
            )
            for label in type_labels.values()
        ],
    )
    inspection_type_display_labels = {
        "external": "External Inspections",
        "internal": "Internal Inspections",
        "driver": "Driver Inspections",
        "count": "Passenger Counts",
        "technical": "Technical Inspections",
    }
    inspection_chart_categories = [
        inspection_type_display_labels[key] for key in type_labels
    ]
    inspection_operator_counts: dict[str, dict[str, int]] = {}
    for row in inspection_rows:
        if row.inspection_type not in type_labels:
            continue
        operator = row.operator_name or "Unassigned"
        inspection_operator_counts.setdefault(
            operator, {label: 0 for label in inspection_chart_categories}
        )
        inspection_operator_counts[operator][
            inspection_type_display_labels[row.inspection_type]
        ] += 1
    inspection_chart_series = [
        AnalyticsTrendSeriesResponse(
            name=operator,
            data=[counts[label] for label in inspection_chart_categories],
        )
        for operator, counts in sorted(inspection_operator_counts.items())
    ]

    total_completed = sum(len(inspections_by_type[key]) for key in type_labels)
    total_failed = sum(len(rows) for rows in failed_inspection_groups.values())
    total_defects = len(all_defects)
    delayed_counts_by_interval = {
        interval: len(rows) for interval, rows in delayed_rows_by_interval.items()
    }
    (
        on_time_route_start_checks,
        late_route_start_checks,
        total_route_start_checks,
    ) = _route_start_interval_counts(delayed_counts_by_interval)
    total_route_exceptions = len(route_deviation_data)
    total_violations = len(pdp_fail_rows) + len(license_disk_fail_rows)
    total_overloaded = len(failed_inspection_groups["Passenger Counts"])
    on_time_value = _format_percent(on_time_route_start_checks, total_route_start_checks)
    fleet_health_value = (
        f"{_score(fleet_bucket_rows.avg_score)}%" if _to_int(fleet_bucket_rows.total) else "N/A"
    )

    drilldowns = {
        "completed": _drilldown("Completed Inspections", inspection_columns, [_inspection_row(row) for row in inspection_rows if row.inspection_type in type_labels]),
        "external-inspections": _drilldown("External Inspections", external_columns, external_rows),
        "internal-inspections": _drilldown("Internal Inspections", internal_columns, internal_rows),
        "driver-inspections": _drilldown("Driver Inspections", driver_columns, driver_rows),
        "passenger-counts-drill": _drilldown("Passenger Counts", passenger_columns, passenger_rows),
        "technical-inspections": _drilldown("Technical Inspections", inspection_columns, technical_rows),
        "behind-schedule-0-5": _drilldown("Route Starts (0-5 mins)", delay_columns, delayed_rows_by_interval["0-5 mins"]),
        "behind-schedule-5-10": _drilldown("Behind Schedule (5-10 mins)", delay_columns, delayed_rows_by_interval["5-10 mins"]),
        "behind-schedule-10-15": _drilldown("Behind Schedule (10-15 mins)", delay_columns, delayed_rows_by_interval["10-15 mins"]),
        "behind-schedule-15-plus": _drilldown("Behind Schedule (15+ mins)", delay_columns, delayed_rows_by_interval["15+ mins"]),
        "route-deviation-events": _drilldown(
            "Route Deviations",
            _report_columns(
                ("busReg", "Bus Reg"),
                ("fleetNo", "Fleet No"),
                ("operator", "Operator"),
                ("driver", "Driver"),
                ("date", "Date"),
                ("time", "Time"),
                ("deviation", "Route Variance"),
                ("routeScore", "Route Score"),
                ("gps", "GPS"),
            ),
            route_deviation_data,
        ),
        "missed-stops": _drilldown("Missed Stops", _report_columns(("message", "Status")), []),
        "expired-pdp": _drilldown(
            "Expired / Failed PRDP Checks",
            _report_columns(
                ("busReg", "Bus Reg"),
                ("fleetNo", "Fleet No"),
                ("operator", "Operator"),
                ("driver", "Driver"),
                ("pdpExpiry", "PDP Expiry"),
                ("daysOverdue", "Days Overdue"),
                ("date", "Inspection Date"),
            ),
            pdp_fail_rows,
        ),
        "expired-driver-licence": _drilldown("Expired Driver Licences", _report_columns(("message", "Status")), []),
        "expired-route-licence": _drilldown("Expired Route Licences", _report_columns(("message", "Status")), []),
        "expired-bus-license-disk": _drilldown(
            "Failed Bus Licence Disk Scans",
            _report_columns(
                ("busReg", "Bus Reg"),
                ("fleetNo", "Fleet No"),
                ("operator", "Operator"),
                ("diskStatus", "Disk Status"),
                ("date", "Inspection Date"),
            ),
            license_disk_fail_rows,
        ),
        "fire-extinguisher-defects": _drilldown("Fire Extinguisher Defects", defect_columns, defect_groups["Fire Extinguisher"]),
        "seat-defects": _drilldown("Seat Defects", defect_columns, defect_groups["Seats"]),
        "aisle-obstructions": _drilldown("Aisle Obstructions", defect_columns, defect_groups["Aisle"]),
        "tyre-defects": _drilldown("Tyre Defects", defect_columns, defect_groups["Tyres"]),
        "window-defects": _drilldown("Window Defects", defect_columns, defect_groups["Windows"]),
        "other-defects": _drilldown("Other Defects", defect_columns, defect_groups["Other"]),
        "failed-external-inspections": _drilldown("Failed External Inspections", external_columns, failed_inspection_groups["External Inspections"]),
        "failed-internal-inspections": _drilldown("Failed Internal Inspections", internal_columns, failed_inspection_groups["Internal Inspections"]),
        "failed-driver-inspections": _drilldown("Failed Driver Inspections", driver_columns, failed_inspection_groups["Driver Inspections"]),
        "failed-passenger-counts": _drilldown("Failed Passenger Counts", passenger_columns, failed_inspection_groups["Passenger Counts"]),
        "failed-technical-inspections": _drilldown("Failed Technical Inspections", inspection_columns, failed_inspection_groups["Technical Inspections"]),
        "operator-compliance-summary": _drilldown(
            "Operator Compliance",
            _report_columns(
                ("operator", "Operator"),
                ("shifts", "Shifts"),
                ("inspections", "Inspections"),
                ("passed", "Passed Inspections"),
                ("failed", "Failed Inspections"),
            ),
            operator_drill_rows,
        ),
    }

    tiles = [
        AnalyticsReportingTileResponse(
            id="daily-monitoring",
            title="Daily Bus Monitoring",
            metric="Total Completed Inspections",
            value=total_completed,
            status=_status_for_count(total_completed),
            icon="pi pi-check-circle",
            trend=inspection_trend,
            chart_series=inspection_chart_series,
            summary_items=[
                AnalyticsSummaryItemResponse(label="External Inspections", value=len(external_rows), drill_key="external-inspections"),
                AnalyticsSummaryItemResponse(label="Internal Inspections", value=len(internal_rows), drill_key="internal-inspections"),
                AnalyticsSummaryItemResponse(label="Driver Inspections", value=len(driver_rows), drill_key="driver-inspections"),
                AnalyticsSummaryItemResponse(label="Passenger Counts", value=len(passenger_rows), drill_key="passenger-counts-drill"),
                AnalyticsSummaryItemResponse(label="Technical Inspections", value=len(technical_rows), drill_key="technical-inspections"),
                AnalyticsSummaryItemResponse(label="Total Inspections", value=total_completed, drill_key=None),
            ],
        ),
        AnalyticsReportingTileResponse(
            id="route-exceptions",
            title="Route Compliance",
            metric="Route Exceptions",
            value=total_route_exceptions,
            status=_status_for_count(total_route_exceptions),
            icon="pi pi-map",
            summary_items=[
                AnalyticsSummaryItemResponse(label="Missed Stops", value=0, drill_key="missed-stops"),
                AnalyticsSummaryItemResponse(label="Route Deviations", value=len(route_deviation_data), drill_key="route-deviation-events"),
                AnalyticsSummaryItemResponse(label="Total Exceptions", value=total_route_exceptions, drill_key=None),
            ],
        ),
        AnalyticsReportingTileResponse(
            id="compliance-violations",
            title="Driver & Bus Compliance",
            metric="Compliance Violations",
            value=total_violations,
            status=_status_for_count(total_violations),
            icon="pi pi-exclamation-triangle",
            summary_items=[
                AnalyticsSummaryItemResponse(label="Expired / Failed PRDP", value=len(pdp_fail_rows), drill_key="expired-pdp"),
                AnalyticsSummaryItemResponse(label="Expired Driver Licence", value=0, drill_key="expired-driver-licence"),
                AnalyticsSummaryItemResponse(label="Expired Route Licence", value=0, drill_key="expired-route-licence"),
                AnalyticsSummaryItemResponse(label="Failed Bus Licence Disk Scan", value=len(license_disk_fail_rows), drill_key="expired-bus-license-disk"),
                AnalyticsSummaryItemResponse(label="Total Violations", value=total_violations, drill_key=None),
            ],
        ),
        AnalyticsReportingTileResponse(
            id="bus-defects",
            title="Bus Defects",
            metric="Total Bus Defects",
            value=total_defects,
            status=_status_for_count(total_defects),
            icon="pi pi-exclamation-circle",
            summary_items=[
                *[
                    AnalyticsSummaryItemResponse(label=label, value=len(rows), drill_key=key)
                    for label, rows, key in [
                        ("Fire Extinguisher", defect_groups["Fire Extinguisher"], "fire-extinguisher-defects"),
                        ("Seats", defect_groups["Seats"], "seat-defects"),
                        ("Aisle", defect_groups["Aisle"], "aisle-obstructions"),
                        ("Tyres", defect_groups["Tyres"], "tyre-defects"),
                        ("Windows", defect_groups["Windows"], "window-defects"),
                        ("Other", defect_groups["Other"], "other-defects"),
                        ("Technical", defect_groups["Technical"], "technical-inspections"),
                    ]
                ],
                AnalyticsSummaryItemResponse(label="Total Defects", value=total_defects, drill_key=None),
            ],
        ),
        AnalyticsReportingTileResponse(
            id="overloaded-trips",
            title="Passenger Count",
            metric="Overloaded Trips",
            value=total_overloaded,
            status=_status_for_count(total_overloaded),
            icon="pi pi-users",
            summary_items=[
                AnalyticsSummaryItemResponse(label="Overloaded Trips", value=total_overloaded, drill_key="failed-passenger-counts"),
                AnalyticsSummaryItemResponse(label="Total", value=total_overloaded, drill_key=None),
            ],
        ),
        AnalyticsReportingTileResponse(
            id="delayed-departures",
            title="Schedule Adherence",
            metric="Delayed Departures",
            value=late_route_start_checks,
            status=_status_for_count(late_route_start_checks),
            icon="pi pi-clock",
            summary_items=[
                AnalyticsSummaryItemResponse(label="Route Starts (0-5 mins)", value=len(delayed_rows_by_interval["0-5 mins"]), drill_key="behind-schedule-0-5"),
                AnalyticsSummaryItemResponse(label="Behind Schedule (5-10 mins)", value=len(delayed_rows_by_interval["5-10 mins"]), drill_key="behind-schedule-5-10"),
                AnalyticsSummaryItemResponse(label="Behind Schedule (10-15 mins)", value=len(delayed_rows_by_interval["10-15 mins"]), drill_key="behind-schedule-10-15"),
                AnalyticsSummaryItemResponse(label="Behind Schedule (15+ mins)", value=len(delayed_rows_by_interval["15+ mins"]), drill_key="behind-schedule-15-plus"),
                AnalyticsSummaryItemResponse(label="Total Late Route Starts", value=late_route_start_checks, drill_key=None),
            ],
        ),
        AnalyticsReportingTileResponse(
            id="service-reliability",
            title="Service Reliability",
            metric="On-Time Performance",
            value=on_time_value,
            status=_status_for_percent(on_time_value),
            icon="pi pi-chart-line",
            summary_items=[
                AnalyticsSummaryItemResponse(label="Route Starts (0-5 mins)", value=len(delayed_rows_by_interval["0-5 mins"]), drill_key="behind-schedule-0-5"),
                AnalyticsSummaryItemResponse(label="Delayed Starts (5-10 mins)", value=len(delayed_rows_by_interval["5-10 mins"]), drill_key="behind-schedule-5-10"),
                AnalyticsSummaryItemResponse(label="Delayed Starts (10-15 mins)", value=len(delayed_rows_by_interval["10-15 mins"]), drill_key="behind-schedule-10-15"),
                AnalyticsSummaryItemResponse(label="Delayed Starts (15+ mins)", value=len(delayed_rows_by_interval["15+ mins"]), drill_key="behind-schedule-15-plus"),
                AnalyticsSummaryItemResponse(label="Total Late Route Starts", value=late_route_start_checks, drill_key=None),
            ],
        ),
        AnalyticsReportingTileResponse(
            id="operator-compliance",
            title="Monthly Contract Compliance",
            metric="Operator Compliance Score",
            value="N/A",
            status="warning",
            icon="pi pi-building",
            summary_items=[
                AnalyticsSummaryItemResponse(
                    label=row["operator"],
                    value=f"{row['shifts']} shifts, {row['inspections']} inspections, {row['passed']} passed, {row['failed']} failed",
                    drill_key="operator-compliance-summary",
                )
                for row in operator_drill_rows
            ]
            + [AnalyticsSummaryItemResponse(label="Total Operators", value=len(operator_drill_rows), drill_key=None)],
        ),
        AnalyticsReportingTileResponse(
            id="photo-evidence",
            title="Failed Inspections",
            metric="Failed Inspections by Type",
            value=total_failed,
            status=_status_for_count(total_failed),
            icon="pi pi-clipboard",
            summary_items=[
                AnalyticsSummaryItemResponse(label=label, value=len(rows), drill_key=key)
                for label, rows, key in [
                    ("External Inspections", failed_inspection_groups["External Inspections"], "failed-external-inspections"),
                    ("Internal Inspections", failed_inspection_groups["Internal Inspections"], "failed-internal-inspections"),
                    ("Driver Inspections", failed_inspection_groups["Driver Inspections"], "failed-driver-inspections"),
                    ("Passenger Counts", failed_inspection_groups["Passenger Counts"], "failed-passenger-counts"),
                    ("Technical Inspections", failed_inspection_groups["Technical Inspections"], "failed-technical-inspections"),
                ]
            ]
            + [AnalyticsSummaryItemResponse(label="Total Failed Inspections", value=total_failed, drill_key=None)],
        ),
        AnalyticsReportingTileResponse(
            id="fleet-health",
            title="Fleet Health",
            metric="Overall Analytics Score",
            value=fleet_health_value,
            status=_status_for_percent(fleet_health_value),
            icon="pi pi-wave-pulse",
            summary_items=[
                AnalyticsSummaryItemResponse(label="Under 50% Score", value=_to_int(fleet_bucket_rows.under_50), drill_key=None),
                AnalyticsSummaryItemResponse(label="Over 50% Score", value=_to_int(fleet_bucket_rows.over_50), drill_key=None),
                AnalyticsSummaryItemResponse(label="Over 80% Score", value=_to_int(fleet_bucket_rows.over_80), drill_key=None),
                AnalyticsSummaryItemResponse(label="Over 95% Score", value=_to_int(fleet_bucket_rows.over_95), drill_key=None),
                AnalyticsSummaryItemResponse(label="Overall Analytics Score", value=fleet_health_value, drill_key=None),
            ],
        ),
    ]

    return AnalyticsReportingSummaryResponse(
        generated_at=datetime.now(timezone.utc),
        source_date_from=report_date_row.source_date_from,
        source_date_to=report_date_row.source_date_to,
        tiles=tiles,
        drilldowns=drilldowns,
    )


@analytics_router.get(
    "/summary",
    response_model=AnalyticsSummaryResponse,
    responses={500: {"model": ErrorResponse}},
    operation_id="get_analytics_summary",
)
def get_analytics_summary(
    start_date: date | None = Query(
        None, description="Optional inclusive analytics start date."
    ),
    end_date: date | None = Query(
        None, description="Optional inclusive analytics end date."
    ),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> AnalyticsSummaryResponse:
    """Return the Analytics page summary from the loaded analytics schema."""

    del current_user
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date.",
        )

    params = _date_params(start_date, end_date)

    try:
        gauge_row = db.execute(
            text(
                """
                with filtered as (
                    select *
                    from analytics.bi_data
                    where (cast(:start_date as date) is null or bi_date >= cast(:start_date as date))
                      and (cast(:end_date as date) is null or bi_date <= cast(:end_date as date))
                ),
                latest_bi as (
                    select distinct on (vehiclereg)
                        vehiclereg,
                        bi_speed,
                        bi_acceleration,
                        bi_deceleration,
                        bi_cornering
                    from filtered
                    order by vehiclereg, bi_date desc
                )
                select
                    avg(bi_speed) as speeding,
                    avg(bi_cornering) as cornering,
                    avg(bi_acceleration) as acceleration,
                    avg(bi_deceleration) as braking
                from latest_bi
                """
            ),
            params,
        ).mappings().one()

        trip_row = db.execute(
            text(
                """
                select
                    coalesce(sum(tripdur), 0) as trip_duration_seconds,
                    coalesce(sum(speeddur), 0) as speed_duration_seconds,
                    coalesce(sum(excess_idle_seconds), 0) as excess_idle_seconds,
                    count(*) filter (where coalesce(riskfactor, 0) > 0) as high_risk_trips
                from analytics.trip_data
                where (cast(:start_date as date) is null or tripstart::date >= cast(:start_date as date))
                  and (cast(:end_date as date) is null or tripstart::date <= cast(:end_date as date))
                """
            ),
            params,
        ).mappings().one()

        top_inspection_row = db.execute(
            text(
                """
                select
                    count(*) filter (
                        where inspection_type in ('external', 'internal', 'driver', 'count', 'technical')
                    ) as total_inspections,
                    count(*) filter (
                        where inspection_type in ('external', 'internal', 'driver', 'count', 'technical')
                          and (
                            pass is false
                            or tyres_pass is false
                            or windows_pass is false
                            or ext_other_pass is false
                            or fire_extinguisher_present is false
                            or seats_pass is false
                            or aisle_pass is false
                            or int_other_pass is false
                            or prdp_scan_succeeded is false
                            or driver_identified is false
                            or (inspection_type = 'count' and coalesce(number_standing, 0) > 0)
                          )
                    ) as failed_inspections
                from inspections.inspections
                where (cast(:start_date as date) is null or inspection_time::date >= cast(:start_date as date))
                  and (cast(:end_date as date) is null or inspection_time::date <= cast(:end_date as date))
                """
            ),
            params,
        ).mappings().one()

        failed_inspection_type_rows = db.execute(
            text(
                """
                select
                    inspection_type,
                    count(*) filter (
                        where pass is false
                           or tyres_pass is false
                           or windows_pass is false
                           or ext_other_pass is false
                           or fire_extinguisher_present is false
                           or seats_pass is false
                           or aisle_pass is false
                           or int_other_pass is false
                           or prdp_scan_succeeded is false
                           or driver_identified is false
                           or (inspection_type = 'count' and coalesce(number_standing, 0) > 0)
                    ) as failed_count
                from inspections.inspections
                where inspection_type in ('external', 'internal', 'driver', 'count', 'technical')
                  and (cast(:start_date as date) is null or inspection_time::date >= cast(:start_date as date))
                  and (cast(:end_date as date) is null or inspection_time::date <= cast(:end_date as date))
                group by inspection_type
                """
            ),
            params,
        ).mappings().all()

        delayed_interval_rows = db.execute(
            text(
                """
                select
                    behind_schedule_interval as interval,
                    count(*) as delayed_count
                from inspections.inspections
                where inspection_type = 'behind_schedule'
                  and (cast(:start_date as date) is null or inspection_time::date >= cast(:start_date as date))
                  and (cast(:end_date as date) is null or inspection_time::date <= cast(:end_date as date))
                group by behind_schedule_interval
                """
            ),
            params,
        ).mappings().all()

        delayed_trend_rows = db.execute(
            text(
                """
                select
                    inspection_time::date as delay_date,
                    count(*) filter (
                        where behind_schedule_interval in ('5-10 mins', '10-15 mins', '15+ mins')
                    ) as delayed_count,
                    count(*) filter (
                        where behind_schedule_interval in ('10-15 mins', '15+ mins')
                    ) as major_delay_count
                from inspections.inspections
                where inspection_type = 'behind_schedule'
                  and (cast(:start_date as date) is null or inspection_time::date >= cast(:start_date as date))
                  and (cast(:end_date as date) is null or inspection_time::date <= cast(:end_date as date))
                group by inspection_time::date
                order by inspection_time::date
                """
            ),
            params,
        ).mappings().all()

        top_route_row = db.execute(
            text(
                """
                select
                    count(*) as total_trips,
                    count(*) filter (where routescore >= 80) as compliant_trips,
                    avg(routescore) as avg_route_score,
                    max(routescore) as max_route_score,
                    max(routevar) as max_route_variance
                from analytics.trip_data
                where (cast(:start_date as date) is null or tripstart::date >= cast(:start_date as date))
                  and (cast(:end_date as date) is null or tripstart::date <= cast(:end_date as date))
                """
            ),
            params,
        ).mappings().one()

        top_fleet_row = db.execute(
            text(
                """
                with filtered as (
                    select *
                    from analytics.bi_data
                    where (cast(:start_date as date) is null or bi_date >= cast(:start_date as date))
                      and (cast(:end_date as date) is null or bi_date <= cast(:end_date as date))
                ),
                latest_bi as (
                    select distinct on (vehiclereg) vehiclereg, bi_total
                    from filtered
                    order by vehiclereg, bi_date desc
                )
                select count(*) as vehicle_count, avg(bi_total) as avg_fleet_score
                from latest_bi
                """
            ),
            params,
        ).mappings().one()

        date_row = db.execute(
            text(
                """
                select min(source_date) as source_date_from, max(source_date) as source_date_to
                from (
                    select bi_date as source_date
                    from analytics.bi_data
                    where (cast(:start_date as date) is null or bi_date >= cast(:start_date as date))
                      and (cast(:end_date as date) is null or bi_date <= cast(:end_date as date))
                    union all
                    select tripstart::date as source_date
                    from analytics.trip_data
                    where (cast(:start_date as date) is null or tripstart::date >= cast(:start_date as date))
                      and (cast(:end_date as date) is null or tripstart::date <= cast(:end_date as date))
                ) source_dates
                """
            ),
            params,
        ).mappings().one()

        vehicle_rows = db.execute(
            text(
                """
                with trip_rollup as (
                    select
                        vehiclereg,
                        max(vehiclealias) as vehiclealias,
                        max(vehiclegroup) as vehiclegroup,
                        coalesce(sum(distance), 0) as distance,
                        coalesce(sum(tripdur), 0) as trip_duration_seconds,
                        coalesce(sum(speeddur), 0) as speed_duration_seconds,
                        coalesce(sum(excess_idle_seconds), 0) as excess_idle_seconds,
                        count(*) filter (where coalesce(riskfactor, 0) > 0) as high_risk_trips,
                        avg(stylescore) as avg_style_score
                    from analytics.trip_data
                    where (cast(:start_date as date) is null or tripstart::date >= cast(:start_date as date))
                      and (cast(:end_date as date) is null or tripstart::date <= cast(:end_date as date))
                    group by vehiclereg
                ),
                latest_bi as (
                    select distinct on (vehiclereg)
                        vehiclereg,
                        bi_total
                    from analytics.bi_data
                    where (cast(:start_date as date) is null or bi_date >= cast(:start_date as date))
                      and (cast(:end_date as date) is null or bi_date <= cast(:end_date as date))
                    order by vehiclereg, bi_date desc
                )
                select
                    t.vehiclereg,
                    t.vehiclealias,
                    t.vehiclegroup,
                    t.distance,
                    t.trip_duration_seconds,
                    t.speed_duration_seconds,
                    t.excess_idle_seconds,
                    t.high_risk_trips,
                    coalesce(b.bi_total, t.avg_style_score, 0) as score
                from trip_rollup t
                left join latest_bi b on b.vehiclereg = t.vehiclereg
                order by coalesce(b.bi_total, t.avg_style_score, 0), t.vehiclereg
                """
            ),
            params,
        ).mappings().all()

        event_rows = db.execute(
            text(
                """
                select
                    vehiclereg,
                    vehiclealias,
                    vehiclegroup,
                    location_name,
                    event_date,
                    event_id,
                    duration,
                    max_speed,
                    speed_limit
                from analytics.events
                where (cast(:start_date as date) is null or event_date::date >= cast(:start_date as date))
                  and (cast(:end_date as date) is null or event_date::date <= cast(:end_date as date))
                order by event_date desc
                limit 25
                """
            ),
            params,
        ).mappings().all()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not load analytics summary")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load analytics summary.",
        ) from exc

    gauge_scores = [
        AnalyticsGaugeScoreResponse(label="Speeding", score=_score(gauge_row.speeding), color="#1d4ed8"),
        AnalyticsGaugeScoreResponse(label="Cornering", score=_score(gauge_row.cornering), color="#16a34a"),
        AnalyticsGaugeScoreResponse(label="Acceleration", score=_score(gauge_row.acceleration), color="#d97706"),
        AnalyticsGaugeScoreResponse(label="Braking", score=_score(gauge_row.braking), color="#dc2626"),
    ]

    total_inspections = _to_int(top_inspection_row.total_inspections)
    failed_inspections = _to_int(top_inspection_row.failed_inspections)
    failed_value = _format_percent(failed_inspections, total_inspections)
    failed_counts_by_type = {
        row.inspection_type: _to_int(row.failed_count)
        for row in failed_inspection_type_rows
    }
    failed_summary_items = [
        AnalyticsSummaryItemResponse(
            label=FAILED_INSPECTION_LABELS[inspection_type],
            value=failed_counts_by_type.get(inspection_type, 0),
            drill_key=f"failed-{FAILED_INSPECTION_LABELS[inspection_type].lower().replace(' ', '-')}",
        )
        for inspection_type in COMPLETED_INSPECTION_TYPES
    ]
    failed_summary_items.append(
        AnalyticsSummaryItemResponse(
            label="Total Failed Inspections",
            value=failed_inspections,
            drill_key=None,
        )
    )

    fleet_vehicle_count = _to_int(top_fleet_row.vehicle_count)
    fleet_health_value = (
        f"{_score(top_fleet_row.avg_fleet_score)}%" if fleet_vehicle_count > 0 else "N/A"
    )

    route_total = _to_int(top_route_row.total_trips)
    route_score_available = (
        _to_float(top_route_row.max_route_score) > 0
        or _to_float(top_route_row.max_route_variance) > 0
    )
    if route_total > 0 and route_score_available:
        route_compliant = _to_int(top_route_row.compliant_trips)
        route_value = f"{_score(top_route_row.avg_route_score)}%"
        route_secondary = f"{route_compliant:,}/{route_total:,}"
    else:
        route_value = "N/A"
        route_secondary = "No route score data"

    delayed_counts = {
        row.interval or "Unknown": _to_int(row.delayed_count)
        for row in delayed_interval_rows
    }
    delayed_0_5 = delayed_counts.get("0-5 mins", 0)
    delayed_5_10 = delayed_counts.get("5-10 mins", 0)
    delayed_10_15 = delayed_counts.get("10-15 mins", 0)
    delayed_15_plus = delayed_counts.get("15+ mins", 0)
    on_time_count, late_route_start_count, total_route_start_count = (
        _route_start_interval_counts(delayed_counts)
    )
    on_time_value = _format_percent(on_time_count, total_route_start_count)
    service_reliability_items = [
        AnalyticsSummaryItemResponse(
            label="Route Starts (0-5 mins)",
            value=delayed_0_5,
            drill_key="behind-schedule-0-5",
        ),
        AnalyticsSummaryItemResponse(
            label="Delayed Starts (5-10 mins)",
            value=delayed_5_10,
            drill_key="behind-schedule-5-10",
        ),
        AnalyticsSummaryItemResponse(
            label="Delayed Starts (10-15 mins)",
            value=delayed_10_15,
            drill_key="behind-schedule-10-15",
        ),
        AnalyticsSummaryItemResponse(
            label="Delayed Starts (15+ mins)",
            value=delayed_15_plus,
            drill_key="behind-schedule-15-plus",
        ),
        AnalyticsSummaryItemResponse(
            label="Total Late Route Starts",
            value=late_route_start_count,
            drill_key=None,
        ),
    ]
    service_reliability_trend = AnalyticsTrendResponse(
        dates=[str(row.delay_date) for row in delayed_trend_rows],
        series=[
            AnalyticsTrendSeriesResponse(
                name="Late Route Starts",
                data=[_to_int(row.delayed_count) for row in delayed_trend_rows],
            ),
            AnalyticsTrendSeriesResponse(
                name="Major Delays",
                data=[_to_int(row.major_delay_count) for row in delayed_trend_rows],
            ),
        ],
    )

    top_kpis = [
        AnalyticsTopKpiResponse(
            id="service-reliability",
            value=on_time_value,
            secondary_text=f"{on_time_count:,}/{total_route_start_count:,}",
            status=_status_for_percent(on_time_value),
            summary_items=service_reliability_items,
            trend=service_reliability_trend,
        ),
        AnalyticsTopKpiResponse(
            id="operator-compliance",
            value=route_value,
            secondary_text=route_secondary,
            status=_status_for_percent(route_value),
        ),
        AnalyticsTopKpiResponse(
            id="photo-evidence",
            value=failed_value,
            secondary_text=f"{failed_inspections:,}/{total_inspections:,}",
            status=_status_for_percent(failed_value, inverse=True),
            summary_items=failed_summary_items,
        ),
        AnalyticsTopKpiResponse(
            id="fleet-health",
            value=fleet_health_value,
            status=_status_for_percent(fleet_health_value),
        ),
    ]

    metric_tiles = [
        AnalyticsMetricTileResponse(
            title="Trip duration",
            icon="pi pi-stopwatch",
            color="#16a34a",
            primary=_format_duration(trip_row.trip_duration_seconds),
        ),
        AnalyticsMetricTileResponse(
            title="Speed duration",
            icon="pi pi-gauge",
            color="#d97706",
            primary=_format_duration(trip_row.speed_duration_seconds),
        ),
        AnalyticsMetricTileResponse(
            title="Excess idle duration",
            icon="pi pi-clock",
            color="#7c3aed",
            primary=_format_duration(trip_row.excess_idle_seconds),
        ),
        AnalyticsMetricTileResponse(
            title="High risk trips",
            icon="pi pi-exclamation-circle",
            color="#dc2626",
            primary=f"{_to_int(trip_row.high_risk_trips):,}",
        ),
        AnalyticsMetricTileResponse(
            title="Accidents",
            icon="pi pi-exclamation-triangle",
            color="#b91c1c",
            primary="0",
        ),
    ]

    vehicle_performance: list[AnalyticsVehiclePerformanceResponse] = []
    vehicle_scores: list[AnalyticsVehicleScoreResponse] = []
    for row in vehicle_rows:
        fleet_no, registration = _split_vehicle_label(row.vehiclereg, row.vehiclealias)
        operator = _operator_label(row.vehiclegroup)
        score = _score(row.score)
        vehicle_performance.append(
            AnalyticsVehiclePerformanceResponse(
                fleet_no=fleet_no,
                registration=registration,
                operator=operator,
                distance=_format_distance(row.distance),
                trip_duration=_format_duration(row.trip_duration_seconds),
                speed_duration=_format_duration(row.speed_duration_seconds),
                idle_duration=_format_duration(row.excess_idle_seconds),
                high_risk_trips=_to_int(row.high_risk_trips),
                score=score,
            )
        )
        vehicle_scores.append(
            AnalyticsVehicleScoreResponse(
                fleet_no=fleet_no,
                registration=registration,
                operator=operator,
                score=score,
            )
        )

    last_events: list[AnalyticsLastEventResponse] = []
    for row in event_rows:
        fleet_no, registration = _split_vehicle_label(row.vehiclereg, row.vehiclealias)
        last_events.append(
            AnalyticsLastEventResponse(
                bus=f"{fleet_no} / {registration}",
                location=row.location_name or "-",
                time=row.event_date,
                event_type=_event_type(row.event_id),
                measurement=_event_measurement(row),
                operator=_operator_label(row.vehiclegroup),
            )
        )

    return AnalyticsSummaryResponse(
        generated_at=datetime.now(timezone.utc),
        source_date_from=date_row.source_date_from,
        source_date_to=date_row.source_date_to,
        top_kpis=top_kpis,
        gauge_scores=gauge_scores,
        metric_tiles=metric_tiles,
        last_events=last_events,
        vehicle_performance=vehicle_performance,
        vehicle_scores=vehicle_scores,
    )
