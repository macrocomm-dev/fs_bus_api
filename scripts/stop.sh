#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/stop.sh - Stop FS Bus local services safely
#
# Stops services started by scripts/start.sh, plus common detached local runs:
#   - FastAPI / Uvicorn API for app.main:app
#   - Angular dev server on FRONTEND_PORT
#   - Cloud SQL Auth Proxy for CLOUD_SQL_INSTANCE / DB_PORT
#
# Usage:
#   bash scripts/stop.sh
# ---------------------------------------------------------------------------

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="${ROOT_DIR}/.local/pids"
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
    load_dotenv_file ".env"
fi

CLOUD_SQL_INSTANCE="${CLOUD_SQL_INSTANCE:-bus-track-480813:africa-south1:fs-bus-db}"
DB_PORT="${DB_PORT:-5432}"
API_PORT="${API_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-4200}"

is_running() {
    local pid="$1"
    [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

stop_pid() {
    local pid="$1"
    local label="$2"

    if ! is_running "${pid}"; then
        return
    fi

    echo "[stop] Stopping ${label} (PID=${pid})"
    kill "${pid}" 2>/dev/null || true

    for _ in {1..20}; do
        if ! is_running "${pid}"; then
            return
        fi
        sleep 0.2
    done

    echo "[stop] ${label} did not exit after TERM; forcing stop (PID=${pid})"
    kill -9 "${pid}" 2>/dev/null || true
}

stop_pid_file() {
    local file="$1"
    local label="$2"

    if [[ ! -f "${file}" ]]; then
        return
    fi

    local pid
    pid="$(cat "${file}" 2>/dev/null || true)"
    if [[ "${pid}" =~ ^[0-9]+$ ]]; then
        stop_pid "${pid}" "${label}"
    fi
    rm -f "${file}"
}

stop_matching() {
    local label="$1"
    local pattern="$2"
    local pids

    pids="$(pgrep -f "${pattern}" 2>/dev/null || true)"
    if [[ -z "${pids}" ]]; then
        return
    fi

    while IFS= read -r pid; do
        [[ -z "${pid}" ]] && continue
        [[ "${pid}" == "$$" ]] && continue
        stop_pid "${pid}" "${label}"
    done <<< "${pids}"
}

echo "[stop] Stopping FS Bus local services..."

stop_pid_file "${PID_DIR}/api-supervisor.pid" "FS Bus API supervisor"
stop_pid_file "${PID_DIR}/frontend.pid" "Angular dev server"
stop_pid_file "${PID_DIR}/cloud-sql-proxy.pid" "Cloud SQL Auth Proxy"

stop_matching "FS Bus API" "uvicorn app\\.main:app.*--port ${API_PORT}"
stop_matching "FS Bus API worker" "multiprocessing\\.spawn.*app\\.main|spawn_main.*uvicorn"
stop_matching "Angular dev server" "ng serve --port ${FRONTEND_PORT}"
stop_matching "Cloud SQL Auth Proxy" "cloud-sql-proxy.*(--port ${DB_PORT}|${CLOUD_SQL_INSTANCE})"

echo "[stop] Remaining listeners on configured ports:"
ss -ltnp | grep -E ":(${API_PORT}|${FRONTEND_PORT}|${DB_PORT}) " || true

echo "[stop] Done."
