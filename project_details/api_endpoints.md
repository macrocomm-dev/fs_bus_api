# API Endpoints

Base URL: `https://bus-track-api-379989015900.africa-south1.run.app`

---

## POST `/auth/token` — Get Access Token

Exchange email and password for a Firebase ID token. The returned `id_token` is used as the `Bearer` token on all protected endpoints. Tokens expire after **1 hour**.

**Request body:**

```json
{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

**cURL:**

```bash
curl -X 'POST' \
  'https://bus-track-api-379989015900.africa-south1.run.app/auth/token' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "email": "user@example.com",
  "password": "yourpassword"
}'
```

**Response `200`:**

```json
{
  "provider": "firebase",
  "id_token": "<id_token>",
  "refresh_token": "<refresh_token>",
  "expires_in": 3600,
  "email": "user@example.com",
  "local_id": "firebase_uid_abc123",
  "registered": true
}
```

---

## POST `/auth/refresh` — Refresh Access Token

Exchange a `refresh_token` for a new `id_token` when the current one has expired.

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
  "provider": "firebase",
  "id_token": "<new_id_token>",
  "refresh_token": "<new_refresh_token>",
  "expires_in": 3600
}
```

**Error responses:**

| Code | Reason |
|------|--------|
| 401  | Invalid or expired refresh token |
| 503  | Firebase service unavailable |

---

## POST `/authentication/get_token` — Get App Login Context

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

Submit one completed monitor shift with all nested bus inspections. Requires a valid Bearer token.

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
        "inspections": {
          "external": {
            "internal_inspection_id": "a1b2c3d4-0001-0001-0001-000000000001",
            "inspection_time": "2026-05-01T08:00:00",
            "inspection_lat": -26.2045,
            "inspection_lon": 28.0480,
            "tyres": {
              "pass_": true,
              "reason": null,
              "photos": []
            },
            "windows": {
              "pass_": true,
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
              "pass_": true,
              "reason": null,
              "photos": []
            },
            "aisle": {
              "pass_": true,
              "reason": null,
              "photos": []
            },
            "other": {
              "pass_": true,
              "reason": null,
              "photos": []
            }
          },
          "driver": {
            "internal_inspection_id": "a1b2c3d4-0001-0001-0001-000000000003",
            "inspection_time": "2026-05-01T08:07:00",
            "inspection_lat": -26.2047,
            "inspection_lon": 28.0482,
            "license_disk_scan_succeeded": true,
            "destination_displayed": true,
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
              "behind_schedule_interval": "5-10 mins"
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
  "message": "success"
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
