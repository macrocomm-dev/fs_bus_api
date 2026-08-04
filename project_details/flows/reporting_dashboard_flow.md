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

Reports uses the shared dashboard filter component:

```text
frontend/app/src/app/core/components/dashboard-filters/
frontend/app/src/app/core/services/dashboard-filter.service.ts
```

The shared filter service stores both draft and applied values, so date/operator selections persist when the user navigates between Reports and Analytics.

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

## Shift Payload Audit Trail

Successful JSON submissions to `POST /shift/create_shift/` can be written to the same audit table used for malformed and failed payloads:

```text
audit.api_error_log
```

The table's `ck_api_error_log_status_code` constraint must allow standard HTTP response codes from `100` to `599`. It originally allowed only `400-599`, which prevented `201` success and normalization audit rows from being inserted.

This is controlled by:

```text
AUDIT_SUCCESS_PAYLOADS_ENABLED=true|false
```

When the flag is `true`, the shift endpoint schedules the success audit write as a FastAPI background task after the shift, selfie, and inspection records have been created. This keeps the monitor request from waiting on the audit insert.

The success audit task receives the already-validated `ShiftCreate` payload via `model_dump(mode="json")`. Do not rely on reading `request.body()` inside the background task for this endpoint, because the ASGI request stream may no longer be available after the response has been prepared.

Before scheduling the background task, the endpoint snapshots request metadata such as method, path, query string, request ID, user agent, client IP, device ID, and authorization header. Background success/normalization audit writes should use that snapshot instead of reading the live `Request` object.

Success rows use:

```text
status_code = 201
error_category = SUCCESS
error_code = SHIFT_CREATED
error_message = Shift created successfully: shift_id=<id>
request_body = validated ShiftCreate payload stored through model_dump(mode="json")
```

The Cloud Run deployment workflow reads the GitHub Actions variable `AUDIT_SUCCESS_PAYLOADS_ENABLED` and falls back to `true` so successful mobile payloads are captured during the inspection investigation window. Set that variable to `false` once the payload question is resolved.

Failure rows continue to use the existing exception-handler flow:

```text
error_category = VALIDATION_ERROR | HTTP_ERROR | INTERNAL_ERROR
validation_errors = structured validation details where available
error_message = failure reason
request_body = captured request JSON when available and below the error-body size cap
```

## Behind-Schedule Interval Compatibility

The mobile app has submitted invalid `behind_schedule_interval` values for late-route reports, most commonly a blank string:

```json
{
  "behind_schedule_interval": ""
}
```

The canonical allowed values remain:

```text
0-5 mins
5-10 mins
10-15 mins
15+ mins
```

Temporary compatibility rule:

- Any value outside the allowed set is defaulted to `0-5 mins`.
- This prevents the whole `POST /shift/create_shift/` payload from failing with a Pydantic enum validation error.
- The mobile app should still validate that a real interval is selected before submission; the API default is only a defensive capture rule.

When the API repairs one or more invalid behind-schedule intervals and the shift is saved, it writes an audit row:

```text
status_code = 201
error_category = PAYLOAD_NORMALIZED
error_code = BEHIND_SCHEDULE_INTERVAL_DEFAULTED
error_message = Invalid behind_schedule_interval value defaulted to 0-5 mins: shift_id=<id>
request_body.repairs = list of repaired paths, original values, bus identifiers, and inspection timestamps
```

Audit query:

```sql
select occurred_at, error_message, request_body
from audit.api_error_log
where error_category = 'PAYLOAD_NORMALIZED'
  and error_code = 'BEHIND_SCHEDULE_INTERVAL_DEFAULTED'
order by occurred_at desc;
```

Reason:

- Inspection pass/fail investigations sometimes need to prove whether a mobile client explicitly sent a checklist value, such as `external.other.pass_ = false`, or omitted it and allowed the API schema default to apply.
- Successful payload capture currently stores the validated `ShiftCreate` payload passed into the background task. For forensic checks of omitted/defaulted fields, use the normalization audit rows above or failed-payload audit rows where the original request body is captured.
- Successful payload capture can increase audit-table storage because shift requests can contain inline image data. Keep it enabled only while the extra forensic detail is needed.

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
