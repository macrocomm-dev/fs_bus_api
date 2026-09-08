-- Versioned timetable snapshots. Apply before deploying the CSV endpoint.
BEGIN;

CREATE SCHEMA IF NOT EXISTS routes;

CREATE TABLE IF NOT EXISTS routes.schedule_version (
    uid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id bigint NOT NULL REFERENCES master_data.operator(operator_id),
    source_name text NOT NULL,
    content_sha256 varchar(64) NOT NULL,
    row_count integer NOT NULL CHECK (row_count > 0),
    published_at timestamptz NOT NULL DEFAULT now(),
    is_active boolean NOT NULL DEFAULT false
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_schedule_version_active_operator
    ON routes.schedule_version(operator_id) WHERE is_active;

CREATE TABLE IF NOT EXISTS routes.departure (
    uid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_uid uuid NOT NULL REFERENCES routes.schedule_version(uid),
    duty_no text NOT NULL CHECK (length(btrim(duty_no)) > 0),
    departure time(0) without time zone NOT NULL,
    origin text NOT NULL CHECK (length(btrim(origin)) > 0),
    destination text NOT NULL CHECK (length(btrim(destination)) > 0),
    direction text NOT NULL CHECK (length(btrim(direction)) > 0),
    valid_days text NOT NULL CHECK (length(btrim(valid_days)) > 0),
    bus_type text NOT NULL CHECK (length(btrim(bus_type)) > 0),
    CONSTRAINT uq_departure_schedule_row UNIQUE
        (schedule_uid, duty_no, departure, origin, destination, direction, valid_days, bus_type)
);

COMMIT;
