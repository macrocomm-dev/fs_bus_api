# New App Architecture Handoff

Use this as the implementation brief for a new repo that must follow the same full-stack architecture and developer workflow as this project.

## Objective

Build a new full-stack application with:

- Angular frontend with PrimeNG.
- Yarn as the frontend package manager.
- FastAPI backend.
- Poetry as the backend dependency manager.
- PostgreSQL on Google Cloud SQL.
- Cloud SQL Auth Proxy for local development.
- FastAPI API containerized with Docker and deployed to Cloud Run.
- Angular frontend deployed to Firebase Hosting.
- OpenAPI Generator for generated Angular API services.
- Local up/down scripts for running the API, frontend, and Cloud SQL proxy.
- GitHub Actions CI/CD workflows for backend and frontend deployments.

## Required Placeholders

Use variables throughout scripts, workflows, docs, and config. Do not hardcode project-specific values except in `.env.example`.

Required placeholders:

```text
APP_NAME
APP_SLUG
GCP_PROJECT_ID
GCP_REGION
CLOUD_SQL_INSTANCE
CLOUD_SQL_DATABASE
CLOUD_SQL_USER
ARTIFACT_REGISTRY_REPO
CLOUD_RUN_SERVICE
CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT
FIREBASE_PROJECT_ID
FRONTEND_HOSTING_URL
API_BASE_URL
DOCS_REQUIRED_ROLE
WIF_PROVIDER
WIF_SERVICE_ACCOUNT
```

## Preferred File Layout

```text
.
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── auth.py
│   ├── models/
│   │   └── __init__.py
│   ├── schemas/
│   │   └── __init__.py
│   ├── routers/
│   │   ├── __init__.py
│   │   └── router_config.py
│   ├── services/
│   │   └── __init__.py
│   └── templates/
├── frontend/
│   └── app/
│       ├── src/
│       │   ├── app/
│       │   │   ├── core/
│       │   │   │   ├── api/
│       │   │   │   ├── interceptors/
│       │   │   │   ├── models/
│       │   │   │   └── services/
│       │   │   ├── features/
│       │   │   ├── app.config.ts
│       │   │   └── app.routes.ts
│       │   └── environments/
│       │       ├── environment.ts
│       │       └── environment.prod.ts
│       ├── scripts/
│       ├── package.json
│       ├── yarn.lock
│       └── openapitools.json
├── scripts/
│   ├── start.sh
│   ├── stop.sh
│   └── update-secrets.sh
├── .github/
│   └── workflows/
│       ├── deploy.yml
│       └── deploy-frontend.yml
├── Dockerfile
├── pyproject.toml
├── poetry.lock
├── generate-api.sh
├── start.sh
├── .env.example
├── .gitignore
└── README.md
```

## Backend Requirements

Use FastAPI with SQLAlchemy 2.x ORM and Pydantic settings.

The backend must live under `app/`.

Required modules:

```text
app/main.py
app/config.py
app/database.py
app/auth.py
app/routers/router_config.py
app/models/
app/schemas/
app/services/
```

`app/main.py` must:

- Create the FastAPI app.
- Configure CORS from settings.
- Register routers through `register_routers(app)`.
- Expose `/health`.
- Expose custom `/docs`.
- Protect `/openapi.json` with bearer auth and an Admin/docs role.

`app/config.py` must:

- Use `pydantic-settings`.
- Load environment variables first.
- Optionally fetch missing secret values from Google Secret Manager.
- Control Secret Manager fallback with `LOAD_GCP_SECRETS`.
- Never log secret values.
- Include settings for:
  - app name
  - GCP project
  - database host, port, name, user, password
  - auth/JWT/Firebase
  - CORS
  - Cloud Storage if needed
  - external integrations if needed

`app/database.py` must:

- Create a SQLAlchemy engine.
- Support local TCP DB host: `127.0.0.1`.
- Support Cloud Run Unix socket path:

```text
DB_HOST=/cloudsql/<CLOUD_SQL_INSTANCE>
```

`app/auth.py` should:

- Validate bearer tokens.
- Normalize user/role context.
- Provide dependencies like:
  - `get_current_user`
  - `require_role("Admin")`
- If Firebase Auth is used, verify Firebase ID tokens with Firebase Admin SDK.

Routers must:

- Live under `app/routers/`.
- Use `HTTPException` for errors.
- Avoid returning raw exception traces.
- Log external API failures with sanitized details.
- Be registered centrally in `app/routers/router_config.py`.

## Poetry Backend Setup

Use Poetry as the primary backend dependency manager.

Initialize:

```bash
poetry init
```

Add runtime dependencies:

