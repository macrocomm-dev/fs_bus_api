# Reporting Dashboard Flow

## Component Scope

The Reporting dashboard is the main operational summary page for bus inspections, route-start performance, route compliance, failed inspections, defects, passenger counts, and fleet health.

Frontend component:

- `frontend/app/src/app/features/reporting/reporting.component.ts`
- `frontend/app/src/app/features/reporting/reporting.component.html`
- `frontend/app/src/app/features/reporting/reporting.component.css`

Backend component:

- `app/routers/analytics.py`
- `GET /analytics/reporting-summary`
- `GET /analytics/summary`

## Data Grain

The system has two important grains that must not be mixed:

- `shifts.shifts`
  - One row is one monitor inspection session.
  - A shift belongs to the person doing inspections.
  - A shift can contain many buses.
  - A shift is not a bus, route, or departure.
- `inspections.inspections`
  - One row is one collected inspection event.
  - The row carries bus identifiers such as `bus_id` and `fleet_number`.
  - For route-start punctuality, rows with `inspection_type = 'behind_schedule'` represent inspected bus route-start checks.

Because one shift can inspect many buses, bus punctuality KPIs must use inspection rows, not distinct `shift_id` values.

## On-Time Performance Methodology

Current source:

- `inspections.inspections`
- Filter: `inspection_type = 'behind_schedule'`
- Date filter: `inspection_time::date` within the selected date range.

Current interval treatment:

- `0-5 mins`: on-time / acceptable route-start check.
- `5-10 mins`: late route-start check.
- `10-15 mins`: late route-start check and major-delay candidate.
- `15+ mins`: late route-start check and major-delay candidate.

Current top KPI formula:

```text
on_time_count = count(behind_schedule rows where behind_schedule_interval = '0-5 mins')
total_route_start_checks = count(behind_schedule rows where interval is one of the four known buckets)
on_time_percentage = on_time_count / total_route_start_checks
secondary_text = on_time_count / total_route_start_checks
```

Current delayed-departures card formula:

```text
late_route_start_count =
  count('5-10 mins') +
  count('10-15 mins') +
  count('15+ mins')
```

The breakdown still shows all four interval buckets so the product owner can see the full distribution.

## Pass/Fail Logic

Do not use `inspections.inspections.pass` for on-time performance.

Reason:

- The behind-schedule ingestion flow stores `behind_schedule_interval`.
- It does not currently derive a meaningful `pass = false` value from that interval.
- The pass/fail meaning for route starts is therefore interval-based.

For inspection-quality cards, failures are derived from the parent `pass` field and the type-specific check fields.

Failed-inspection denominator:

- external inspections
- internal inspections
- driver inspections
- passenger counts
- technical inspections

Excluded from failed-inspection denominator:

- `behind_schedule` route-start rows, because they feed the on-time performance KPI.

Derived failed-inspection rules:

- Parent `pass = false` is a failure.
- Any failed subclass check is a failure:
  - tyres
  - windows
  - exterior other
  - fire extinguisher
  - seats
  - aisle
  - interior other
  - PRDP scan
  - driver identified
- Passenger count rows with `number_standing > 0` are treated as overloaded passenger-count failures until capacity data is available.

Do not rely only on `pass = false` for reporting failed inspections. Some source rows can carry the failure on the subclass field while the parent field is missing or not meaningful for that inspection type.

## Driver And Bus Compliance Methodology

Current source:

- `inspections.inspections`

Current categories:

- Expired / failed PRDP
- Expired driver licence
- Expired route licence
- Failed bus licence disk scan

Current bus licence disk logic:

- `license_disk_scan_succeeded` is collected at bus level in the incoming shift payload.
- The ingestion flow copies that bus-level value onto every inspection row created for that bus.
- The reporting endpoint therefore deduplicates licence disk failures before counting them.

Current dedupe key:

```text
shift_id + bus_id + fleet_number + duty_number + replacement_bus
```

Reason:

- One monitor shift can include multiple buses.
- One bus within a shift can create multiple inspection rows.
- A single failed licence disk scan must not be counted once per inspection row.

The compliance card count is therefore a count of unique failed bus licence disk scan attempts, not a count of inspection rows.

## Frontend Logic

The reporting component loads real data from generated Angular API services backed by:

- `GET /analytics/reporting-summary` for dashboard cards and drilldown rows.
- `GET /analytics/summary` for the top KPI row and analytics-backed summaries.

Static frontend tile definitions are used only as loading/order shells while the API response is in flight. The displayed KPI methodology must come from the backend response.

Daily Bus Monitoring comparison chart:

- Categories are inspection types.
- Bars are split by operator when the backend provides `chart_series`.
- Operator resolution comes from the inspection-to-vehicle join.
- Rows that cannot resolve to a vehicle operator are grouped under `Unassigned`.

Expanded card bar charts:

- Each metric category maps to its drilldown rows through `drill_key`.
- The frontend groups those drilldown rows by the `operator` field.
- When operator-bearing rows exist, the bar chart uses stacked colored series per operator.
- When no operator-bearing rows exist, the chart falls back to a single `Total` series.

The top KPI row uses:

- `value`: backend percentage string.
- `secondaryText`: backend count string such as `308/323`.
- `summaryItems`: backend interval breakdown.
- `trendData`: backend daily late-start trend.

## Backend Logic

`app/routers/analytics.py` owns the reporting aggregation logic.

Shared route-start constants:

- `ROUTE_START_INTERVALS`
- `ON_TIME_ROUTE_START_INTERVALS`
- `MAJOR_DELAY_INTERVALS`

Shared helper:

- `_route_start_interval_counts(counts_by_interval)`

Both `GET /analytics/reporting-summary` and `GET /analytics/summary` must use this same route-start logic so the top KPI and expanded cards remain consistent.

## Data Quality Notes

Known limitations:

- The KPI only includes inspected route-start checks. It cannot yet include scheduled starts that were never inspected.
- The `0-5 mins` threshold is a product/business rule and should be reconfirmed if the client changes the SLA.
- Unknown or new `behind_schedule_interval` values are not shown in the four-bucket UI until explicitly mapped.

## Architecture And Infrastructure

Runtime architecture:

- Angular + PrimeNG frontend.
- FastAPI backend.
- PostgreSQL Cloud SQL database.
- Generated Angular API client from backend OpenAPI.

Local development:

- `scripts/start.sh` starts the Cloud SQL proxy, FastAPI API, and Angular dev server.
- `scripts/stop.sh` stops local services.

Deployment:

- Backend deploys to Cloud Run.
- Frontend deploys to Firebase Hosting.
- Runtime configuration and integration secrets are provided through environment variables and Google Secret Manager.

OpenAPI impact:

- This change reuses existing response fields and does not require API interface regeneration.
