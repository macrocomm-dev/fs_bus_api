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
if [[ -f ".env" ]]; then
    echo "[start] Loading environment from .env"
    set -o allexport
    # shellcheck disable=SC1091
    source .env
    set +o allexport
fi

GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-bus_track}"
CLOUD_SQL_INSTANCE="${CLOUD_SQL_INSTANCE:-bus_track:us-central1:fs-bus-db}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
API_PORT="${API_PORT:-8000}"

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

# ---------------------------------------------------------------------------
# 5. Cleanup on exit
# ---------------------------------------------------------------------------
cleanup() {
    echo ""
    echo "[start] Shutting down..."
    if [[ -n "${PROXY_PID}" ]]; then
        echo "[start] Stopping Cloud SQL Auth Proxy (PID=${PROXY_PID})"
        kill "${PROXY_PID}" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# 6. Launch the API
# ---------------------------------------------------------------------------
echo "[start] Starting FS Bus API on port ${API_PORT}"
echo "[start] Docs available at http://127.0.0.1:${API_PORT}/docs"

uvicorn app.main:app \
    --host "127.0.0.1" \
    --port "${API_PORT}" \
    --reload
