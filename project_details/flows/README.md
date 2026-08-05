# Flow Documentation

This folder describes the business and technical flow for major FS Bus dashboard components.

Use these files when changing KPI methodology, API aggregation logic, frontend component behavior, or deployment/runtime assumptions.

Current flow docs:

- `reporting_dashboard_flow.md` - Reporting dashboard methodology, data grain, API/frontend logic, and infrastructure notes.
- `vehicle_and_monitor_drilldowns_flow.md` - Per-vehicle event/trip matching, high-risk trip logic, and monitor drilldown methodology.

## Shifts Table Lazy Loading

The Shifts page uses PrimeNG `p-table` server-side lazy loading.

Frontend behavior:

- `p-table` is configured with `[lazy]="true"`.
- `(onLazyLoad)` sends PrimeNG's `first`, `rows`, `sortField`, `sortOrder`, and the global search value to the API.
- The page fetches only the visible shift page.
- Inspection expansion still works by fetching inspection groups only for the visible shift IDs.
- Shift expansion lookups rely on the inspection read endpoints returning all matching rows when no explicit `limit` is supplied. This avoids a mismatch where a shift row count is correct but the expansion is empty because the grouped-inspection request was capped before that shift's rows were reached.
- Expanded shift rows group inspection cards by bus/fleet/duty inside PrimeNG fieldsets, so bus identity is shown once per group instead of repeated on every inspection card.

Backend behavior:

- `GET /shift/shifts/paged` returns `{ items, total, first, rows }`.
- The endpoint applies search, sort, offset, and limit in SQL.
- The endpoint includes `inspection_count` and `failed_inspection_count` per shift via a grouped inspection subquery.
- Existing `GET /shift/shifts` remains available for current consumers that still need the non-paged list.

## Monitor Shift Counts

The Monitors page first loads `GET /shift/monitors/summary` to populate the monitor selector and aggregate summary cards quickly. That endpoint reads monitor/supervisor users from `app_auth.app_user` and also includes unknown user IDs that have shift rows.

After a monitor is selected, the page loads only that monitor's shifts through `GET /shift/shifts?user_id=<firebase_uid>` and then fetches inspection groups in chunks by shift ID. The monitor summary cards use the summary endpoint counts, while the top chart and shift table use the loaded per-row `inspectionCount` value so row-level details stay aligned.

Expanded monitor shift rows use the same bus/fleet/duty fieldset grouping as the Shifts page.

## Shift Selfies

Shift selfies are stored in `photos.selfies` and loaded through `GET /image/selfies/by_shift_ids`.

Frontend behavior:

- The Monitors page fetches selfies for the loaded shift IDs alongside inspection groups.
- The selected monitor's latest selfie is derived by sorting that monitor's shift selfies by `timestamp` descending.
- Expanded monitor and shift rows show shift selfie thumbnails with PrimeNG image preview.
- Expanded monitor and shift rows also render a chronological timeline that interleaves shift selfies and inspection events by timestamp.
- Selfies are displayed at shift level because they belong to the monitor shift, not to a specific bus inspection row.