```bash
poetry add fastapi "uvicorn[standard]" sqlalchemy psycopg2-binary pydantic-settings
poetry add "python-jose[cryptography]" "passlib[bcrypt]" python-multipart httpx
poetry add firebase-admin google-cloud-secret-manager google-cloud-storage
```

Add dev dependencies:

```bash
poetry add --group dev pytest
```

The new repo should commit:

```text
pyproject.toml
poetry.lock
```

If deployment tooling still expects `requirements.txt`, generate it from Poetry:

```bash
poetry export --without-hashes --format=requirements.txt --output requirements.txt
```

Prefer Docker installing with Poetry directly, but exporting `requirements.txt` is acceptable if CI/CD requires it.

## Dockerfile

Preferred Dockerfile:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

COPY app/ ./app/

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

## Frontend Requirements

Create the Angular app under:

```text
frontend/app
```

Use:

- Angular standalone components.
- PrimeNG.
- PrimeIcons.
- `@primeuix/themes`.
- Yarn Berry.
- Generated API client in `src/app/core/api`.

Recommended install:

```bash
corepack enable
yarn create @angular app frontend/app
cd frontend/app
yarn add primeng primeicons @primeuix/themes rxjs
yarn add -D firebase-tools openapi-typescript prettier vitest jsdom
```

`frontend/app/package.json` should include:

```json
{
  "packageManager": "yarn@4.1.1",
  "scripts": {
    "start": "ng serve",
    "build": "ng build",
    "watch": "ng build --watch --configuration development",
    "test": "ng test",
    "generate:api": "node scripts/generate-api.mjs",
    "deploy": "ng build --configuration production && firebase deploy --only hosting"
  }
}
```

Frontend conventions:

- Use `features/` for page-level feature components.
- Use `core/services/` for app-wide services.
- Use `core/interceptors/` for HTTP interceptors.
- Use `core/models/` for frontend-only types.
- Use `core/api/` for generated API client.
- Store auth session in localStorage using an app-specific key like:

```text
<APP_SLUG>_session
```

PrimeNG conventions:

- Use `p-floatlabel` with `variant="on"` for form fields.
- Use `p-select` instead of deprecated dropdown components.
- Use `p-table` for tables.
- Use `p-button` with PrimeIcons.
- Use `p-tag` for compact statuses.
- Use `p-toolbar` for top bars.
- Use `p-drawer` and `p-menu` for side navigation.
- Use `p-toast` for global error notifications.

## Frontend Environment Files

Create:

```text
frontend/app/src/environments/environment.ts
frontend/app/src/environments/environment.prod.ts
```

Development:

```ts
export const environment = {
  production: false,
  apiUrl: 'http://127.0.0.1:8000',
};
```

Production:

```ts
export const environment = {
  production: true,
  apiUrl: 'https://<CLOUD_RUN_SERVICE_URL>',
};
```

## OpenAPI Generator

Yes, this architecture explicitly uses OpenAPI Generator.

Create root script:

```text
generate-api.sh
```

The script must:

1. Load credentials from:

```text
frontend/app/.env.local
```

2. Require:

```text
API_URL=http://127.0.0.1:8000
API_ADMIN_EMAIL=<admin-email>
API_ADMIN_PASS=<admin-password>
```

3. Authenticate against:

```text
POST ${API_URL}/auth/get_token
```

4. Extract `access_token`.

5. Fetch protected OpenAPI schema:

```text
GET ${API_URL}/openapi.json
Authorization: Bearer <access_token>
```

6. Generate Angular services into:

```text
frontend/app/src/app/core/api
```

Use this generator command:

```bash
openapi-generator-cli generate \
  -i "${TEMP_SPEC}" \
  -g typescript-angular \
  -o "${OUTPUT_DIR}" \
  --additional-properties=\
ngVersion=21,\
npmName=<APP_SLUG>-api-client,\
supportsES6=true,\
withInterfaces=true,\
useSingleRequestParameter=true,\
stringEnums=true \
  --skip-validate-spec
```

7. Write:

```text
frontend/app/src/app/core/api/api-config.ts
```

Example `api-config.ts`:

```ts
import { Configuration } from './configuration';
import { environment } from '../../../environments/environment';

function getStoredAccessToken(): string | undefined {
  try {
    const raw = globalThis.localStorage?.getItem('<APP_SLUG>_session');
    if (!raw) return undefined;
    const parsed = JSON.parse(raw) as { accessToken?: string | null };
    return parsed.accessToken ?? undefined;
  } catch {
    return undefined;
  }
}

export function createApiConfiguration(): Configuration {
  return new Configuration({
    basePath: environment.apiUrl,
    credentials: {
      HTTPBearer: () => getStoredAccessToken(),
    },
  });
}
```

