#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# generate-api.sh — Generate Angular TypeScript services from the FS Bus API
#
# This script:
#   1. Loads credentials from frontend/app/.env.local
#   2. Authenticates against the running backend to get a Bearer token
#   3. Downloads the protected OpenAPI spec
#   4. Runs openapi-generator-cli (typescript-angular) to generate full
#      typed API services into frontend/app/src/app/core/api/
#
# Prerequisites:
#   • Backend must be running (./start.sh)
#   • openapi-generator-cli installed globally:
#       npm install -g @openapitools/openapi-generator-cli
#   • frontend/app/.env.local must contain:
#       API_URL=http://127.0.0.1:8000
#       API_ADMIN_EMAIL=<email>
#       API_ADMIN_PASS=<password>
#
# Usage:
#   chmod +x generate-api.sh
#   ./generate-api.sh
# ---------------------------------------------------------------------------

set -euo pipefail

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log()     { printf "%s[API-GEN]%s %s\n" "${BLUE}"  "${NC}" "$1"; }
success() { printf "%s[API-GEN]%s %s\n" "${GREEN}" "${NC}" "$1"; }
error()   { printf "%s[API-GEN]%s %s\n" "${RED}"   "${NC}" "$1"; }

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="${SCRIPT_DIR}/frontend/app"
ENV_FILE="${FRONTEND_DIR}/.env.local"
OUTPUT_DIR="${FRONTEND_DIR}/src/app/core/api"
TEMP_SPEC="/tmp/fs-bus-openapi-spec.json"

# ---------------------------------------------------------------------------
# Load .env.local
# ---------------------------------------------------------------------------
if [[ -f "${ENV_FILE}" ]]; then
    log "Loading credentials from frontend/app/.env.local"
    set -o allexport
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +o allexport
else
    error "frontend/app/.env.local not found."
    error "Create it with: API_URL, API_ADMIN_EMAIL, API_ADMIN_PASS"
    exit 1
fi

API_URL="${API_URL:-http://127.0.0.1:8000}"
API_URL="${API_URL%/}"  # strip trailing slash

if [[ -z "${API_ADMIN_EMAIL:-}" || -z "${API_ADMIN_PASS:-}" ]]; then
    error "API_ADMIN_EMAIL and API_ADMIN_PASS must be set in frontend/app/.env.local"
    exit 1
fi

# ---------------------------------------------------------------------------
# Check dependencies
# ---------------------------------------------------------------------------
if ! command -v openapi-generator-cli &>/dev/null; then
    error "openapi-generator-cli not found. Install it with:"
    error "  npm install -g @openapitools/openapi-generator-cli"
    exit 1
fi

if ! command -v curl &>/dev/null; then
    error "curl is required but not installed."
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 1 — Authenticate and get Bearer token
# ---------------------------------------------------------------------------
log "Authenticating with ${API_URL}/auth/get_token …"

LOGIN_RESPONSE=$(curl -sf -X POST "${API_URL}/auth/get_token" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${API_ADMIN_EMAIL}\",\"password\":\"${API_ADMIN_PASS}\"}" \
    || true)

if [[ -z "${LOGIN_RESPONSE}" ]]; then
    error "Auth request failed — is the backend running at ${API_URL}?"
    exit 1
fi

ACCESS_TOKEN=$(echo "${LOGIN_RESPONSE}" | python3 -c \
    "import json,sys; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null || true)

if [[ -z "${ACCESS_TOKEN}" ]]; then
    error "Could not extract access_token. Check credentials."
    error "Response: ${LOGIN_RESPONSE}"
    exit 1
fi

success "Authenticated successfully."

# ---------------------------------------------------------------------------
# Step 2 — Download OpenAPI spec
# ---------------------------------------------------------------------------
log "Fetching OpenAPI spec from ${API_URL}/openapi.json …"

HTTP_STATUS=$(curl -s -o "${TEMP_SPEC}" -w "%{http_code}" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    "${API_URL}/openapi.json")

if [[ "${HTTP_STATUS}" != "200" ]]; then
    error "Failed to fetch spec (HTTP ${HTTP_STATUS})"
    exit 1
fi

success "Spec downloaded → ${TEMP_SPEC}"

# ---------------------------------------------------------------------------
# Step 3 — Generate Angular services
# ---------------------------------------------------------------------------
log "Generating Angular TypeScript services …"

mkdir -p "${OUTPUT_DIR}"

openapi-generator-cli generate \
    -i "${TEMP_SPEC}" \
    -g typescript-angular \
    -o "${OUTPUT_DIR}" \
    --additional-properties=\
ngVersion=21,\
npmName=fs-bus-api-client,\
supportsES6=true,\
withInterfaces=true,\
useSingleRequestParameter=true,\
stringEnums=true \
    --skip-validate-spec

success "Services generated → ${OUTPUT_DIR}"

# ---------------------------------------------------------------------------
# Step 4 — Write API config helper
# ---------------------------------------------------------------------------
log "Writing API config …"

cat > "${OUTPUT_DIR}/api-config.ts" << 'EOF'
import { Configuration } from './configuration';
import { environment } from '../../../environments/environment';

function getStoredAccessToken(): string | undefined {
  try {
    const raw = globalThis.localStorage?.getItem('fs_bus_session');
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
EOF

# ---------------------------------------------------------------------------
# Step 5 — Cleanup
# ---------------------------------------------------------------------------
rm -f "${TEMP_SPEC}"

success "Done! Generated files are in: ${OUTPUT_DIR}"
log ""
log "Next steps:"
log "  1. Run \`yarn install\` inside frontend/app if new packages were added"
log "  2. Import generated services in your Angular modules/components"
log "  3. Use createApiConfiguration() to pass the Bearer token at runtime"
log ""
log "Example:"
log "  import { ShiftsService } from 'src/app/core/api';"
log "  import { createApiConfiguration } from 'src/app/core/api/api-config';"
