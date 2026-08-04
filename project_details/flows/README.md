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
- Expanded shift rows group inspection cards by bus/fleet/duty inside PrimeNG fieldsets, so bus identity is shown once per group instead of repeated on every inspection card.

Backend behavior:

- `GET /shift/shifts/paged` returns `{ items, total, first, rows }`.
- The endpoint applies search, sort, offset, and limit in SQL.
- The endpoint includes `inspection_count` and `failed_inspection_count` per shift via a grouped inspection subquery.
- Existing `GET /shift/shifts` remains available for current consumers that still need the non-paged list.

## Monitor Shift Counts

The Monitors page loads shifts for the selected monitor and then fetches inspection groups in chunks by shift ID. The monitor summary cards, top chart, and shift table all use the same per-row `inspectionCount` value so totals stay aligned after the shift table inspection-count fix.

Expanded monitor shift rows use the same bus/fleet/duty fieldset grouping as the Shifts page.
