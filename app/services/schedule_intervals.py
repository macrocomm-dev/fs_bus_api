"""Shared report categories; preserve the meaning of older offline captures."""

from app.schemas.shift import BehindScheduleInterval

# (stored value, display label, drilldown key). Old keys stay valid for clients.
ROUTE_START_BANDS = (
    (BehindScheduleInterval.early_departure.value, "Early departure", "behind-schedule-early"),
    (BehindScheduleInterval.zero_to_five.value, "On time (0-5 mins)", "behind-schedule-0-5"),
    (BehindScheduleInterval.six_to_fifteen_late.value, "6–15 minutes late", "behind-schedule-6-15"),
    (BehindScheduleInterval.fifteen_to_thirty_late.value, "15–30 minutes late", "behind-schedule-15-30"),
    (BehindScheduleInterval.thirty_plus_late.value, "30 minutes or more late", "behind-schedule-30-plus"),
    (BehindScheduleInterval.five_to_ten.value, "5–10 mins late (legacy)", "behind-schedule-5-10"),
    (BehindScheduleInterval.ten_to_fifteen.value, "10–15 mins late (legacy)", "behind-schedule-10-15"),
    (BehindScheduleInterval.fifteen_plus.value, "15+ mins late (legacy)", "behind-schedule-15-plus"),
)
ROUTE_START_INTERVALS = tuple(value for value, _, _ in ROUTE_START_BANDS)
ON_TIME_ROUTE_START_INTERVALS = {BehindScheduleInterval.zero_to_five.value}
EARLY_ROUTE_START_INTERVALS = {BehindScheduleInterval.early_departure.value}
LATE_ROUTE_START_INTERVALS = set(ROUTE_START_INTERVALS) - ON_TIME_ROUTE_START_INTERVALS - EARLY_ROUTE_START_INTERVALS
MAJOR_DELAY_INTERVALS = {
    BehindScheduleInterval.fifteen_to_thirty_late.value,
    BehindScheduleInterval.thirty_plus_late.value,
    # Older reports keep the historical major-delay definition.
    BehindScheduleInterval.ten_to_fifteen.value,
    BehindScheduleInterval.fifteen_plus.value,
}
LEGACY_ROUTE_START_INTERVALS = {
    BehindScheduleInterval.five_to_ten.value,
    BehindScheduleInterval.ten_to_fifteen.value,
    BehindScheduleInterval.fifteen_plus.value,
}


def visible_route_start_bands(counts_by_interval):
    """Always show current choices; show old bands only when they have data."""
    return [
        band for band in ROUTE_START_BANDS
        if band[0] not in LEGACY_ROUTE_START_INTERVALS or counts_by_interval.get(band[0], 0)
    ]
