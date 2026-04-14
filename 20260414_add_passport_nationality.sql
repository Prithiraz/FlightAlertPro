-- Migration: Add passport_nationality to user_profiles
-- This enables the Destination Hub to provide personalised visa intelligence.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user_profiles' AND column_name = 'passport_nationality'
  ) THEN
    ALTER TABLE user_profiles ADD COLUMN passport_nationality text DEFAULT NULL;
  END IF;
END $$;
