/*
  # Add referral system columns

  ## Changes

  ### user_profiles table
  - Add `referral_code` (text, unique) – a short unique code assigned at registration (e.g. FLIGHT-X7B9).
  - Add `referred_by`  (text, nullable) – stores the referral_code of the user who referred this account.
  - Add `elite_until`  (timestamptz, nullable) – if set and in the future, the user receives temporary Elite access.

  ### users table (mirror, if it exists)
  - Same three columns added.
*/

DO $$
BEGIN
  -- ----------------------------------------------------------------
  -- user_profiles: add referral columns
  -- ----------------------------------------------------------------
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user_profiles' AND column_name = 'referral_code'
  ) THEN
    ALTER TABLE user_profiles ADD COLUMN referral_code text UNIQUE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user_profiles' AND column_name = 'referred_by'
  ) THEN
    ALTER TABLE user_profiles ADD COLUMN referred_by text;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user_profiles' AND column_name = 'elite_until'
  ) THEN
    ALTER TABLE user_profiles ADD COLUMN elite_until timestamptz;
  END IF;

  -- ----------------------------------------------------------------
  -- users table: same columns (mirror)
  -- ----------------------------------------------------------------
  IF EXISTS (
    SELECT 1 FROM information_schema.tables WHERE table_name = 'users'
  ) THEN
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name = 'users' AND column_name = 'referral_code'
    ) THEN
      ALTER TABLE users ADD COLUMN referral_code text UNIQUE;
    END IF;

    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name = 'users' AND column_name = 'referred_by'
    ) THEN
      ALTER TABLE users ADD COLUMN referred_by text;
    END IF;

    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name = 'users' AND column_name = 'elite_until'
    ) THEN
      ALTER TABLE users ADD COLUMN elite_until timestamptz;
    END IF;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_user_profiles_referral_code ON user_profiles(referral_code);
