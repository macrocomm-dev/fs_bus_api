# Route Departure Timetables

## Storage and identifiers

`routes.departure` stores scheduled departures, separately from existing
`master_data.route` definitions and `master_data.route_stop` geography.
There is no confirmed mapping between timetable duty numbers and route codes;
do not equate those identifiers.

Each departure has a UUID `uid`, a `schedule_uid`, and the seven source fields:
`duty_no`, `departure`, `origin`, `destination`, `direction`, `valid_days`,
`bus_type`. Duty numbers remain text, preserving leading zeros. Departure times
are local `Africa/Johannesburg` times stored as PostgreSQL `time` and exported
as `HH:MM`. Day groups and bus types retain the source's text values.

`routes.schedule_version` records each full operator timetable, including a
UUID, operator ID, source filename, canonical content SHA-256, row count,
publication timestamp, and active flag. Only one version per operator can be
active, enforced by a partial unique index.

UUIDs identify records within a published version. A new version creates new
departure UUIDs; they are not permanent identifiers for a conceptual route or
duty. Reimporting identical current content, including with reordered rows,
is a no-op and preserves all UUIDs. Old versions and departures are retained
so cached historical identifiers remain resolvable in the database.

## Initial IBL file

The initial source is `schedules/ibl_bus_schedule.csv`, containing 1,172 rows.
On 2026-09-08 the project owner confirmed that `04:4` means `04:40` and `05:3`
means `05:30`. All 1,172 source times were normalized by appending the missing
trailing zero before validation/import. Future files must already contain
unambiguous `HH:MM` times; the importer does not guess or repair them.

## Periodic updates

Use a full replacement timetable for one operator every time it changes.
Validate before publishing, retain the original reviewed source file in the
normal project records, and avoid editing published departure rows directly.

```bash
python scripts/import_departures.py schedules/ibl_bus_schedule.csv --operator-id 1
python scripts/import_departures.py schedules/ibl_bus_schedule.csv --operator-id 1 --publish
```

The first command validates locally without a DB connection. The second uses
the application's existing database environment/Secret Manager configuration
and local Cloud SQL proxy. Confirm the operator ID before publishing.

Validation rejects wrong headers, missing/extra values, ambiguous or invalid
times, duplicate rows, and empty files. The importer locks the operator row,
inserts the complete new version, retires the previous version, and publishes
the new version in a single transaction. Errors roll back the entire update;
other operators' timetables are unaffected. Downloads use one SELECT so they
see the complete old version or the complete new version.

Publishing takes effect immediately. Scheduled future activation and an admin
upload UI are not implemented. A rollback can be performed by republishing
the previously approved CSV; this creates a new version and preserves history.

## Mobile CSV contract

See the [mobile developer guide](../mobile_departures_api_guide.md) for a full
walkthrough with request/response examples, typed column definitions, ETag
handling, offline storage, and cURL commands.

`GET /routes/departures.csv` requires the existing Firebase bearer token used
by the mobile app. Timetables are shared lookup data for authenticated users;
the optional positive integer `operator_id` filters the download. Without it,
the response contains every operator's active timetable.

CSV header:

```csv
uid,schedule_uid,operator_id,duty_no,departure,origin,destination,direction,valid_days,bus_type
```

The response is UTF-8 `text/csv` with CSV quoting, CRLF line endings, a download
filename, `Cache-Control: private, no-cache`, and an `ETag` identifying the exact
response bytes. No published rows for the selection yields HTTP 200 with a
header-only CSV. An invalid/non-positive operator parameter yields 422.

The external mobile team should:

1. Download the CSV while online using its Firebase ID token.
2. Validate and save the full file and ETag atomically on the device.
3. Continue using the cached timetable when offline; schedule lookup must not
   depend on a network call during shift capture.
4. When online again, send the saved ETag in `If-None-Match` to the same URL
   with the same operator filter.
5. Keep the cache on HTTP 304. Replace the entire matching cache only after a
   complete HTTP 200 response has been validated. Keep the old cache on network
   failure, incomplete download, or authentication failure, refreshing login
   credentials through the existing auth flow as appropriate.

Cache the ETag separately for each operator selection. The endpoint provides
full snapshots rather than incremental row updates, so removals are reflected
when the client replaces its cache. Old UUIDs already referenced by offline
records must not be rewritten to the latest timetable. The existing shift
payload is unchanged and does not yet accept a departure UUID.

## Deployment and verification

Apply `scripts/20260908_route_departures.sql` to the target database before
deploying the backend. The migration is additive and rerunnable; it creates
the schema and two tables without modifying existing route/inspection data.
The migration assumes the existing runtime DB role is the owner (as with this
project's manual schema scripts); if another role applies it, grant the API
role schema USAGE and the appropriate table privileges.

The API change deploys through the existing backend CI/CD on `main`. No new
runtime secrets or dependencies are required. The endpoint is documented by
protected OpenAPI; existing frontend pages do not consume it. Regenerate the
Angular client when adding a dashboard consumer.

`tests/test_departures.py` checks authentication, CSV round-tripping, operator
filtering, ETag revalidation, version history, identical-import handling, failed
import rollback, and input validation. Database-specific constraints and the
initial import are also checked against PostgreSQL during setup.

Setup on 2026-09-08: migration applied and 1,172 IBL departures published for
`operator_id=1`, schedule UUID `b6e73094-3936-499f-869b-1f688b8b0f94`.
All 59 tests passed; the 14 schedule tests also passed after import batching.
A local API client connected to the live DB returned all 1,172 CSV rows and
HTTP 304 on revalidation. Firebase verification was overridden only for that
local DB smoke test; the endpoint's missing-token rejection is covered by the
automated tests. Cloud Run deployment and a real-token HTTP smoke test remain
pending.
