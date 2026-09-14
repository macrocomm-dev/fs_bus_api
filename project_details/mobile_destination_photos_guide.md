# Destination-display photos and route selection

## Which operator should the FS mobile app download?

The project scope covers Interstate Bus Lines (IBL) and Maluti. For the general
FS monitoring app, omit the operator filter so the offline cache contains every
operator's currently published timetable:

```http
GET /routes/departures.csv
Authorization: Bearer <Firebase ID token>
Accept: text/csv
```

Use `GET /routes/departures.csv?operator_id=1` only when the app deliberately
needs IBL alone. Omit the parameter entirely for all operators; do not send
`operator_id=` or `operator_id=null` (these return 422). The CSV includes an
`operator_id` on every row, so the app can filter its cached rows locally.
Only published active timetables are returned; the download does not promise
that a timetable has already been supplied for every operator in the project.
On 2026-09-14, the database had one active timetable: IBL with 1,172 departures.
The filter is a data selection, not a permission setting or user assignment.
Keep the CSV and ETag together for the selected URL. When switching from an
IBL-only cache to an all-operator cache, do a first download without the old
`If-None-Match`. See [the departures guide](mobile_departures_api_guide.md).

## Destination Displayed Correctly: JSON submission

Keep the existing boolean `destination_displayed`. Add a lowercase `photos`
array immediately beside it, inside each `busses[]` entry. This bus-level array
belongs specifically to the destination-display question. Other inspection
photos remain inside their existing checklist items.

Example bus entry within the existing shift request (not a complete request):

```json
{
  "bus_id": "VIN0001ZA",
  "bus_number": "BUS-001",
  "duty_number": "504",
  "replacement_bus": false,
  "license_disk_scan_succeeded": true,
  "destination_displayed": false,
  "photos": [
    {
      "timestamp": "2026-09-14T08:15:00",
      "lat": -29.1187,
      "lon": 26.2145,
      "photo": "<base64-encoded-image>"
    }
  ],
  "inspections": {}
}
```

- Submit through the existing `POST /shift/create_shift/` JSON endpoint.
- Field names are case-sensitive: use `photos`, not `Photos`, and
  `destination_displayed`, not `Destination_displayed`. JSON field order has no
  effect; placing the array after the boolean simply makes the example clearer.
- Each photo uses the same timestamp, GPS, and base64 format as existing photos.
  Keep the original capture timestamp/GPS when uploading from an offline queue.
- The array is optional. Omit it or send `[]` if no photos were captured.
- Photos are allowed for either answer; attaching a photo does not change the
  destination answer or any inspection's pass/fail result.
- Photos can be uploaded even if no other inspection section was completed.
  Continue supplying any sections that were completed in `inspections`.
- Existing clients that do not send the array continue to work.

## Multipart compatibility

The existing multipart endpoint remains hidden from Swagger and is not needed
for the normal JSON integration. If using `POST /shift/create_shift_multipart/`,
put the same photo metadata in `data.busses[i].photos[k]`, without the `photo`
base64 field. The `data` part is the JSON string for the whole shift.
Upload the corresponding image file under:

```text
bus_{i}_destination_displayed_photo_{k}
```

Indexes start at zero. For the first bus's first photo the name is
`bus_0_destination_displayed_photo_0`. Missing files referenced by metadata
return 422 with the missing file name.

## Reading and viewing the evidence

The existing `/inspection/bus_inspections` grouped endpoints return a `photos`
array beside `destination_displayed`. Each returned photo includes `id`,
`timestamp`, `lat`, `lon`, `photo` (base64), and `created_at`.
Filters by shift, bus, and user also apply to destination photos. Date/time
filters select photos by their capture timestamp. Photo-only bus groups have
empty inspection sections; they do not represent extra inspection events.
Evidence is grouped using the existing shift, bus, duty, and replacement-bus
identity, so two duties or an original/replacement entry keep separate arrays.

In the dashboard, expand the shift row to view **Destination Displayed Correctly
— Photos**, the answer, capture time/GPS, and image previews. These photos are
not added to inspection counts, failed-inspection totals, or timelines.

## Storage and rollout

Photos use the new `photos.destination_display` table, linked to the shift and
bus grouping. Storing them independently avoids duplicating evidence across
external/internal/driver events and supports bus entries without such events.
No existing inspection/photo rows are rewritten.

Apply `scripts/20260914_destination_display_photos.sql` before deploying the
backend. The migration is additive and can be rerun safely. Deploy backend and
dashboard before enabling uploads in the mobile app. An older backend ignores
unknown request fields, so it would silently discard the new bus-level array.
The generated Angular JSON request/response models have been refreshed.

Implementation status (2026-09-14): the migration was applied to the configured
Cloud SQL database and the new table was verified empty. Backend and dashboard
code deployment remain pending. All 95 backend tests pass and the dashboard
production build passes with its existing size warnings.
