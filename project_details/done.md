# Done

## Existing implementation baseline

- FastAPI application scaffold created with API metadata and startup flow.
- CORS configuration wiring added.
- Health endpoint implemented.
- OAuth2 bearer scheme and JWT helper functions implemented.
- Auth token endpoint scaffold created as a placeholder for real auth.
- Settings management created with environment-first and Secret Manager fallback loading.
- SQLAlchemy engine and session setup implemented for PostgreSQL.
- Dockerfile created for containerized API runtime.
- docker-compose stack created with API service and Cloud SQL Proxy service for local use.
- start.sh script created for local startup workflow.
- Initial GitHub Actions CI/CD workflow created for test, build, and deploy path on main branch.
- Scope artifacts added under project_details/scope.

## Cloud bootstrap completed (africa-south1)

- Google Cloud project defaults set to bus-track-480813 with regional defaults in africa-south1.
- Required GCP APIs enabled for compute, Cloud SQL, Secret Manager, Cloud Run, Artifact Registry, IAM, Resource Manager, and Service Networking.
- Service accounts provisioned: fs-bus-api-runtime and fs-bus-cicd.
- IAM role bindings applied for runtime and CI/CD service accounts.
- Cloud SQL PostgreSQL instance provisioned in africa-south1 and upgraded to POSTGRES_17.
- Application database created: fs_bus_api.
- Application database user created: fs_bus_user.
- Secret Manager secret containers created and initialized: api-secret-key, db-password, db-name, db-user.
- Database user password rotated and synchronized into db-password secret.

## Deployment and CI wiring completed

- Runtime database URL handling updated to support Cloud SQL Unix socket paths in Cloud Run.
- Default application GCP project updated to bus-track-480813.
- GitHub Actions workflow updated to use Workload Identity Federation instead of static service account keys.
- Cloud Run service bus-track-api configured to use runtime service account fs-bus-api-runtime.
- Cloud Run service bus-track-api configured with Cloud SQL instance bus-track-480813:africa-south1:fs-bus-db.
- Cloud Run service bus-track-api configured with Secret Manager-backed environment values for DB and JWT secrets.
- Artifact Registry repository bus-track-mcomm verified in africa-south1.
- GitHub Workload Identity Pool and Provider created for macrocomm-dev/fs_bus_api.
- Workload identity binding applied to fs-bus-cicd for GitHub Actions OIDC.
- GitHub deployment configuration moved to repository variables and redundant GitHub secrets were removed.
- Temporary manual token-creator grant used for smoke testing was removed after validation.
- Application startup failure on Cloud Run fixed by moving CORS middleware registration out of startup lifecycle.
- Current workspace image built, pushed to Artifact Registry, and deployed to Cloud Run successfully.

## Smoke checks completed

- Cloud Run health endpoint validated successfully with HTTP 200.
- Protected /me endpoint validated to reject invalid credentials with HTTP 401.
- Placeholder auth token endpoint validated to return HTTP 501 until real auth is implemented.
- Secret Manager latest-version access validated for api-secret-key, db-password, db-name, and db-user.
- Direct external PostgreSQL connection probe from local environment timed out against the instance public IP, so DB-backed application behavior is not yet fully validated end-to-end.

## Auth implementation started

- API bearer-token validation switched from local placeholder JWT decoding to Firebase token verification.
- Firebase configuration fields added to application settings and local environment template.
- Current authenticated user response expanded to expose sub, name, email, role, and derived permissions.
- Role hierarchy modeled in code for Monitor, Supervisor, and Admin, including inherited capabilities.
- Focused automated tests added for auth helpers and the /me protected route.
- Added /auth/test/whoami as a simple Firebase bearer-token validation endpoint that returns the authenticated user details.
- Protected /openapi.json with the same Firebase bearer-token flow and an Admin-role gate.
- Replaced the default public /docs route with a token-entry shell that uses the caller's Firebase ID token to load protected OpenAPI docs and authorize Swagger requests.
- Added a Firebase bootstrap script and created one test user per role: Monitor, Supervisor, and Admin.
- Moved the custom docs shell into a dedicated template file and added a built-in test sign-in form that calls /auth/test/token when test auth helpers are enabled.

## Route departure timetables (2026-09-08)

- Created live `routes.departure` and `routes.schedule_version` tables with UUID keys and a single active version per operator; added a rerunnable SQL migration and ORM models.
- Normalized 1,172 IBL departure times after the owner confirmed `04:4` means `04:40`; published the timetable for Interstate Bus Lines (`operator_id=1`).
- Added authenticated `GET /routes/departures.csv` with optional operator filtering, UUID columns, UTF-8 CSV output, and ETag/304 support for offline mobile caches; backend deployment is pending.
- Added a validating timetable import CLI that publishes complete versions atomically, retains history, and preserves UUIDs when current content is reimported unchanged.
- Passed all 59 automated tests, including 14 schedule tests; rechecked all 14 schedule tests after batching imports.
- Verified CSV HTTP 200 with all 1,172 rows and HTTP 304 against the live DB through the local API test client; verified PostgreSQL active-version uniqueness, identical reimport, and replacement rollback.

