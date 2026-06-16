-- Migration: Operational Ledger for the driver-dispatch feedback loop.
-- Captures ground-truth driver milestones (FBO arrival, passenger exit,
-- passenger collected) against each flight's ORIGINAL Predicted On-Block Time,
-- plus the resulting Driver_Wait_Minutes delta. This proprietary dataset powers
-- future FBO-specific micro-models.

CREATE TABLE IF NOT EXISTS operational_ledger (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  flight_id text NOT NULL,
  flight_number text,
  passenger_name text,
  fbo text,
  predicted_obt timestamptz,
  arrived_at_fbo_at timestamptz,
  passenger_exited_at timestamptz,
  passenger_collected_at timestamptz,
  driver_wait_minutes integer,
  status text NOT NULL DEFAULT 'in_progress',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Indexes for driver lookups, per-FBO aggregation, and active-trip filtering.
CREATE INDEX IF NOT EXISTS operational_ledger_flight_id_idx ON operational_ledger (flight_id);
CREATE INDEX IF NOT EXISTS operational_ledger_fbo_idx ON operational_ledger (fbo);
CREATE INDEX IF NOT EXISTS operational_ledger_status_idx ON operational_ledger (status);
