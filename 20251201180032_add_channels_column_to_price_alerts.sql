/*
  # Add channels column to price_alerts
  
  1. Changes
    - Add `channels` column as alias/copy of notification_channels for backward compatibility
    - Ensure both columns stay in sync
  
  2. Notes
    - Some API code references 'channels' instead of 'notification_channels'
    - This migration adds the missing column
*/

-- Add channels column if not exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'price_alerts' AND column_name = 'channels'
  ) THEN
    ALTER TABLE price_alerts ADD COLUMN channels text[] DEFAULT ARRAY['email']::text[];
    
    -- Copy notification_channels to channels if data exists
    UPDATE price_alerts SET channels = notification_channels WHERE notification_channels IS NOT NULL;
  END IF;
END $$;