## Departure API integration documentation (2026-09-08)

- Added `DepartureDownloadRequest` for validated GET query parameters and `DepartureCsvRow` for validated CSV output columns; retained the CSV download response format.
- Expanded Swagger/OpenAPI with mobile usage steps, CSV examples, ETag and download headers, JSON error models, and a supplementary parsed-row schema.
- Added `project_details/mobile_departures_api_guide.md` with beginner-oriented authentication, first-download, update-check, offline storage, error handling, model definitions, pseudocode, and cURL instructions.
- Passed all 15 schedule endpoint tests, including the OpenAPI query/header/CSV contract check; verified the new contract appears in the full app's generated schema. No DB changes or deployment were needed for these local code/documentation changes; backend deployment remains pending.

## Local development recovery (2026-09-08)

- Restored the incomplete Python virtual environment, installed backend and frontend dependencies, and downloaded the ignored local Cloud SQL Auth Proxy binary matching the repository's configured version.
- Configured the ignored `.env` to load runtime secrets from Secret Manager, allow the local dashboard origins, use frontend port 4201 alongside the existing BLS app on 4200, and disable local operational email alerts.
- Added missing Secret Manager, frontend-port, CORS, and local alert settings to `.env.example`; documented required/optional settings and recovery steps in `project_details/local_development.md` and linked it from README.
- Started the proxy on 5432, API on 8000, and FS Bus Angular dashboard on 4201; verified HTTP 200 for health/docs/dashboard, CORS from the dashboard origin, secret availability, and a read-only query of all 1,172 active IBL departures through the local proxy.

## Docs test account recovery (2026-09-08)

- Reset only `admin.test@fsbus.example.com` in Firebase with explicit owner approval; saved the test credentials in the ignored `.env` and `frontend/app/.env.local` files with owner-only permissions.
- Verified the real test-account login through the local API, authenticated access to protected OpenAPI, and a successful authenticated CSV download of all 1,172 IBL departures. Passwords and tokens were not recorded in tracked documentation.

## Schedule inspection bands and MBS docs access (2026-09-14)

- Expanded `behind_schedule_interval` without changing the JSON structure: added early departure and the three new late bands, retained `0-5 mins` for on-time checks, and kept legacy values valid for offline queues and historical reporting.
- Updated both reporting endpoints, dashboard labels/drilldowns, and the generated Angular enum. Early departures have a separate count and trend and are excluded from late totals. Historical bands remain separately labelled and are not rebinned.
- Documented exact mobile values, examples, offline compatibility, report calculations, and backend-first rollout in `project_details/mobile_schedule_inspections_guide.md`; updated API, reporting, and authentication references.
- Restored the missing Firebase `Admin` role claim for `mbsadmin@fsbus.example.com` after confirming its matching database user was active and already Admin. Password and operator association were unchanged. The claim repair is live; David must clear his old token and sign in again. Added clearer docs-page guidance for insufficient-role errors.
- Validation: all 84 backend tests passed; dashboard production build passed with existing size warnings. Read-only checks against live historical data confirmed both reporting endpoints agree on on-time percentage and legacy counts. No database migration or historical data changes were required.
- Backend/frontend code deployment and the subsequent mobile rollout remain pending.

## Destination-display photo evidence (2026-09-14)

- Added optional bus-level `photos` beside `destination_displayed` for JSON and multipart shift uploads, using the existing photo timestamp/GPS/base64 format. Old payloads remain valid; missing multipart files return 422 and roll back pending photo writes.
- Added and applied `scripts/20260914_destination_display_photos.sql` to create `photos.destination_display` in Cloud SQL. Evidence is stored once per photo, separately from inspection events, including when no other inspection section was captured. Existing data and event counts were unchanged.
- Added grouped readback with shift/bus/user/date filters and complete photo arrays under limited reads. The dashboard shift details now show destination answers and image previews without adding inspection counts or timeline events. Regenerated the affected Angular JSON models.
- Added `project_details/mobile_destination_photos_guide.md` and linked it from API/departures docs. The general FS app should omit the operator filter to support IBL and Maluti; verified that only IBL currently has a published timetable (1,172 departures).
- Validation: all 95 backend tests passed, including 11 destination-photo contract/persistence cases; the production dashboard build passed with existing size warnings. Backend/frontend deployment remains pending before mobile uploads can begin.

## Notes

- Items in this file represent work already present in the repository baseline.
- Completed tasks from project_details/to_do.md must be moved here as they are finished.
