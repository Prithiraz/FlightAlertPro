/*
  # Add Smart Profile preferences to user_profiles

  ## Changes

  ### user_profiles table
  - Add `home_airport` (text) – user's default home airport IATA code
  - Add `default_cabin` (text) – preferred cabin class with CHECK constraint
    ('economy', 'premium_economy', 'business', 'first'). Defaults to 'economy'.

  Note: `preferred_currency` already exists and will be used for currency preference.
*/

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user_profiles' AND column_name = 'home_airport'
  ) THEN
    ALTER TABLE user_profiles ADD COLUMN home_airport text DEFAULT NULL;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user_profiles' AND column_name = 'default_cabin'
  ) THEN
    ALTER TABLE user_profiles
      ADD COLUMN default_cabin text NOT NULL DEFAULT 'economy'
        CHECK (default_cabin IN ('economy', 'premium_economy', 'business', 'first'));
  END IF;
END $$;
