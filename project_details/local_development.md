# Local Development Setup and Recovery

The local stack consists of the Angular dashboard, FastAPI API, and Cloud SQL
Auth Proxy. The API connects through the proxy to the existing FS Bus Cloud
SQL database; starting locally does not create a separate development database.

## Environment files

The root `.env` configures local startup and backend settings. Copy
`.env.example` if it is missing, then customize ports and CORS as needed.
Do not overwrite an existing populated file or commit it to Git.

| Setting | Local value / source |
|---|---|
| `GOOGLE_CLOUD_PROJECT` | `bus-track-480813` |
| `FIREBASE_PROJECT_ID` | `bus-track-480813` |
| `FIREBASE_WEB_API_KEY` | Public Firebase client configuration from `.env.example`; not a user's password. |
| `LOAD_GCP_SECRETS` | `true` when leaving database and integration secret values empty. The startup script otherwise defaults to `false`. |
| `CLOUD_SQL_INSTANCE` | `bus-track-480813:africa-south1:fs-bus-db` |
| `DB_HOST` / `DB_PORT` | `127.0.0.1` / `5432`, matching the local proxy. |
| `DB_TIMEZONE` | `Africa/Johannesburg` |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Leave empty to load from Secret Manager (`db-name`, `db-user`, `db-password`), or provide local overrides. The template already provides `DB_USER=fs_bus_user`. |
| `SECRET_KEY` | Loaded from `api-secret-key`; retained for legacy helpers, not used to issue Firebase ID tokens. |
| `API_PORT` | `8000`; the frontend development environment points to `http://127.0.0.1:8000`. |
| `FRONTEND_PORT` | `4200` by default. This workstation uses `4201` because BLS Fleet Portal already occupies `4200`. |
| `CORS_ORIGINS` | Comma-separated allowed browser origins. Include `http://localhost:<FRONTEND_PORT>` and `http://127.0.0.1:<FRONTEND_PORT>`. |
| `ENABLE_TEST_AUTH_ENDPOINTS` | `true` enables the Firebase sign-in helper used by local `/docs`. |
| `DOCS_REQUIRED_ROLE` | `Admin` for access to protected OpenAPI. |
| `ALERT_EMAIL_ENABLED` | `false` locally so testing errors does not send operational emails. |
| `AUDIT_SUCCESS_PAYLOADS_ENABLED` | Optional investigation setting; `true` stores successful shift payloads in the shared audit database. It is not needed for timetable downloads. |
| `SMART_FLEET_BASE_URL` | `https://smart-fleet.co.za` |
| `SMART_FLEET_EMAIL`, `SMART_FLEET_API_HASH` | Leave empty to load from `smart-fleet-email` and `smart-fleet-api-hash`. Used by Smart Fleet integration. |

Cloud Storage configuration can also be loaded from Secret Manager (`gcs_bucket`
into `GCS_BUCKET_NAME`). SMTP settings are not needed to send alerts when
`ALERT_EMAIL_ENABLED=false`; the current settings loader may still fetch them.
The database, auth, and timetable download do not require working SMTP delivery.

Secrets do not need to be copied into `.env`. Existing Application Default
Credentials authorize runtime retrieval from Secret Manager and the proxy's
connection to Cloud SQL. After a new machine setup or expired login, run:

```bash
gcloud auth application-default login
```

This Google Cloud login is separate from logging into the dashboard as a
Firebase user. A cloud credential does not automatically sign you into the app.

## Optional API-generation credentials

`frontend/app/.env.local` is required only by the Angular API-client generation
script, not by normal dashboard/API startup. If regeneration is needed, create
this ignored file with:

```dotenv
API_URL=http://127.0.0.1:8000
API_ADMIN_EMAIL=<your-admin-email>
API_ADMIN_PASS=<your-admin-password>
```

The tracked `frontend/app/env.local` file is a template with a different name;
`generate-api.sh` reads `.env.local` with the leading dot. The dashboard's API
URL is configured in `frontend/app/src/environments/environment.ts`.

On this workstation, the docs test account is `admin.test@fsbus.example.com`.
Its password was reset with owner approval on 2026-09-08 and saved as
`API_ADMIN_PASS` alongside `API_ADMIN_EMAIL` and `API_URL` in the ignored root
`.env`, with matching values in `frontend/app/.env.local`. Both files have
owner-only permissions. Keep the password in those local files rather than in
tracked documentation. Login, protected OpenAPI access, and a 1,172-row CSV
download were verified through the running local API using this account.

## Dependencies after a fresh checkout

Required: Python 3.12 with venv/pip support, Node 22, Yarn 4.1.1, Google Cloud
CLI with ADC credentials, and the Cloud SQL Auth Proxy. Yarn's version is
declared in `frontend/app/package.json`.

Install frontend dependencies once (and after lockfile changes):

```bash
cd frontend/app
yarn install --immutable
```

From the repository root, normal Python setup is:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

If this machine reports missing `ensurepip`, its existing system pip can
bootstrap the environment without installing system packages:

```bash
python3 -m venv --without-pip .venv
python3 -m pip --python .venv install pip -r requirements.txt
```

The restored local `./cloud-sql-proxy` binary is ignored by Git. It is the
official Linux amd64 v2.14.1 binary, matching `docker-compose.yml`. Startup
finds the proxy on PATH or at this repository-root location. A fresh checkout
on another machine must install the proxy again using the appropriate binary
for that machine.

## Start and stop

From the repository root:

```bash
bash scripts/start.sh
```

Keep that terminal running. The script loads `.env`, activates `.venv`, installs
Python dependencies, and starts the proxy, dashboard, and API. It assumes the
frontend dependencies have already been installed. Existing listeners on its
configured ports are left alone, so confirm they belong to the intended app.

To stop this project's local services:

```bash
bash scripts/stop.sh
```

The stop script uses the same `.env` ports. With this workstation's configuration
it targets the FS Bus frontend on 4201, not the BLS frontend on 4200.

## Test the restored environment

Current workstation URLs:

- Dashboard: `http://localhost:4201/`
- API health: `http://127.0.0.1:8000/health`
- API docs: `http://127.0.0.1:8000/docs`
- IBL CSV: `http://127.0.0.1:8000/routes/departures.csv?operator_id=1`

Sign in to the dashboard with your existing Firebase app account. For Swagger,
use an Admin account in the docs sign-in form or paste its valid Firebase ID
token. This loads protected OpenAPI and authorizes "Try it out" requests.
The CSV itself accepts authenticated mobile users as well; it does not require
the Admin docs role. Opening the CSV URL directly without a bearer token returns
401. See [the mobile integration guide](mobile_departures_api_guide.md) for cURL
and ETag examples; use the local API base URL when testing locally.

Recovery verified on 2026-09-08: proxy, API, and dashboard started successfully;
health/docs/dashboard returned 200; the 4201 browser-origin CORS check passed;
database and integration secrets loaded; a read-only database query through
the local proxy found 1,172 active IBL departures. The frontend dev build
completed despite existing Angular package peer-dependency warnings.