8. Clean up the temporary OpenAPI spec.

`generate-api.sh` should fail loudly when:

- `.env.local` is missing.
- `openapi-generator-cli` is not installed.
- backend is not running.
- auth fails.
- `/openapi.json` returns non-200.

Install OpenAPI Generator CLI:

```bash
npm install -g @openapitools/openapi-generator-cli
```

## Local Development Scripts

Create:

```text
scripts/start.sh
scripts/stop.sh
start.sh
```

`scripts/start.sh` must:

- Load `.env`.
- Export common env vars.
- Create/use local backend environment.
- Run `poetry install`.
- Start Cloud SQL Auth Proxy if `DB_PORT` is free.
- Start Angular dev server if `FRONTEND_PORT` is free.
- Start FastAPI with Uvicorn reload.
- Store PIDs under:

```text
.local/pids
```

Supported env vars:

```text
GOOGLE_CLOUD_PROJECT
CLOUD_SQL_INSTANCE
DB_HOST
DB_PORT
API_PORT
FRONTEND_PORT
LOAD_GCP_SECRETS
```

Cloud SQL Auth Proxy command:

```bash
cloud-sql-proxy --address "127.0.0.1" --port "${DB_PORT}" "${CLOUD_SQL_INSTANCE}"
```

FastAPI command:

```bash
poetry run uvicorn app.main:app \
  --host "127.0.0.1" \
  --port "${API_PORT}" \
  --reload
```

Angular command:

```bash
cd frontend/app
yarn start --port "${FRONTEND_PORT}"
```

`scripts/stop.sh` must:

- Load `.env`.
- Stop PIDs from `.local/pids`.
- Stop matching Uvicorn, Angular, and Cloud SQL proxy processes.
- Print any remaining listeners on:

```text
API_PORT
FRONTEND_PORT
DB_PORT
```

Root `start.sh` should be a wrapper:

```bash
#!/usr/bin/env bash
set -euo pipefail
bash scripts/start.sh
```

## `.env.example`

Create:

```text
# App
APP_NAME=<APP_NAME>
APP_SLUG=<APP_SLUG>

# GCP / Firebase
GOOGLE_CLOUD_PROJECT=<GCP_PROJECT_ID>
FIREBASE_PROJECT_ID=<FIREBASE_PROJECT_ID>
FIREBASE_WEB_API_KEY=
ENABLE_TEST_AUTH_ENDPOINTS=true
DOCS_REQUIRED_ROLE=Admin

# Cloud SQL
CLOUD_SQL_INSTANCE=<GCP_PROJECT_ID>:<GCP_REGION>:<INSTANCE_NAME>
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=
DB_USER=
DB_PASSWORD=

# Auth
SECRET_KEY=
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=240

# CORS
CORS_ORIGINS=http://localhost:4200,https://<FIREBASE_PROJECT_ID>.web.app

# Local ports
API_PORT=8000
FRONTEND_PORT=4200

# Secrets
LOAD_GCP_SECRETS=false
```

## Secret Manager

Create:

```text
scripts/update-secrets.sh
```

It must upsert secrets without printing values.

Required base secrets:

```text
api-secret-key
db-password
db-name
db-user
```

Pattern:

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-<GCP_PROJECT_ID>}"

upsert_secret() {
  local secret_name="$1"
  local value="$2"
  local tmp_file
  tmp_file="$(mktemp)"
  trap 'rm -f "$tmp_file"' RETURN

  printf "%s" "$value" > "$tmp_file"

  if gcloud secrets describe "$secret_name" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud secrets versions add "$secret_name" \
      --project "$PROJECT_ID" \
      --data-file="$tmp_file" >/dev/null
    echo "Updated secret version for $secret_name."
  else
    gcloud secrets create "$secret_name" \
      --project "$PROJECT_ID" \
      --replication-policy="automatic" \
      --data-file="$tmp_file" >/dev/null
    echo "Created secret $secret_name."
  fi
}
```

## Backend CI/CD

Create:

```text
.github/workflows/deploy.yml
```

Workflow behavior:

- Run on push and pull request to `main`.
- Run tests.
- Build Docker image.
- Push to Artifact Registry.
- Deploy to Cloud Run.
- Attach Cloud SQL instance.
- Bind secrets.
- Set environment variables.

Required GitHub Actions variables:

```text
GCP_PROJECT_ID
GCP_REGION
CLOUD_SQL_INSTANCE
ARTIFACT_REGISTRY_REPO
CLOUD_RUN_SERVICE
WIF_PROVIDER
WIF_SERVICE_ACCOUNT
```

Required GitHub/GCP setup:

- Workload Identity Federation provider.
- GitHub Actions service account.
- Artifact Registry repo.
- Cloud Run runtime service account.
- Secret Manager secrets.
- Cloud SQL client permissions for runtime service account.
- Secret accessor permissions for runtime service account.

Deploy command pattern:

```bash
gcloud run deploy "${CLOUD_RUN_SERVICE}" \
  --image "${IMAGE_NAME}:${GITHUB_SHA}" \
  --region "${GCP_REGION}" \
  --project "${GCP_PROJECT_ID}" \
  --platform managed \
  --service-account "${CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT}" \
  --allow-unauthenticated \
  --add-cloudsql-instances "${CLOUD_SQL_INSTANCE}" \
  --set-secrets="SECRET_KEY=api-secret-key:latest,DB_PASSWORD=db-password:latest,DB_NAME=db-name:latest,DB_USER=db-user:latest" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${GCP_PROJECT_ID},DB_HOST=/cloudsql/${CLOUD_SQL_INSTANCE}" \
  --quiet
