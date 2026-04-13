/*
  # Add subscription_tier column for 3-tier subscription model

  ## Changes

  ### user_profiles table
  - Add `subscription_tier` (text) with CHECK constraint for valid values:
    'free', 'pro', 'elite', 'business'. Defaults to 'free'.
  - Migrate existing `is_pro = true` rows to `subscription_tier = 'pro'`
    (using the existing `plan` column for more granular tiers where available).
  - Drop the `is_pro` column after migration.

  ### users table (mirror)
  - Same migration: add `subscription_tier`, migrate from `is_pro`, drop `is_pro`.
*/

DO $$
BEGIN
  -- ----------------------------------------------------------------
  -- user_profiles: add subscription_tier
  -- ----------------------------------------------------------------
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user_profiles' AND column_name = 'subscription_tier'
  ) THEN
    ALTER TABLE user_profiles
      ADD COLUMN subscription_tier text NOT NULL DEFAULT 'free'
        CHECK (subscription_tier IN ('free', 'pro', 'elite', 'business'));
  END IF;

  -- Migrate data: use existing `plan` column if it holds a valid tier,
  -- otherwise fall back to 'pro' for rows that were previously is_pro=true.
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user_profiles' AND column_name = 'is_pro'
  ) THEN
    UPDATE user_profiles
    SET subscription_tier = CASE
      WHEN plan IN ('pro', 'elite', 'business') THEN plan
      WHEN is_pro = true THEN 'pro'
      ELSE 'free'
    END
    WHERE subscription_tier = 'free';  -- only migrate rows not yet set

    ALTER TABLE user_profiles DROP COLUMN IF EXISTS is_pro;
  END IF;

  -- ----------------------------------------------------------------
  -- users table: add subscription_tier (mirror)
  -- ----------------------------------------------------------------
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_name = 'users'
  ) THEN
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name = 'users' AND column_name = 'subscription_tier'
    ) THEN
      ALTER TABLE users
        ADD COLUMN subscription_tier text NOT NULL DEFAULT 'free'
          CHECK (subscription_tier IN ('free', 'pro', 'elite', 'business'));
    END IF;

    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name = 'users' AND column_name = 'is_pro'
    ) THEN
      UPDATE users
      SET subscription_tier = CASE
        WHEN is_pro = true THEN 'pro'
        ELSE 'free'
      END
      WHERE subscription_tier = 'free';

      ALTER TABLE users DROP COLUMN IF EXISTS is_pro;
    END IF;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_user_profiles_subscription_tier
  ON user_profiles(subscription_tier);
