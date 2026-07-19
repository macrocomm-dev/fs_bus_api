# Analytics And Reports Data Notes

## Analytics Hooked Up Now

The Analytics page now uses `GET /analytics/summary` instead of hardcoded dummy rows.

Current backend sources:

- `analytics.bi_data`
  - Used for the gauge row:
    - Speeding: `bi_speed`
    - Cornering: `bi_cornering`
    - Acceleration: `bi_acceleration`
    - Braking: `bi_deceleration`
  - Used for vehicle behaviour scores:
    - Bottom graph score: latest `bi_total` per vehicle
    - Vehicle performance score: latest `bi_total` per vehicle
- `analytics.trip_data`
  - Used for the second KPI row:
    - Trip duration: sum of `tripdur`
    - Speed duration: sum of `speeddur`
    - Excess idle duration: sum of `excess_idle_seconds`
    - High risk trips: count of trips where `riskfactor > 0`
  - Used for the vehicle performance table:
    - Vehicle registration/fleet number: parsed from `vehiclereg`
    - Operator: mapped from `vehiclegroup`
    - Distance: sum of `distance`
    - Trip duration: sum of `tripdur`
    - Speed duration: sum of `speeddur`
    - Idle duration: sum of `excess_idle_seconds`
    - High risk trips: count of `riskfactor > 0`
- `analytics.events`
  - Endpoint supports it for Last Events, but the table currently has `0` rows.

Current row counts found during inspection:

- `analytics.trip_data`: `24,947`
- `analytics.bi_data`: `2,393`
- `analytics.events`: `0`
- `master_data.vehicle`: `274`
- `shifts.shifts`: `48` after old-data cleanup
- `inspections.inspections`: `720` after old-data cleanup

Operator mapping currently used by the Analytics endpoint:

- `INTERSTATE` -> `Interstate Bus Lines`
- `MALUTI` -> `Maluti Bus Services`

## Analytics Not Fully Hooked Yet

These Analytics items cannot be fully real yet from the inspected data:

- Last Events table
  - Blocked because `analytics.events` is empty.
  - The table shape is available and the endpoint will return rows if this table is populated.
- Accidents KPI
  - Currently returns `0`.
  - Blocked because no inspected table has an explicit accident count/type field.
  - `analytics.events` has `event_id`, but there is no event-type mapping table or known accident `event_id`.
- High risk trips
  - Hooked technically, but current `analytics.trip_data.riskfactor` is `0.00` for every row, so it returns `0`.
- Speed duration and excess idle duration
  - Hooked technically, but current values are all zero in the inspected data.
- Route compliance in Analytics
  - `analytics.trip_data` has `routescore` and `routevar`, but the current Analytics page does not display route compliance.
  - If added later, we need to confirm whether `routescore = 0` means non-compliance, missing calculation, or unavailable route matching.

## Reports Page Hooked Up Now

The Reporting dashboard now uses `GET /analytics/reporting-summary` for dashboard cards, expanded card breakdowns, drilldown modal tables, and available trend charts. The old hardcoded report rows are no longer used as the active data source; static frontend tile definitions only remain as loading/order shells while the API request is in flight.

Current backend sources:

- Top row: Overall Operator Compliance
  - On Time Performance:
    - Source: `shifts.shifts` plus `inspections.inspections`
    - Current calculation: shifts with no `behind_schedule` inspection report divided by total shifts in the selected date range.
  - Route Compliance:
    - Source checked: `analytics.trip_data.routescore` and `analytics.trip_data.routevar`
    - Current display: `N/A` because both fields are currently `0.00` for all inspected rows, so a percentage would be misleading.
  - Failed Inspections:
    - Source: `inspections.inspections`
    - Current calculation: `pass = false` divided by total inspections in the selected date range.
  - Fleet Health:
    - Source: latest `analytics.bi_data.bi_total` per vehicle in the selected date range.
- Daily Bus Monitoring
  - Source: `inspections.inspections`
  - Group by `inspection_type`.
  - Drilldowns return real inspection rows for external, internal, driver, passenger count, and technical inspections.
  - Inspection type over time uses real daily inspection counts.
- Failed Inspections
  - Source: `inspections.inspections`
  - Group failed rows by `inspection_type`.
  - Passenger count failures currently use `number_standing > 0` as a provisional overloaded-trip proxy.
