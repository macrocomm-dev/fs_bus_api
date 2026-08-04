# Vehicle And Monitor Drilldowns Flow

## Vehicle Detail

The per-vehicle route is `/vehicles/:vehicleKey` in the Angular app and
`GET /vehicle/vehicle-detail/{vehicle_key}` in the API.

The API resolves `vehicle_key` against the master vehicle table using VIN,
registration number, fleet number, and normalized chart/table labels. The same
detail payload then supplies:

- master vehicle identity and operator details;
- Smart Fleet last address, last ping, and matched device ID;
- latest inspection time/type/result;
- recent analytics trips;
- real analytics events;
- score-per-trip points;
- inspection history;
- data quality flags/counts for each source.

## Event Matching

`analytics.events` now carries VIN values in `vin_no`. Vehicle detail event rows
match on both:

- Smart Fleet style `vehiclereg` labels; and
- normalized `vin_no`.

This is important because `analytics.trip_data` stores vehicle labels like
`REGISTRATION - FLEET`, while events can now be resolved cleanly through VIN.

## High Risk Trips

High risk trips are no longer derived from `analytics.trip_data.riskfactor`.

For v1, a high risk trip means:

```text
3 or more real analytics.events rows occurred within that trip's start/end time
window for the same vehicle.
```

The API joins events to trips by:

1. matching `analytics.events.vin_no` to `master_data.vehicle.vin`;
2. matching the resulting registration/fleet values to the trip label; and
3. counting events where `event_date` falls between `tripstart` and `tripend`.

This rule is used by:

- vehicle detail recent trips (`event_count`, `high_risk`);
- analytics metric tile for high risk trips;
- analytics vehicle performance high risk trip counts.

If future feeds add a direct trip ID to `analytics.events`, the join should move
to that direct key.

## Monitor View

The Angular route `/monitors` shows monitor productivity from existing live
data. It currently uses:

- `GET /shift/shifts` for shift rows;
- `GET /inspection/bus_inspections/by_shift_ids` for linked inspection rows.

The shift API now exposes `user_id` alongside monitor name/surname so the UI can
select a stable monitor key. The page shows:

- selected monitor dropdown;
- shift count;
- linked inspection count;
- failed inspection count;
- distinct buses inspected;
- shifts vs inspections chart;
- expandable shift table;
- inspection table for the selected monitor.

This view reuses the same inspection flattening approach as the Shifts page, so
inspection counts remain consistent across both screens.
