# Mobile Developer Guide: Downloading Departure Timetables

This guide is for the external mobile app team. The API provides a CSV file
that the app downloads while online and stores for offline schedule lookup.
The app does not need direct database access.

Implementation status: the database is populated and the endpoint is
implemented/tested locally. The backend change must be deployed before this
new endpoint is available on the Cloud Run URL below.

## 1. What you need to build

Implement a "refresh saved timetable" operation that:

1. Makes an authenticated GET request when online.
2. Downloads and parses a CSV file on the first request.
3. Saves the parsed timetable and the response's ETag together on the device.
4. Uses the saved timetable while offline.
5. Checks for changes later and replaces the saved timetable when needed.

Suggested times to check are app startup while online and when connectivity
returns. These are client scheduling recommendations; the API does not push
updates to devices. Do not require a download for every departure lookup.

## 2. Request model: GET parameters and headers

```http
GET https://bus-track-api-379989015900.africa-south1.run.app/routes/departures.csv?operator_id=1
Authorization: Bearer <firebase-id-token>
Accept: text/csv
```

There is **no JSON request body** for this endpoint.

For the general FS app, omit `operator_id` to download all published operators;
the project covers IBL and Maluti. Use `operator_id=1` only for an intentionally
IBL-only cache. Omit the parameter entirely rather than sending `operator_id=`.
Keep the CSV and ETag scoped to the same selection. See the
[operator-selection explanation](mobile_destination_photos_guide.md#which-operator-should-the-fs-mobile-app-download).

| Input | Where it goes | Required? | Meaning |
|---|---|---|---|
| `operator_id` | URL query parameter | No | Positive integer. `1` is Interstate Bus Lines. Omit to download all operators' active timetables. |
| `Authorization` | HTTP header | Yes | `Bearer ` followed by the Firebase ID/access token from the existing sign-in flow. |
| `Accept` | HTTP header | Recommended | Use `text/csv`. |
| `If-None-Match` | HTTP header | No | The ETag saved with the existing local timetable. Omit if you do not have a usable matching local timetable. |

Use the same valid Firebase token used for other protected API calls, including
shift submission. Do not put the refresh token in the Authorization header.
The ETag is unrelated to authentication and must never replace the bearer token.

The backend's named query model is `DepartureDownloadRequest` in
`app/schemas/departure.py`. Authentication and `If-None-Match` are separate HTTP
headers. FastAPI validates the query and documents the headers in OpenAPI.

## 3. Response model: a CSV file

HTTP 200 contains **CSV text, not JSON and not a JSON array**. Generated HTTP
clients may expose the body as a file, byte array, blob, or string. Decode it as
UTF-8 and pass it to a CSV parser. Do not call a JSON decoder on a 200 response.

Example response (identifiers and shortened ETag are illustrative):

```http
HTTP/1.1 200 OK
Content-Type: text/csv; charset=utf-8
Content-Disposition: attachment; filename="route-departures.csv"
ETag: "example-fingerprint"
Cache-Control: private, no-cache

uid,schedule_uid,operator_id,duty_no,departure,origin,destination,direction,valid_days,bus_type
c084710e-e075-432c-bca6-04ba59c697e5,b6e73094-3936-499f-869b-1f688b8b0f94,1,504,04:40,Freedomsquare,Central Park,Forward,Monday to Friday,Standard
```

Every field is present. The backend validates each exported row with
`DepartureCsvRow` in `app/schemas/departure.py`.

| Column | Type after CSV parsing | Meaning / handling |
|---|---|---|
| `uid` | UUID string | Unique departure record in this schedule version. |
| `schedule_uid` | UUID string | Identifies the schedule version containing this row. |
| `operator_id` | Positive integer | Operator owning the row. CSV parsers usually return text; convert this field to an integer if needed. |
| `duty_no` | String | Duty identifier such as `504` or `005`. Keep leading zeros. This is not a route code or a vehicle ID. |
| `departure` | String, `HH:MM` | Local South African time, for example `04:40`. It is not a date or UTC timestamp; do not apply a timezone conversion. |
| `origin` | String | Starting location. |
| `destination` | String | Destination location. |
| `direction` | String | Current labels: `Forward`, `Reverse`. |
| `valid_days` | String | Current labels: `Monday to Friday`, `Saturday`, `Sunday`. No separate holiday calendar is provided. |
| `bus_type` | String | Current labels: `Standard`, `Train`. Preserve these source labels. |

Use a CSV library that supports quoted fields, escaped quotes, UTF-8, and CRLF
line endings. Locations can contain commas; `line.split(',')` is not a valid
CSV parser. Map columns by header name rather than treating their position as
their meaning. Day groups and bus types are strings, not enforced API enums;
handle an unfamiliar label without crashing.

The response is the complete active selection, without pagination. If there
are no published departures for the requested selection, HTTP 200 contains the
header and zero data rows. This includes an operator ID with no published
schedule; it does not return 404. A valid empty CSV represents an empty current
selection. A zero-byte HTTP 200 body is not a valid CSV; keep the previous cache.

OpenAPI describes the HTTP 200 body as `text/csv` with a binary/string schema,
so generated clients do not expect JSON. Its `x-csv-row-schema` extension also
contains the typed row definition. This extension is supplementary; standard
client generators may ignore it, so use the column table above when defining
your mobile row model. HTTP 304 has no body and therefore no row model.

## 4. What an ETag means

An ETag is a fingerprint of the exact CSV returned by the API. The server
computes a SHA-256 fingerprint and sends it in the `ETag` response header.
Treat the value as opaque text: save it exactly, **including quotation marks**.
Do not compute your own fingerprint from parsed rows.

If the response contents change, the ETag changes. An identical reimport of
the current timetable makes no database changes, so its download ETag remains
the same. An ETag identifies the entire selected CSV, not an individual row.

The ETag and CSV must be saved as one matching pair. The saved key should
include the API base URL and operator selection: the IBL-only download and
the all-operators download have separate caches. Do not reuse one selection's
ETag for another selection.

`Cache-Control: private, no-cache` permits caching; it asks HTTP caches to
check freshness before reusing the response. The mobile app explicitly stores
the timetable for offline use. This is not `no-store`.

## 5. Checking for updates

On the first download, omit `If-None-Match`. After saving a CSV and ETag, send:

```http
GET /routes/departures.csv?operator_id=1
Authorization: Bearer <current-firebase-id-token>
Accept: text/csv
If-None-Match: "example-fingerprint"
```

The API compares that header with the current CSV's ETag:

| Response | What the app should do |
|---|---|
| `304 Not Modified` | Keep the saved CSV and ETag. There is no response body to parse. This is a successful check. |
| `200 OK` | Parse and validate the complete new CSV, then replace that selection's local timetable and ETag together. Do not append rows. |
| `401 Unauthorized` | Keep the cache. Use the existing auth refresh/login flow, then retry once with a valid ID token. Do not retry indefinitely. |
| `422 Unprocessable Entity` | Keep the cache. Fix invalid query parameters, such as `operator_id=0` or `operator_id=abc`. |
| `500`, other server errors, timeout, or disconnected network | Keep the cache and retry later. Do not save an error body as CSV. |

Some HTTP libraries report 304 through their error callback because it is
outside the 200–299 range. Configure or handle 304 explicitly as "unchanged".
If the local CSV was deleted or cannot be parsed, omit `If-None-Match` even if
an ETag is still stored: you need a full download to rebuild the cache.

JSON errors use the existing API error contracts. For example, a missing token:

```json
{"detail":"Could not validate credentials"}
```

Validation errors have a `detail` array containing field errors. Look at the
HTTP status before choosing a CSV or JSON parser.

## 6. Safe local storage and offline behavior

Download to temporary memory/file storage first. Check HTTP status, content
type, CSV header, row fields, and ETag before changing the saved timetable.
Use a local database transaction or an equivalent storage mechanism to save
the new rows and their ETag together. If the download, validation, or save
fails, keep the previous complete timetable and ETag.

This prevents a half-downloaded file from removing the user's working offline
schedule. It also ensures the app never claims it has the latest ETag while
still holding old rows. Serialize refreshes for each selection so two requests
cannot overwrite the local cache out of order.

When offline, read the stored timetable directly. If it has never been
downloaded, show "No timetable saved. Connect to download it." The existing
offline shift-capture workflow is otherwise unchanged by this endpoint.

Illustrative pseudocode (storage and HTTP names are placeholders for your app):

```text
refreshTimetable(selection):
    prevent another refresh for the same selection from running concurrently
    cached = loadSavedTimetableAndETag(selection)
    if offline:
        return cached or "No timetable saved"

    headers = {Authorization: "Bearer " + validFirebaseIdToken,
               Accept: "text/csv"}
    if cached has a valid CSV and ETag:
        headers["If-None-Match"] = cached.etag

    response = GET selection.url with headers
    if response.status == 304:
        return cached
    if response.status == 401:
        if authentication has not yet been retried:
            refresh authentication using existing app flow
            return result of retrying this refresh with further auth retries disabled
        otherwise:
            report authentication failure and return cached data
    if response.status is not 200:
        report the failure or schedule a later retry, then return cached data

    newRows = parseAndValidateCsv(response.body)
    newETag = response.headers["ETag"]
    validate newETag is present
    saveRowsAndETagTogether(selection, newRows, newETag)
    return newly saved timetable

on any network, parsing, validation, or storage error:
    keep the previous saved timetable and ETag
```

## 7. Try the API with cURL

After the endpoint is deployed, substitute a valid Firebase ID token below.
Keep tokens out of source control and logs. These commands write to download
staging files, not to the app's saved timetable.

```bash
FS_BUS_API_URL='https://bus-track-api-379989015900.africa-south1.run.app'
FS_BUS_ID_TOKEN='<paste-a-valid-firebase-id-token>'

curl --fail-with-body --max-time 30 \
  "$FS_BUS_API_URL/routes/departures.csv?operator_id=1" \
  -H "Authorization: Bearer $FS_BUS_ID_TOKEN" \
  -H 'Accept: text/csv' \
  --dump-header departures-download.headers \
  --output departures-download.csv \
  --write-out 'HTTP %{http_code}\n'
```

Inspect the status, the CSV, and the `ETag` line in the headers file. Copy the
ETag value (including double quotes) into `FS_BUS_ETAG`, then check again:

```bash
FS_BUS_ETAG='"paste-the-etag-value-here"'

curl --fail-with-body --max-time 30 \
  "$FS_BUS_API_URL/routes/departures.csv?operator_id=1" \
  -H "Authorization: Bearer $FS_BUS_ID_TOKEN" \
  -H 'Accept: text/csv' \
  -H "If-None-Match: $FS_BUS_ETAG" \
  --dump-header departures-recheck.headers \
  --output departures-recheck.csv \
  --write-out 'HTTP %{http_code}\n'
```

Expect HTTP 304 and no CSV response body if nothing changed. Keep the first
successful download; never replace it with a 304's empty staging file.

## 8. Schedule history and shift submissions

Only current schedules are returned by this endpoint. The API stores all old
versions, but this endpoint does not download history. When a changed schedule
is published, its departure rows receive new UUIDs. Do not assume a UUID lasts
forever for a duty number, and do not rewrite previously captured offline
records to refer to the new timetable.

This work does not add `uid` or `schedule_uid` to the existing shift submission
request. Continue sending the agreed shift payload. A future explicit contract
change would be needed to submit departure references with shifts.

The database publication procedure is documented separately in
[Route Departure Timetables](flows/route_departures_flow.md).
