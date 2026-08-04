-- Allow audit.api_error_log to store successful request audit rows.
--
-- This table started as an error log, so the original status-code constraint
-- only allowed 4xx/5xx responses. We now also use it to audit accepted shift
-- payloads and normalized payloads, which use 201.

ALTER TABLE audit.api_error_log
    DROP CONSTRAINT IF EXISTS ck_api_error_log_status_code;

ALTER TABLE audit.api_error_log
    ADD CONSTRAINT ck_api_error_log_status_code
    CHECK (status_code BETWEEN 100 AND 599);