```

## Frontend CI/CD

Create:

```text
.github/workflows/deploy-frontend.yml
```

Workflow behavior:

- Run on push to `main` when `frontend/**` changes.
- Run build-only on pull requests.
- Use Node 22.
- Enable Corepack.
- Install with Yarn.
- Build Angular production.
- Deploy to Firebase Hosting.

Required command:

```bash
corepack enable
yarn install --immutable
yarn build --configuration production
yarn firebase deploy --only hosting --project "${GCP_PROJECT_ID}" --non-interactive
```

Required secret:

```text
FIREBASE_TOKEN
```

or use Google auth if switching Firebase deploy to WIF-compatible auth.

## Auth And Session Pattern

Frontend auth service should expose:

```text
login(email, password)
refresh(refreshToken)
logout()
isLoggedIn()
getAccessToken()
session signal
```

Session localStorage shape:

```ts
type AuthSession = {
  accessToken: string;
  refreshToken: string | null;
  expiresAt: string | null;
  role: string | null;
  userId: string | number | null;
  name: string | null;
  surname: string | null;
};
```

Generated API services should read the bearer token through `api-config.ts`.

## Global Error Handling

Frontend must include:

- HTTP interceptor.
- `ApiErrorToastService`.
- PrimeNG toast setup.

Behavior:

- Show user-facing toast: `Something went wrong`.
- Log full error to console.
- Let component-specific errors still display where useful.

## Cloud SQL

Local:

```bash
cloud-sql-proxy --address 127.0.0.1 --port "${DB_PORT}" "${CLOUD_SQL_INSTANCE}"
```

Cloud Run:

```text
DB_HOST=/cloudsql/<CLOUD_SQL_INSTANCE>
```

Cloud Run deploy must include:

```bash
--add-cloudsql-instances "${CLOUD_SQL_INSTANCE}"
```

## Git Ignore

Include:

```text
.env
.env.local
.venv/
.local/
__pycache__/
.pytest_cache/
dist/
frontend/app/.angular/
frontend/app/dist/
frontend/app/node_modules/
```

## Implementation Checklist

1. Create repo structure.
2. Add Poetry backend.
3. Add FastAPI app, settings, DB, auth, router registration.
4. Add first health endpoint.
5. Add Dockerfile.
6. Create Angular app under `frontend/app`.
7. Add PrimeNG and base theme.
8. Add frontend routing.
9. Add auth/session services.
10. Add global API error interceptor and toast.
11. Add OpenAPI generator script `generate-api.sh`.
12. Add `frontend/app/.env.local` for API generation credentials.
13. Add local `scripts/start.sh`.
14. Add local `scripts/stop.sh`.
15. Add `.env.example`.
16. Add Secret Manager update script.
17. Add backend deploy workflow.
18. Add frontend deploy workflow.
19. Create Cloud SQL instance/database/user.
20. Create Secret Manager secrets.
21. Create Artifact Registry repo.
22. Create Cloud Run runtime service account.
23. Grant Cloud SQL Client and Secret Accessor permissions.
24. Configure GitHub Workload Identity Federation.
25. Configure Firebase Hosting.
26. Run local start script.
27. Generate API client.
28. Build frontend.
29. Deploy backend.
30. Deploy frontend.

## Questions To Confirm Before Implementation

Ask the project owner:

1. Should the new app use Firebase Authentication again?
2. Should generated Angular API client files be committed or generated in CI?
3. Should Cloud Run use default egress or static outbound IP through VPC connector + Cloud NAT?
4. Should the Docker build install with Poetry directly or export `requirements.txt` for deployment compatibility?
5. Which roles are required for `DOCS_REQUIRED_ROLE` and app authorization?
6. Which external integrations need Secret Manager entries from day one?

