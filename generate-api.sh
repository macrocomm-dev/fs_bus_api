./generate-api.sh./generate-api.sh#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# generate-api.sh — Generate TypeScript types from the FS Bus API OpenAPI spec
#
# Prerequisites:
#   • Backend must be running (./start.sh)
#   • frontend/app/.env.local must have API_ADMIN_EMAIL and API_ADMIN_PASS set
#
# Usage:
#   chmod +x generate-api.sh
#   ./generate-api.sh
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="${SCRIPT_DIR}/frontend/app"

echo "[generate-api] Running OpenAPI generator..."
cd "${FRONTEND_DIR}"
node scripts/generate-api.mjs
