#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-bus-track-480813}"

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

if [[ -z "${SMART_FLEET_EMAIL:-}" ]]; then
  echo "SMART_FLEET_EMAIL is required." >&2
  echo "Example: SMART_FLEET_EMAIL='user@example.com' SMART_FLEET_API_HASH='...' $0" >&2
  exit 1
fi

if [[ -z "${SMART_FLEET_API_HASH:-}" ]]; then
  echo "SMART_FLEET_API_HASH is required." >&2
  echo "Example: SMART_FLEET_EMAIL='user@example.com' SMART_FLEET_API_HASH='...' $0" >&2
  exit 1
fi

tmp_email="$(mktemp)"
tmp_hash="$(mktemp)"
trap 'rm -f "$tmp_email" "$tmp_hash"' EXIT

printf "%s" "$SMART_FLEET_EMAIL" > "$tmp_email"
printf "%s" "$SMART_FLEET_API_HASH" > "$tmp_hash"

upsert_secret() {
  local secret_name="$1"
  local data_file="$2"

  if gcloud secrets describe "$secret_name" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud secrets versions add "$secret_name" \
      --project "$PROJECT_ID" \
      --data-file="$data_file" \
      >/dev/null
    echo "Updated secret version for $secret_name."
  else
    gcloud secrets create "$secret_name" \
      --project "$PROJECT_ID" \
      --replication-policy="automatic" \
      --data-file="$data_file" \
      >/dev/null
    echo "Created secret $secret_name."
  fi
}

upsert_secret "smart-fleet-email" "$tmp_email"
upsert_secret "smart-fleet-api-hash" "$tmp_hash"

echo "Smart Fleet secrets are ready for Cloud Run deployments."
