CREATE TABLE IF NOT EXISTS operational_ledger (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Flight identity
  flight_id TEXT NOT NULL,
  target_fbo TEXT,
  aircraft_category TEXT CHECK (aircraft_category IN ('narrow_body', 'wide_body', 'regional', 'private')),

  -- Probabilistic prediction chain outputs (written by physics_engine.py)
  predicted_touchdown_time TIMESTAMPTZ,
  predicted_on_block_time TIMESTAMPTZ,
  predicted_passenger_ready_time TIMESTAMPTZ,
  dispatch_window_start TIMESTAMPTZ,
  dispatch_window_end TIMESTAMPTZ,
  recommendation_confidence TEXT CHECK (recommendation_confidence IN ('High', 'Moderate', 'Low')),
  expected_driver_wait_minutes NUMERIC(5,2),

  -- Ground truth capture (auto + manual)
  actual_touchdown_time TIMESTAMPTZ,           -- auto-captured via ADS-B geofence trigger
  driver_geofence_arrival_time TIMESTAMPTZ,    -- simulated auto-capture when driver taps "In Position"
  actual_passenger_met_time TIMESTAMPTZ,       -- manual: driver taps "Passenger Met"

  -- Derived metrics (computed on write)
  driver_wait_minutes NUMERIC(5,2)
    GENERATED ALWAYS AS (
      EXTRACT(EPOCH FROM (actual_passenger_met_time - driver_geofence_arrival_time)) / 60.0
    ) STORED,
  late_pickup_minutes NUMERIC(5,2)
    GENERATED ALWAYS AS (
      GREATEST(0, EXTRACT(EPOCH FROM (actual_passenger_met_time - predicted_passenger_ready_time)) / 60.0)
    ) STORED,

  -- Metadata
  dispatcher_user_email TEXT,
  driver_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE operational_ledger ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Dispatchers manage own ledger entries"
  ON operational_ledger FOR ALL TO authenticated
  USING (dispatcher_user_email = auth.jwt()->>'email')
  WITH CHECK (dispatcher_user_email = auth.jwt()->>'email');

CREATE INDEX IF NOT EXISTS ol_flight_id_idx ON operational_ledger (flight_id);
CREATE INDEX IF NOT EXISTS ol_dispatcher_idx ON operational_ledger (dispatcher_user_email);
CREATE INDEX IF NOT EXISTS ol_created_at_idx ON operational_ledger (created_at DESC);
