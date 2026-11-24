-- Add optional links to the exact cached timetable departure and observed time.
-- Existing inspection times are not reinterpreted as actual departure times.
BEGIN;
ALTER TABLE inspections.inspections
    ADD COLUMN IF NOT EXISTS departure_uid uuid REFERENCES routes.departure(uid),
    ADD COLUMN IF NOT EXISTS scheduled_departure_time time without time zone,
    ADD COLUMN IF NOT EXISTS actual_departure_time timestamp without time zone;
COMMIT;
