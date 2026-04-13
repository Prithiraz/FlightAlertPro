-- Migration: Add flexible date range support to price_alerts
-- Adds departure_start_date and departure_end_date columns.
-- departure_date is kept for backward compatibility (nullable, no longer required).

ALTER TABLE price_alerts
  ADD COLUMN IF NOT EXISTS departure_start_date DATE,
  ADD COLUMN IF NOT EXISTS departure_end_date   DATE;

-- Back-fill existing rows: if departure_date is set, use it for both start and end.
UPDATE price_alerts
SET
  departure_start_date = departure_date::DATE,
  departure_end_date   = departure_date::DATE
WHERE departure_date IS NOT NULL
  AND departure_start_date IS NULL;

-- Optional index to speed up worker queries on date range alerts.
CREATE INDEX IF NOT EXISTS idx_price_alerts_start_date
  ON price_alerts (departure_start_date);
