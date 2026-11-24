# Dashboard inspection and departure updates — 24 November 2026

## Default date range and inspection filtering

The shared date picker defaults to seven calendar days including today. For
24 November 2026, this means 18–24 November inclusive. A successful dashboard
login resets date and operator selections. Token refresh does not reset them.
The previous default was month-to-date. Dates follow the dashboard browser's
local calendar, consistent with the existing date controls.

The Inspections page has an **Inspection type** dropdown with All, External,
Internal, Driver, Passenger Count, and Schedule Check. Choosing a type includes
both compliant records and violations. Clicking a summary tile selects that
type's violations only. Changing the dropdown clears the violation-only filter.

User-facing inspection status labels now use **Violation** / **Inspection
Violations**. Existing API field names such as `failed_inspection_count`, drill
keys, and stored boolean columns remain unchanged for compatibility. Counts
remain event counts, not counts of individual failed checklist questions.

## Passenger capacities and overloading

Overloading is assessed by our backend from the counts submitted by the mobile
app. The previous dashboard rule incorrectly classified any standing passenger
as overload. We cannot establish what additional local calculations the external
mobile application performs from this repository.

| Fleet series | Seated limit | Standing limit | Combined capacity |
|---|---:|---:|---:|
| 3000–3999 | 65 | 12 | 77 |
| 4000–4999 | 114 | 32 | 146 |
| 5000–5999 | 79 | 24 | 103 |
| 7000–7999 | 49 | 12 | 61 |

The owner confirmed that seating and standing limits must be checked separately:

- Violation if `number_seated > seating_capacity` **or**
  `number_standing > standing_capacity`.
- Exactly at either limit is permitted.
- Passengers over capacity = positive seating excess + positive standing excess.
- Example: a 3002 bus with 66 seated and 0 standing is a violation (one excess
  seated passenger), even though its total is less than 77.
- Fleet numbers must be four digits in a known series (surrounding whitespace is
  ignored). Unknown fleet series or missing counts return a null assessment,
  displayed as unknown/not assessed; they are not counted as confirmed violations.

The central rules are in `app/services/passenger_capacity.py`. They apply to new
passenger-count submissions, grouped inspection reads, reporting, analytics,
monitor/shift summaries, and vehicle inspection status. Vehicle responses expose
`seating_capacity` and `standing_capacity`, calculated from their fleet number;
the dashboard vehicle details display them. Passenger-count read responses also
expose `overloaded_passengers` and the assessed `pass_` value.

Historical passenger counts are reassessed when read using the same rules.
Their recorded counts and original stored pass flags are not rewritten, so
historical dashboard totals will change to correct the old standing-passenger
proxy. No mobile update is needed for this correction: continue sending the
existing `number_seated` and `number_standing` fields and the correct bus fleet
number in `bus_number`.

## Departure times: what was collected previously?

Before this change, schedule inspections contained `inspection_time`, a lateness
band, and the bus duty number. There was no explicit actual departure datetime
or link to the chosen timetable departure. An inspection timestamp is not proof
of departure. A duty number alone is insufficient to pick a scheduled departure:
there can be several timetable rows for one duty.

Old records therefore show **Not captured** for scheduled and actual departure.
No times are guessed from the inspection timestamp or the lateness band.

## Mobile change required to capture departures

Inside the existing `busses[].inspections.behind_schedule_reports[]` object, the
app may now send these optional fields:

| Field | Meaning |
|---|---|
| `departure_uid` | The exact row's `uid` from the locally cached departures CSV. This is NOT the CSV's `schedule_uid`. |
| `actual_departure_time` | The observed departure datetime, using the same local capture-time convention as the other shift timestamps. Omit or send null if not observed. |

Example schedule report (not the full shift request):

```json
{
  "internal_inspection_id": "schedule-20261124-001",
  "inspection_time": "2026-11-24T08:15:00",
  "inspection_lat": -29.1187,
  "inspection_lon": 26.2145,
  "behind_schedule_interval": "6-15 mins late",
  "departure_uid": "<uid from the selected CSV departure row>",
  "actual_departure_time": "2026-11-24T08:10:00"
}
```

Replace the UID placeholder with the real UUID. Keep the existing bus-level
`duty_number` aligned with the chosen row's `duty_no`. The backend validates that
the departure exists and belongs to that duty, otherwise returning HTTP 422.
A valid older CSV row is accepted: historical schedules are retained for offline
uploads. Do not replace the captured UID with one from a newer download.

The backend copies the selected row's scheduled time into
`scheduled_departure_time` on the inspection. This preserves the captured
schedule alongside `departure_uid` and `actual_departure_time`. Both JSON and
the existing multipart metadata contract accept the new optional input fields.
The existing lateness-band field is unchanged; it is not recalculated from these
times. The external mobile developer must update the capture UI and submission
payload before actual observations can appear.

Grouped inspection responses expose all three fields. Schedule inspection
summaries/details in Inspections, Shifts, and Monitors display scheduled and
actual times, as do the reporting schedule drilldowns. The scheduled time is a
local time-of-day; the actual value includes the capture date.

## Deployment

The additive migration `scripts/20261124_inspection_departures.sql` was applied
to Cloud SQL on 24 November 2026. It adds nullable fields and a foreign key to
historical timetable rows; it does not backfill old observations.

Deploy the backend and dashboard changes before David releases the departure
capture fields. The old backend would ignore these unknown request fields.
Existing mobile payloads remain valid. Dashboard code and the mobile capture
change are not automatically deployed by applying the database migration.
