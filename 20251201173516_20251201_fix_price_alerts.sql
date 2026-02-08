/*
  # Fix Price Alerts Schema

  1. Changes
    - Add `active` column if not exists (standardize naming from is_active)
    - Add `phone` column for SMS/WhatsApp alerts
    - Add `currency` column to store alert price currency
    - Add `triggered_at` timestamp for tracking when alert fired

  2. Security
    - RLS already enabled, no changes needed
*/

-- Add columns if not exist
DO $$
BEGIN
  -- Add active column (rename from is_active for consistency)
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'price_alerts' AND column_name = 'active'
  ) THEN
    ALTER TABLE price_alerts ADD COLUMN active boolean DEFAULT true;

    -- Copy is_active to active if is_active exists
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name = 'price_alerts' AND column_name = 'is_active'
    ) THEN
      UPDATE price_alerts SET active = is_active;
    END IF;
  END IF;

  -- Add phone column
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'price_alerts' AND column_name = 'phone'
  ) THEN
    ALTER TABLE price_alerts ADD COLUMN phone text;
  END IF;

  -- Add currency column
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'price_alerts' AND column_name = 'currency'
  ) THEN
    ALTER TABLE price_alerts ADD COLUMN currency text DEFAULT 'USD';
  END IF;

  -- Add triggered_at column
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'price_alerts' AND column_name = 'triggered_at'
  ) THEN
    ALTER TABLE price_alerts ADD COLUMN triggered_at timestamptz;
  END IF;
END $$;

-- Create index on active status for faster queries
CREATE INDEX IF NOT EXISTS idx_price_alerts_active ON price_alerts(active) WHERE active = true;