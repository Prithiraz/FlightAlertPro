-- Run this exact block in your Supabase SQL Editor to support the new timestamps
ALTER TABLE operational_ledger ADD COLUMN IF NOT EXISTS driver_in_position_at timestamptz;
ALTER TABLE operational_ledger ADD COLUMN IF NOT EXISTS passenger_met_at timestamptz;
ALTER TABLE operational_ledger ADD COLUMN IF NOT EXISTS vehicle_departed_at timestamptz;
