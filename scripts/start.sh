#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/start.sh - Launch FS Bus local services
#
# Starts:
#   - Cloud SQL Auth Proxy
#   - Angular dev server
#   - FastAPI / Uvicorn API
#
# Usage:
#   bash scripts/start.sh
# ---------------------------------------------------------------------------

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="${ROOT_DIR}/.local/pids"
mkdir -p "${PID_DIR}"
cd "${ROOT_DIR}"

load_dotenv_file() {
    local env_file="$1"
    local line key value

    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line//[[:space:]]/}" ]] && continue
        [[ "$line" != *"="* ]] && continue

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
FRONTEND_PORT="${FRONTEND_PORT:-4200}"
LOAD_GCP_SECRETS="${LOAD_GCP_SECRETS:-false}"

export GOOGLE_CLOUD_PROJECT CLOUD_SQL_INSTANCE DB_HOST DB_PORT API_PORT FRONTEND_PORT LOAD_GCP_SECRETS

if [[ "${LOAD_GCP_SECRETS}" != "true" ]]; then
    echo "[start] Secret Manager lookup disabled for local startup (set LOAD_GCP_SECRETS=true to enable)"
fi

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

echo "[start] Installing dependencies from requirements.txt"
pip install --quiet -r requirements.txt

PROXY_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    echo "[start] Shutting down services started by this script..."
    if [[ -n "${FRONTEND_PID}" ]]; then
        kill "${FRONTEND_PID}" 2>/dev/null || true
        rm -f "${PID_DIR}/frontend.pid"
    fi
    if [[ -n "${PROXY_PID}" ]]; then
        kill "${PROXY_PID}" 2>/dev/null || true
        rm -f "${PID_DIR}/cloud-sql-proxy.pid"
    fi
}
trap cleanup EXIT INT TERM

if ! ss -ltn | grep -q ":${DB_PORT} "; then
    proxy_bin=""
    if command -v cloud-sql-proxy &>/dev/null; then
        proxy_bin="cloud-sql-proxy"
    elif [[ -x "./cloud-sql-proxy" ]]; then
        proxy_bin="./cloud-sql-proxy"
    fi

    if [[ -n "${proxy_bin}" ]]; then
        echo "[start] Starting Cloud SQL Auth Proxy for instance: ${CLOUD_SQL_INSTANCE}"
        "${proxy_bin}" --address "127.0.0.1" --port "${DB_PORT}" "${CLOUD_SQL_INSTANCE}" &
        PROXY_PID=$!
        echo "${PROXY_PID}" > "${PID_DIR}/cloud-sql-proxy.pid"
        echo "[start] Cloud SQL Auth Proxy started (PID=${PROXY_PID})"
        sleep 2
    else
        echo "[start] WARNING: cloud-sql-proxy not found. Skipping proxy startup."
    fi
else
    echo "[start] Port ${DB_PORT} is already listening; leaving existing DB proxy/service alone."
fi

FRONTEND_DIR="${ROOT_DIR}/frontend/app"
if [[ -d "${FRONTEND_DIR}" ]]; then
    if ss -ltn | grep -q ":${FRONTEND_PORT} "; then
        echo "[start] Port ${FRONTEND_PORT} is already listening; leaving existing Angular server alone."
    else
        echo "[start] Starting Angular dev server on port ${FRONTEND_PORT}"
        (cd "${FRONTEND_DIR}" && yarn start --port "${FRONTEND_PORT}" 2>&1 | sed 's/^/[angular] /') &
        FRONTEND_PID=$!
        echo "${FRONTEND_PID}" > "${PID_DIR}/frontend.pid"
        echo "[start] Angular dev server started (PID=${FRONTEND_PID})"
    fi
    echo "[start] Angular app available at http://localhost:${FRONTEND_PORT}"
else
    echo "[start] WARNING: Angular frontend not found at ${FRONTEND_DIR}. Skipping."
fi

echo "[start] Starting FS Bus API on port ${API_PORT}"
echo "[start] Docs available at http://127.0.0.1:${API_PORT}/docs"
echo "$$" > "${PID_DIR}/api-supervisor.pid"

uvicorn app.main:app \
    --host "127.0.0.1" \
    --port "${API_PORT}" \
    --reload