- Defects / Bus Defects
  - Source: `inspections.inspections`
  - Fields available include:
    - `tyres_pass`
    - `windows_pass`
    - `ext_other_pass`
    - `fire_extinguisher_present`
    - `seats_pass`
    - `aisle_pass`
    - `int_other_pass`
    - `license_disk_scan_succeeded`
    - `destination_displayed`
    - `prdp_scan_succeeded`
    - `driver_identified`
  - Drilldowns return rows for failed fire-extinguisher, seats, aisle, tyres, windows, other, and technical checks.
- Delayed departures / route starts
  - Source: `inspections.inspections`
  - Use `inspection_type = 'behind_schedule'` and group by `behind_schedule_interval`.
  - Drilldowns return the real rows per delay bucket:
    - `0-5 mins`
    - `5-10 mins`
    - `10-15 mins`
    - `15+ mins`
- Shifts per operator
  - Source: `shifts.shifts` joined to `app_auth.app_user` and `master_data.operator`.
  - Used in the operator compliance drilldown.
- Inspections passed/failed per operator
  - Source: `inspections.inspections` joined to `master_data.vehicle`.
  - Match candidates: `bus_id`, `fleet_number`, vehicle `vin`, `registration_number`, `fleet_number`.
  - Used in the operator compliance drilldown.
- Fleet health bucket graph
  - Source: `analytics.bi_data`
  - Uses latest `bi_total` per vehicle and buckets by `<50`, `50+`, `80+`, `95+`.
- Route deviations
  - Source: `analytics.trip_data.routevar`.
  - Current query returns trips with `routevar > 0`, including `routescore`, start location, and vehicle/operator details.
- Bus licence disk scan count
  - Source: `inspections.inspections.license_disk_scan_succeeded`.
  - Current implementation counts rows where this field is `false` as failed bus licence disk scans.

## Reports Data Still Blocked Or Needs Confirmation

- On-time performance
  - Hooked with the provisional definition above.
  - Need confirmation: should the denominator be all monitor shifts, scheduled route starts, actual departures, or inspected buses?
- Route compliance
  - Partially hooked for route deviations from `analytics.trip_data.routevar`.
  - Blocked for missed stops because no actual stop-arrival / stop-missed table exists.
  - Need confirmation: whether `routescore = 0` means non-compliance or unavailable route matching.
  - Need confirmation: whether route compliance should be trip-weighted, route-weighted, or operator-weighted.
- Passenger overloaded trips
  - Partially hooked from passenger count rows.
  - Current provisional rule: rows with standing passengers are treated as overloaded.
  - Need bus seating/standing capacity per vehicle or route to calculate true overload percentage.
- Bus license disk count
  - Partially hooked from `license_disk_scan_succeeded`.
  - Need definition: should the card show successful scans, failed scans, missing disks, or total licence disk checks?
- Operator compliance score
  - Drilldown counts are hooked.
  - Overall percentage currently remains `N/A`.
  - Need scoring formula for converting shifts, inspection pass/fail counts, delayed starts, route deviations, and compliance checks into one operator compliance percentage.
- Fleet health by operator
  - Overall fleet health bucket counts are hooked from `analytics.bi_data`.
  - Operator split is not shown on the Reporting page chart yet because `analytics.bi_data` does not carry operator and would require a reliable vehicle-to-operator join key for every `vehiclereg`.
- Driver licence expiry
  - Not hookable from inspected DB.
  - No driver licence expiry table/field was found.
- Route licence expiry
  - Not hookable from inspected DB.
  - No route licence expiry table/field was found.
- Accidents
  - Not hookable from inspected DB.
  - No accident table or accident event mapping found.
- Last analytics events
  - Reporting page does not currently display this, but Analytics does.
  - `analytics.events` exists but has no rows.
- Missed stops
  - Not hookable from inspected DB.
  - No actual stop arrival / stop missed table found.
- Depot-specific route compliance
  - Not hookable from inspected DB.
  - Routes and stops exist, but no depot field or route execution table was found during this inspection.
- Roadworthiness failures
  - Product owner previously requested removal.
  - No current Reporting card depends on this as a standalone metric.

## Cleanup Already Done

Rows before `2026-07-01 00:00:00` were cleared from the shift workflow tables:

- Deleted `133` old shifts.
- Deleted `164` old inspection rows.
- Deleted `25` linked inspection photos.
- Deleted `51` linked shift selfies.
- Verified remaining old shifts: `0`.
- Verified remaining old inspections: `0`.
