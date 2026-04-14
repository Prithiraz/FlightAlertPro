-- Migration: Add client columns to price_alerts and create flight_delays table
-- Supports the Business Tier Travel Agent Portal and EU261 Auto-Claim Engine

-- 1. Add client fields to price_alerts (for Business tier Travel Agent Portal)
ALTER TABLE price_alerts
  ADD COLUMN IF NOT EXISTS client_name TEXT,
  ADD COLUMN IF NOT EXISTS client_email TEXT;

-- 2. Create flight_delays table (for Elite tier EU261 Auto-Claim Engine)
CREATE TABLE IF NOT EXISTS flight_delays (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  flight_id TEXT NOT NULL,
  delay_minutes INTEGER NOT NULL DEFAULT 0,
  eu261_eligible BOOLEAN NOT NULL DEFAULT FALSE,
  user_email TEXT,
  alert_id UUID REFERENCES price_alerts(id) ON DELETE SET NULL,
  departure_airport TEXT,
  arrival_airport TEXT,
  scheduled_departure TIMESTAMPTZ,
  actual_departure TIMESTAMPTZ,
  airline_iata TEXT,
  compensation_amount INTEGER,
  claim_sent_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for quick lookups by flight and user
CREATE INDEX IF NOT EXISTS flight_delays_flight_id_idx ON flight_delays (flight_id);
CREATE INDEX IF NOT EXISTS flight_delays_user_email_idx ON flight_delays (user_email);
