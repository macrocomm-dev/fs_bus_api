# FS Bus API

FastAPI service for capturing data for the FS bus tracking application.
The database (PostgreSQL) lives in the `bus_track` GCloud project (Cloud SQL).

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

Interactive docs: <http://127.0.0.1:8000/docs>

### 3b — Docker Compose stack

```bash
docker compose up --build
```

This starts the Cloud SQL Auth Proxy and the API containers together.
The API is available at <http://localhost:8000>.

---

## Authentication

All API calls (except `/health` and `/docs`) require an `Authorization: Bearer <token>` header.

Tokens are signed JWTs (HS256).  Obtain one from the `/auth/token` endpoint:

```bash
curl -X POST http://localhost:8000/auth/token \
  -d "username=<user>&password=<password>"
```

In production, tokens should be issued by the configured identity provider
and validated by this API's Bearer scheme.

---

## CI/CD (GitHub Actions → Cloud Run)

The workflow in `.github/workflows/deploy.yml` triggers on every push to `main`:

1. **Test** — runs `pytest` if a `tests/` directory exists
2. **Build & Push** — builds the Docker image and pushes to Artifact Registry
3. **Deploy** — deploys to Cloud Run with Cloud SQL and Secret Manager wired in

### Required GitHub Actions secrets

| Secret | Description |
|--------|-------------|
| `GCP_SA_KEY` | Service account key JSON |
| `GCP_PROJECT_ID` | GCloud project ID (e.g. `bus_track`) |
| `GCP_REGION` | Region (e.g. `us-central1`) |
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
| `GOOGLE_CLOUD_PROJECT` | `bus_track` | GCloud project |
| `CLOUD_SQL_INSTANCE` | `bus_track:us-central1:fs-bus-db` | Cloud SQL connection name |
| `DB_HOST` | `127.0.0.1` | DB host (proxy address) |
| `DB_PORT` | `5432` | DB port |
| `SECRET_KEY` | *(from Secret Manager)* | JWT signing key |
| `API_PORT` | `8000` | Port for `start.sh` |
