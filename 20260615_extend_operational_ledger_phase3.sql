-- Migration: Phase 3 — the Probabilistic Dispatch-Decision Platform.
-- Fixes the ground-truth data flaw: a single "collected" timestamp cannot
-- separate passenger readiness from driver tardiness. We capture the driver's
-- geofence arrival and the passenger-met moment independently, plus predicted
-- vs. actual touchdown, and track both wait metrics.

ALTER TABLE operational_ledger
  ADD COLUMN IF NOT EXISTS target_fbo text,
  ADD COLUMN IF NOT EXISTS aircraft_category text,
  ADD COLUMN IF NOT EXISTS predicted_touchdown_time timestamptz,
  ADD COLUMN IF NOT EXISTS actual_touchdown_time timestamptz,            -- auto-captured (ADS-B; simulated)
  ADD COLUMN IF NOT EXISTS driver_geofence_arrival_time timestamptz,     -- simulated geofence auto-capture
  ADD COLUMN IF NOT EXISTS actual_passenger_met_time timestamptz,        -- manual ("Passenger Met")
  ADD COLUMN IF NOT EXISTS late_pickup_minutes integer;

CREATE INDEX IF NOT EXISTS operational_ledger_target_fbo_idx ON operational_ledger (target_fbo);
CREATE INDEX IF NOT EXISTS operational_ledger_aircraft_category_idx ON operational_ledger (aircraft_category);
