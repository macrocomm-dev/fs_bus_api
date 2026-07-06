# Reporting and Model Changes - 2026-07-06

## Context

These changes follow a review of the product owner's reporting-page feedback and a comparison between the API ORM models and the live PostgreSQL Cloud SQL database.

## Reporting Page Changes

### Replaced separate date inputs with a date range picker

Files changed:

- `frontend/app/src/app/features/reporting/reporting.component.html`
- `frontend/app/src/app/features/reporting/reporting.component.ts`
- `frontend/app/src/app/features/reporting/reporting.component.css`

Reasoning:

The filter row previously used two separate PrimeNG date inputs, `Date From` and `Date To`. The dashboard now uses a single PrimeNG range picker, which better matches the expected reporting workflow and reduces filter-row clutter.

The underlying applied filter shape still uses `dateFrom` and `dateTo`, so the selected range is normalized back into those two values when filters are applied. This preserves the existing local filtering behavior and keeps future API query parameters straightforward.

### Removed the icon before Breakdown

File changed:

- `frontend/app/src/app/features/reporting/reporting.component.html`

Reasoning:

The product owner requested removal of the three-line icon before the "Breakdown" heading. The heading now renders as plain text while keeping the existing drill-down hint.

### Removed Roadworthiness Failures from Compliance

File changed:

- `frontend/app/src/app/features/reporting/reporting.component.ts`

Reasoning:

The product owner requested that roadworthiness failure be removed from the compliance block. The `Roadworthiness Failures` summary item was removed from the `Driver & Bus Compliance` KPI card, and the default total was adjusted from `11` to `6` to match the remaining compliance categories:

- Expired PDP
- Expired Driver Licence
- Expired Route Licence

## API Model Changes

### Aligned models with live database tables

Files changed:

- `app/models/bus_inspection.py`
- `app/models/master_data.py`
- `app/models/app_auth.py`
- `app/models/audit.py`
- `app/models/__init__.py`

Reasoning:

The live PostgreSQL database was inspected through the local Cloud SQL proxy. The following application tables are present and queryable:

- `app_auth.app_user`
- `audit.api_error_log`
- `inspections.inspections`
- `master_data.operator`
- `master_data.route`
- `master_data.route_stop`
- `master_data.vehicle`
- `photos.photos`
- `photos.selfies`
- `shifts.shifts`

The ORM models now better reflect those tables.

### Added `BusInspection.created_at`

File changed:

- `app/models/bus_inspection.py`

Reasoning:

The live `inspections.inspections` table contains a nullable `created_at` column with a `now()` default. The ORM model did not include it, so it was added to make the model complete for the current table shape.

### Matched `BusInspection.user_id` nullability

File changed:

- `app/models/bus_inspection.py`

Reasoning:

The live `inspections.inspections.user_id` column is nullable. The ORM previously modeled it as non-nullable. The model was updated to avoid drift between SQLAlchemy metadata and the live database.

### Matched `Vehicle.date_of_1st_reg` type

File changed:

- `app/models/master_data.py`

Reasoning:

The live `master_data.vehicle.date_of_1st_reg` column is a PostgreSQL `date`, not a timestamp. The ORM type annotation was changed from `datetime | None` to `date | None`.

### Exported `Operator`

File changed:

- `app/models/__init__.py`

Reasoning:

`Operator` is a real live table model and is imported directly in routers. It should also be exported from `app.models` alongside the other model classes.

### Added model relationships

Files changed:

- `app/models/master_data.py`
- `app/models/app_auth.py`

Reasoning:

Relationships were added between related live tables so SQLAlchemy can navigate common domain links:

- `Operator.routes`
- `Operator.vehicles`
- `Operator.app_users`
- `Route.operator`
- `Route.stops`
- `RouteStop.route`
- `Vehicle.operator`
- `AppUser.operator`

These relationships match existing foreign-key usage in the routers and make future reporting/query work easier.

### Cleaned duplicate import

File changed:

- `app/models/audit.py`

Reasoning:

`BigInteger` was imported twice. The duplicate import was removed as a small cleanup while touching the model files.

## Verification

The following checks were completed:

- Angular build passes with the existing bundle/CSS budget warnings.
- SQLAlchemy mapper configuration passes.
- Read-only ORM smoke test successfully queried all 10 live app DB tables.

`pytest` was not run because `pytest` is not installed in the current Python environment.

## Notes

The reporting page still uses local mock data from `DRILL_CONFIGS`; it does not query the API or database yet.

The codebase still contains legacy `operations.*` ORM models, but the live database currently does not contain the matching `operations` schema tables.
