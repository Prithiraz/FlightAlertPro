/*
  # Add last_triggered_price to price_alerts
  
  1. Changes
    - Add `last_triggered_price` column to track the last price that triggered a notification
    - This enables deduplication to avoid spamming users with alerts for the same price
  
  2. Notes
    - Column is nullable - NULL means alert has never been triggered
    - When alert triggers, this field is updated with the current lowest price
    - Next trigger only happens if new price is lower than this value
*/

-- Add last_triggered_price column if not exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'price_alerts' AND column_name = 'last_triggered_price'
  ) THEN
    ALTER TABLE price_alerts ADD COLUMN last_triggered_price numeric(10,2);
  END IF;
END $$;
