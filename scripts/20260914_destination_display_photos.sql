-- Apply before deploying destination-display photo uploads/readback.
-- Additive: existing inspections and their event counts are unchanged.
BEGIN;
CREATE TABLE IF NOT EXISTS photos.destination_display (
    id bigserial PRIMARY KEY,
    shift_id bigint NOT NULL REFERENCES shifts.shifts(id),
    user_id varchar NOT NULL,
    bus_id varchar NOT NULL,
    fleet_number varchar NOT NULL,
    duty_number varchar NOT NULL,
    replacement_bus boolean NOT NULL,
    license_disk_scan_succeeded boolean,
    destination_displayed boolean,
    timestamp timestamp without time zone NOT NULL,
    lat double precision NOT NULL,
    lon double precision NOT NULL,
    photo text NOT NULL,
    created_at timestamp without time zone NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_destination_display_bus_group
    ON photos.destination_display (shift_id, bus_id, duty_number, replacement_bus);
COMMIT;
