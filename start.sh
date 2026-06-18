#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# start.sh — Launch FS Bus API locally
#
# Prerequisites:
#   • Python 3.12+ with a virtualenv at .venv (or activate your own venv)
#   • gcloud CLI installed and authenticated:
#       gcloud auth application-default login
#   • Cloud SQL Auth Proxy binary on PATH (or at ./cloud-sql-proxy):
#       https://cloud.google.com/sql/docs/postgres/connect-auth-proxy
#   • A .env file (copy .env.example and fill in values)
#
# Usage:
#   chmod +x start.sh
#   ./start.sh
# ---------------------------------------------------------------------------

set -euo pipefail

# ---------------------------------------------------------------------------
# 1. Load environment variables from .env if present
# ---------------------------------------------------------------------------
load_dotenv_file() {
    local env_file="$1"
    local line
    local key
    local value

    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line//[[:space:]]/}" ]] && continue

        key="${line%%=*}"
        value="${line#*=}"

        key="${key#"${key%%[![:space:]]*}"}"
        key="${key%"${key##*[![:space:]]}"}"

        if [[ "$value" =~ ^\".*\"$ ]] || [[ "$value" =~ ^\'.*\'$ ]]; then
            value="${value:1:-1}"
        fi

        printf -v "$key" '%s' "$value"
        export "$key"
    done < "$env_file"
}

if [[ -f ".env" ]]; then
    echo "[start] Loading environment from .env"
    load_dotenv_file ".env"
fi

GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-bus-track-480813}"
CLOUD_SQL_INSTANCE="${CLOUD_SQL_INSTANCE:-bus-track-480813:africa-south1:fs-bus-db}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
API_PORT="${API_PORT:-8000}"
LOAD_GCP_SECRETS="${LOAD_GCP_SECRETS:-true}"

export GOOGLE_CLOUD_PROJECT CLOUD_SQL_INSTANCE DB_HOST DB_PORT API_PORT LOAD_GCP_SECRETS

if [[ "${LOAD_GCP_SECRETS}" != "true" ]]; then
    echo "[start] Secret Manager lookup disabled for local startup (set LOAD_GCP_SECRETS=true to enable)"
fi

# ---------------------------------------------------------------------------
# 2. Ensure virtual environment is active
# ---------------------------------------------------------------------------
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    if [[ -d ".venv" ]]; then
        echo "[start] Activating .venv"
        # shellcheck disable=SC1091
        source .venv/bin/activate
    else
        echo "[start] No virtual environment found. Creating .venv ..."
        python3 -m venv .venv
        # shellcheck disable=SC1091
        source .venv/bin/activate
    fi
fi

# ---------------------------------------------------------------------------
# 3. Install / sync dependencies
# ---------------------------------------------------------------------------
echo "[start] Installing dependencies from requirements.txt"
pip install --quiet -r requirements.txt

# ---------------------------------------------------------------------------
# 4. Start Cloud SQL Auth Proxy in the background
# ---------------------------------------------------------------------------
PROXY_PID=""

start_proxy() {
    local proxy_bin
    if command -v cloud-sql-proxy &>/dev/null; then
        proxy_bin="cloud-sql-proxy"
    elif [[ -x "./cloud-sql-proxy" ]]; then
        proxy_bin="./cloud-sql-proxy"
    else
        echo "[start] WARNING: cloud-sql-proxy not found. Skipping proxy startup."
        echo "         Download from: https://cloud.google.com/sql/docs/postgres/connect-auth-proxy"
        return
    fi

    echo "[start] Starting Cloud SQL Auth Proxy for instance: ${CLOUD_SQL_INSTANCE}"
    "$proxy_bin" \
        --address "127.0.0.1" \
        --port "${DB_PORT}" \
        "${CLOUD_SQL_INSTANCE}" &
    PROXY_PID=$!
    echo "[start] Cloud SQL Auth Proxy started (PID=${PROXY_PID})"
    # Give the proxy a moment to establish the connection
    sleep 2
}

start_proxy

FRONTEND_PORT="${FRONTEND_PORT:-4200}"
export FRONTEND_PORT

# ---------------------------------------------------------------------------
# 5. Cleanup on exit
# ---------------------------------------------------------------------------
FRONTEND_PID=""

cleanup() {
    echo ""
    echo "[start] Shutting down..."
    if [[ -n "${PROXY_PID}" ]]; then
        echo "[start] Stopping Cloud SQL Auth Proxy (PID=${PROXY_PID})"
        kill "${PROXY_PID}" 2>/dev/null || true
    fi
    if [[ -n "${FRONTEND_PID}" ]]; then
        echo "[start] Stopping Angular dev server (PID=${FRONTEND_PID})"
        kill "${FRONTEND_PID}" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# 6. Start Angular frontend in the background
# ---------------------------------------------------------------------------
FRONTEND_DIR="$(dirname "$0")/frontend/app"

if [[ -d "${FRONTEND_DIR}" ]]; then
    echo "[start] Starting Angular dev server on port ${FRONTEND_PORT}"
    (cd "${FRONTEND_DIR}" && yarn start --port "${FRONTEND_PORT}" 2>&1 | sed 's/^/[angular] /') &
    FRONTEND_PID=$!
    echo "[start] Angular dev server started (PID=${FRONTEND_PID})"
    echo "[start] Angular app available at http://localhost:${FRONTEND_PORT}"
else
    echo "[start] WARNING: Angular frontend not found at ${FRONTEND_DIR}. Skipping."
fi

# ---------------------------------------------------------------------------
# 7. Launch the API
# ---------------------------------------------------------------------------
echo "[start] Starting FS Bus API on port ${API_PORT}"
echo "[start] Docs available at http://127.0.0.1:${API_PORT}/docs"

uvicorn app.main:app \
    --host "127.0.0.1" \
    --port "${API_PORT}" \
    --reload
