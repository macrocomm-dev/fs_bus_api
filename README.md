# FS Bus API

FastAPI service for capturing data for the FS bus tracking application.
The database (PostgreSQL) lives in the `bus-track-480813` GCloud project (Cloud SQL).

---

## Project structure

```
.
├── app/
│   ├── main.py        # FastAPI entry-point (title: FS Bus API)
│   ├── auth.py        # OAuth2 bearer / JWT helpers
│   ├── config.py      # Settings + GCloud Secret Manager loader
│   ├── database.py    # SQLAlchemy engine / session
│   └── routers/       # Add feature routers here
├── .github/
│   └── workflows/
│       └── deploy.yml # CI/CD → Cloud Run
├── Dockerfile
├── docker-compose.yml # Local stack (API + Cloud SQL Auth Proxy)
├── requirements.txt
├── start.sh           # Local quick-start script
└── .env.example       # Environment variable template
```

---

## Local development

### Prerequisites

| Tool | Purpose |
|------|---------|
| Python 3.12+ | Runtime |
| [gcloud CLI](https://cloud.google.com/sdk/docs/install) | ADC credentials & Secret Manager access |
| [Cloud SQL Auth Proxy](https://cloud.google.com/sql/docs/postgres/connect-auth-proxy) | Local DB tunnel |
| Docker + Docker Compose (optional) | Containerised stack |

### 1 — Authenticate with GCloud

```bash
gcloud auth application-default login
```

This allows the app to call Secret Manager and the proxy to connect to Cloud SQL.

### 2 — Configure environment

```bash
cp .env.example .env
# Edit .env — most secrets are loaded automatically from Secret Manager,
# but you can override any value locally.
```

### 3a — Quick start (uvicorn + local proxy)

```bash
chmod +x start.sh
./start.sh
```

The script will:
- Create / activate a `.venv` virtual environment
- Install dependencies from `requirements.txt`
- Start the Cloud SQL Auth Proxy (if `cloud-sql-proxy` is on your `PATH`)
- Launch the API at <http://127.0.0.1:8000>

Interactive docs shell: <http://127.0.0.1:8000/docs>

The docs shell is served by the FastAPI app itself. It can either:
- call the temporary `/auth/test/token` endpoint with Firebase test credentials
- or accept a manually pasted Firebase ID token

It then uses that same bearer token to fetch the protected OpenAPI schema and authorize "Try it out" requests.

### 3b — Docker Compose stack

```bash
docker compose up --build
```

This starts the Cloud SQL Auth Proxy and the API containers together.
The API is available at <http://localhost:8000>.

---

## Authentication

Firebase Authentication is now the identity provider for API bearer-token validation.

- Protected API routes require `Authorization: Bearer <firebase-id-token>`.
- `/auth/token` is intentionally disabled; use `/auth/get_token` for the app-facing login flow.
- The mobile app should obtain its Firebase ID token from Firebase Auth itself, typically through the Firebase client SDK or Firebase Auth REST API, not from this backend.
- `/auth/test/whoami` and `/me` are the simplest endpoints to validate that a Firebase ID token is being accepted by the API.
- `/auth/test/token` is a temporary backend proxy that exchanges email/password for a Firebase ID token for smoke testing only.
- `/openapi.json` is protected by the same bearer-token flow and defaults to `Admin` access via `DOCS_REQUIRED_ROLE`.
- `/docs` is a custom FastAPI-served shell that can sign in through `/auth/test/token` for testing or accept a pasted Firebase ID token, then fetch `/openapi.json` and authorize Swagger requests.

Direct Firebase sign-in endpoint used by clients:

```text
https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=<FIREBASE_WEB_API_KEY>
```

Helper script for direct Firebase sign-in:

```bash
/home/erlo/fs_bus_api/.venv/bin/python scripts/get_firebase_test_token.py \
  admin.test@fsbus.example.com \
  '<password>'
```

Temporary backend proxy for smoke testing:

```bash
curl -X POST http://localhost:8000/auth/test/token \
  -H "Content-Type: application/json" \
  -d '{"email":"admin.test@fsbus.example.com","password":"<password>"}'
```

Example protected call:

```bash
curl http://localhost:8000/auth/test/whoami \
  -H "Authorization: Bearer <firebase-id-token>"
```

---

## CI/CD (GitHub Actions → Cloud Run)

The workflow in `.github/workflows/deploy.yml` triggers on every push to `main`:

1. **Test** — runs `pytest` if a `tests/` directory exists
2. **Build & Push** — builds the Docker image and pushes to Artifact Registry
3. **Deploy** — deploys to Cloud Run with Cloud SQL and Secret Manager wired in

### Required GitHub Actions variables

| Secret | Description |
|--------|-------------|
| `WIF_PROVIDER` | Workload Identity Provider resource name |
| `WIF_SERVICE_ACCOUNT` | CI service account email |
| `GCP_PROJECT_ID` | GCloud project ID (e.g. `bus-track-480813`) |
| `GCP_REGION` | Region (e.g. `africa-south1`) |
| `CLOUD_SQL_INSTANCE` | Connection name (`<project>:<region>:<instance>`) |
| `ARTIFACT_REGISTRY_REPO` | Artifact Registry repo name |
| `CLOUD_RUN_SERVICE` | Cloud Run service name |

### Required GCloud Secret Manager secrets

| Secret ID | Description |
|-----------|-------------|
| `api-secret-key` | JWT signing key |
| `db-password` | Database password |
| `db-name` | Database name |
| `db-user` | Database username |

---

## Environment variables

See `.env.example` for the full list.  Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_CLOUD_PROJECT` | `bus-track-480813` | GCloud project |
| `FIREBASE_WEB_API_KEY` | `AIzaSyDh21k62KCpURRdmM_zQXozBtJJQ3HHxhA` | Public Firebase client API key used for token exchange |
| `CLOUD_SQL_INSTANCE` | `bus-track-480813:africa-south1:fs-bus-db` | Cloud SQL connection name |
| `DB_HOST` | `127.0.0.1` | DB host (proxy address) |
| `DB_PORT` | `5432` | DB port |
| `DB_TIMEZONE` | `Africa/Johannesburg` | PostgreSQL session timezone used for DB-generated timestamps |
| `SECRET_KEY` | *(from Secret Manager)* | Legacy local JWT helper secret |
| `ENABLE_TEST_AUTH_ENDPOINTS` | `true` | Enables the temporary `/auth/test/token` backend proxy |
| `DOCS_REQUIRED_ROLE` | `Admin` | Minimum Firebase role allowed to fetch `/openapi.json` |
| `API_PORT` | `8000` | Port for `start.sh` |
