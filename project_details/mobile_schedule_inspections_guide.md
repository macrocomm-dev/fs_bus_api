# Mobile Schedule Inspection Values — September 2026

The JSON object structure is unchanged. Continue using `behind_schedule_interval`
inside `busses[].inspections.behind_schedule_reports[]`. The inspection type is
still `behind_schedule`, including for early departures. Only the possible
string values and dashboard presentation have expanded.

## Exact values for new captures

| Mobile label | JSON `behind_schedule_interval` value |
|---|---|
| Early departure | `Early departure` |
| On time / 0–5 minutes late | `0-5 mins` |
| 6–15 minutes late | `6-15 mins late` |
| 15–30 minutes late | `15-30 mins late` |
| 30 minutes or more late | `30+ mins late` |

Use the JSON values exactly as written, including case, spaces, `late`, and the
ordinary ASCII hyphen (`-`). UI labels can use an en dash (`–`); do not send the
display label as the API value. The existing `0-5 mins` option is retained so
on-time observations can still be captured and reported separately from early
or late departures.

Example nested report (place this in the existing `behind_schedule_reports`
array; do not submit it as the entire shift request):

```json
{
  "internal_inspection_id": "schedule-report-20260914-001",
  "inspection_time": "2026-09-14T08:20:00",
  "inspection_lat": -29.1187,
  "inspection_lon": 26.2145,
  "behind_schedule_interval": "6-15 mins late"
}
```

For an early departure, only change the final value to `Early departure`.
JSON and multipart shift submissions use the same list of accepted strings.
The API records the band selected by the app; it does not calculate a band from
the timestamp or timetable. Exact boundary handling, such as the shared label
boundary at 15 minutes, must be consistent in the mobile selection logic.

## Old versions of the mobile app and offline queues

These old strings remain accepted unchanged for queued/offline reports:

```text
5-10 mins
10-15 mins
15+ mins
```

Do not rewrite queued records to the new bands. The recorded band does not
contain enough information to make that conversion reliably, especially for
`15+ mins`, which could represent any delay beyond 15 minutes.

The API schema intentionally contains both current and legacy values to keep
older app versions working during rollout. Show only the five current choices
in the updated capture UI. Unknown/blank values still trigger the existing
temporary `0-5 mins` fallback and normalization audit entry; always require an
explicit valid selection in the mobile UI rather than relying on that fallback.

## Dashboard behavior

- Current cards and drilldowns show the new bands and the on-time band.
- Early departures are included in total inspected route-start checks but are
  neither on time nor late. They have a separate count and trend series.
- The delayed-departure total counts only late bands, including old late bands.
- Old bands appear separately with a `legacy` label when the selected dates
  contain those records. They are not relabelled or migrated into new bands.
- Major delays use `15-30 mins late` and `30+ mins late` for new reports. Old
  `10-15 mins` and `15+ mins` retain the previous major-delay classification.
  A combined historical trend therefore includes the definitions used by each
  generation of the capture form; it is not a remeasurement of exact minutes.

## Deployment order

Deploy the backend before releasing a mobile build that sends the new strings.
The previous backend accepts an unrecognized string by defaulting it to
`0-5 mins`, so releasing the mobile change first would lose the intended band.
Confirm the deployed `/openapi.json` enum lists the new choices before rollout.
Deploy the dashboard changes with the backend; its generated enum has also
been refreshed. No database schema migration is required: the existing column
is text and has no interval check constraint. No historical rows are updated.

## Docs login: successful sign-in followed by HTTP 403

Firebase authentication and the docs role check are separate. A valid password
can produce a token that lacks the role required by protected `/openapi.json`.
The docs currently require the Firebase custom claim `role: Admin`. An Admin
role in the application database alone does not put that claim in the token.

On 2026-09-14, `mbsadmin@fsbus.example.com` was enabled and its matching database
record was active with role `Admin`, but its Firebase custom claims were empty.
The missing Admin claim was restored for that account only. Its password and
operator association were unchanged. The available evidence does not establish
when or why the claim was removed.

David should open `/docs`, click **Clear Token**, and use **Sign In For Testing**
again with the same MBS email/password. A fresh Firebase ID token will include
the restored role. Loading an old pasted token again will still fail.
The claim repair is live; the new interval contract and improved docs error
message require deployment of the code changes.
