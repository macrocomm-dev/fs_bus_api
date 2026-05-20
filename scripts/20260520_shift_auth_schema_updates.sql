-- Apply before deploying the API changes that depend on these columns.
-- Target database: PostgreSQL

BEGIN;

ALTER TABLE inspections.inspections
    ADD COLUMN IF NOT EXISTS fire_extinguisher_present boolean;

ALTER TABLE app_auth.app_user
    ADD COLUMN IF NOT EXISTS name varchar,
    ADD COLUMN IF NOT EXISTS surname varchar;

UPDATE app_auth.app_user
SET
    name = COALESCE(
        name,
        NULLIF(split_part(trim(full_name), ' ', 1), '')
    ),
    surname = COALESCE(
        surname,
        NULLIF(
            regexp_replace(trim(full_name), '^[^ ]+\s*', ''),
            ''
        )
    )
WHERE full_name IS NOT NULL;

UPDATE inspections.inspections
SET inspection_type = 'behind_schedule'
WHERE inspection_type = 'technical'
  AND behind_schedule_interval IS NOT NULL;

COMMIT;
