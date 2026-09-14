# API Endpoints

Base URL: `https://bus-track-api-379989015900.africa-south1.run.app`

---

## GET `/routes/departures.csv` — Download Current Timetables

For first-time integration, read the [step-by-step mobile developer guide](mobile_departures_api_guide.md).
It covers request/response models, every CSV column, first download, ETags,
offline storage, error handling, pseudocode, and cURL examples. The endpoint's
Swagger description also includes the mobile usage steps and response headers.

Named models in `app/schemas/departure.py`:

- `DepartureDownloadRequest`: query parameters; this GET has no JSON body.
- `DepartureCsvRow`: a validated parsed CSV row; the HTTP 200 response remains a CSV file.
- JSON 401/500 responses reuse `ErrorResponse`; 422 uses FastAPI's validation error contract.
- HTTP 304 has no response body.

Requires `Authorization: Bearer <firebase-id-token>`. Optional query parameter:
`operator_id` (positive integer); omit it to download all operators' active schedules.

Returns HTTP 200 with a UTF-8 CSV attachment:

```csv
uid,schedule_uid,operator_id,duty_no,departure,origin,destination,direction,valid_days,bus_type
```

Times are local `Africa/Johannesburg`, formatted as `HH:MM`. UUIDs identify
departure records and their published schedule version. No published data
returns a header-only CSV.

Save the response `ETag`. Send it in `If-None-Match` on the next request to the
same URL/filter; HTTP 304 means the locally cached CSV is still current. On
HTTP 200, replace the complete local cache after validating the download. On
network/auth failure, retain the cached schedule for offline use.

See `project_details/flows/route_departures_flow.md` for the import workflow,
versioning rules, and required database migration. The new endpoint becomes
available on Cloud Run after the backend change is deployed.

---

## POST `/auth/refresh` — Refresh Access Token

Exchange a `refresh_token` for a new bearer token and the current app user context.

**Request body:**

```json
{
  "refresh_token": "<refresh_token>"
}
```

**cURL:**

```bash
curl -X 'POST' \
  'https://bus-track-api-379989015900.africa-south1.run.app/auth/refresh' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "refresh_token": "<refresh_token>"
}'
```

**Response `200`:**

```json
{
  "access_token": "<new_id_token>",
  "refresh_token": "<new_refresh_token>",
  "token_type": "bearer",
  "role": "Supervisor",
  "user_id": "firebase_uid_abc123",
  "name": "Ada",
  "surname": "Lovelace",
  "expires_at": "2026-05-20T14:30:00Z"
}
```

**Error responses:**

| Code | Reason |
|------|--------|
| 401  | Invalid or expired refresh token |
| 503  | Firebase service unavailable |

---

## POST `/auth/get_token` — Get App Login Context

Exchange email and password for a Firebase ID token plus the app user context stored in the database.

**Request body:**

