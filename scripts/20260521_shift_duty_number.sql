BEGIN;

ALTER TABLE inspections.inspections
    ADD COLUMN IF NOT EXISTS duty_number varchar,
    ADD COLUMN IF NOT EXISTS replacement_bus boolean NOT NULL DEFAULT false;

COMMIT;