```json
{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

**Response `200`:**

```json
{
  "access_token": "<id_token>",
  "refresh_token": "<refresh_token>",
  "token_type": "bearer",
  "role": "Supervisor",
  "user_id": "firebase_uid_abc123",
  "name": "Ada",
  "surname": "Lovelace",
  "expires_at": "2026-05-01T09:00:00Z"
}
```

---

## POST `/shift/create_shift/` — Create Shift

Destination-display evidence: the optional bus-level `photos` array sits beside
`destination_displayed`; see the [mobile photo guide](mobile_destination_photos_guide.md)
for exact JSON, multipart file names, readback, and deployment order.

Submit one completed monitor shift with all nested bus inspections. Requires a valid Bearer token.

Schedule inspection choices: see the [mobile schedule inspection guide](mobile_schedule_inspections_guide.md)
for the exact new `behind_schedule_interval` strings, an example, offline
compatibility, and deployment order. The nested JSON structure is unchanged.

**Headers:**

| Header | Value |
|--------|-------|
| `Authorization` | `Bearer <id_token>` |
| `Content-Type` | `application/json` |

**cURL:**

```bash
curl -X 'POST' \
  'https://bus-track-api-379989015900.africa-south1.run.app/shift/create_shift/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <id_token>' \
  -d '{
    "user_id": "firebase_uid_abc123",
    "start_time": "2026-05-01T07:00:00",
    "end_time": "2026-05-01T15:30:00",
    "start_lat": -26.2041,
    "start_lon": 28.0473,
    "end_lat": -26.2089,
    "end_lon": 28.0512,
    "device_id": "device_001",
    "selfies": [
      {
        "timestamp": "2026-05-01T07:05:00",
        "lat": -26.2041,
        "lon": 28.0473,
        "photo": "<base64_encoded_image>"
      }
    ],
    "busses": [
      {
        "bus_id": "VIN0001ZA",
        "bus_number": "GA 01 001 GP",
        "license_disk_scan_succeeded": true,
        "destination_displayed": true,
        "photos": [],
        "inspections": {
          "external_inspected": true,
          "internal_inspected": true,
          "driver_inspected": true,
          "passenger_counts_done": true,
          "behind_schedule_reports_done": true,
          "external": {
            "internal_inspection_id": "a1b2c3d4-0001-0001-0001-000000000001",
            "inspection_time": "2026-05-01T08:00:00",
            "inspection_lat": -26.2045,
            "inspection_lon": 28.0480,
            "tyres": {
              "pass_": false,
              "reason": null,
              "photos": []
            },
            "windows": {
              "pass_": false,
              "reason": null,
              "photos": []
            },
            "other": {
              "pass_": false,
              "reason": "Body damage on left rear panel",
              "photos": [
                {
                  "timestamp": "2026-05-01T08:02:00",
                  "lat": -26.2045,
                  "lon": 28.0480,
                  "photo": "<base64_encoded_image>"
                }
              ]
            }
          },
          "internal": {
            "internal_inspection_id": "a1b2c3d4-0001-0001-0001-000000000002",
            "inspection_time": "2026-05-01T08:05:00",
            "inspection_lat": -26.2046,
            "inspection_lon": 28.0481,
            "fire_extinguisher_present": true,
            "seats": {
              "pass_": false,
              "reason": null,
              "photos": []
            },
            "aisle": {
              "pass_": false,
              "reason": null,
              "photos": []
            },
            "other": {
              "pass_": false,
              "reason": null,
              "photos": []
            }
          },
          "driver": {
            "internal_inspection_id": "a1b2c3d4-0001-0001-0001-000000000003",
            "inspection_time": "2026-05-01T08:07:00",
            "inspection_lat": -26.2047,
            "inspection_lon": 28.0482,
            "prdp_scan_succeeded": true,
            "prdp_expiry_date": "2027-03-15T00:00:00",
            "driver_identified": true,
            "driver_fail_reason": null,
            "driver_name": "Sipho Nkosi"
          },
          "passenger_counts": [
            {
              "internal_inspection_id": "a1b2c3d4-0001-0001-0001-000000000004",
              "inspection_time": "2026-05-01T08:15:00",
              "inspection_lat": -26.2050,
              "inspection_lon": 28.0488,
              "number_seated": 32,
              "number_standing": 8
            }
          ],
          "behind_schedule_reports": [
            {
              "internal_inspection_id": "a1b2c3d4-0001-0001-0001-000000000005",
              "inspection_time": "2026-05-01T08:20:00",
              "inspection_lat": -26.2052,
              "inspection_lon": 28.0490,
              "behind_schedule_interval": "6-15 mins late"
            }
          ]
        }
      }
    ]
  }'
```

**Response `201`:**

```json
{
  "status": 201,
  "message": "success",
  "shift_id": 12345
}
```

**Error responses:**

| Code | Reason |
|------|--------|
| 401  | Missing or invalid Bearer token |
| 422  | Validation error — malformed request body |
| 500  | Internal server error |

---

### Inspection Types

| Value | Description |
|-------|-------------|
| `external` | Exterior inspection (tyres, windows, ext_other) |
| `internal` | Interior inspection (seats, aisle, int_other) |
| `count` | Passenger count (number_seated, number_standing) |
| `driver` | Driver identification check |
| `behind_schedule` | Behind-schedule report (behind_schedule_interval) |
