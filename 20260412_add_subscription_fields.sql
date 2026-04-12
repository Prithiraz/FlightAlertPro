/*
  # Add subscription fields for Stripe integration

  ## Changes

  ### user_profiles table
  - `is_pro` (boolean) - Whether the user has an active Pro (or higher) subscription
  - `stripe_customer_id` (text) - Stripe customer ID
  - `subscription_status` (text) - Stripe subscription status (e.g. active, canceled)
  - `plan` (text) - Purchased plan name (free, pro, elite, business)
  - `subscription_id` (text) - Stripe subscription ID

  ### users table
  - `is_pro` (boolean) - Mirror of user_profiles.is_pro for fast queries
  - `stripe_customer_id` (text) - Stripe customer ID
  - `subscription_status` (text) - Stripe subscription status

  ## Notes
  - A service-role RLS bypass policy is NOT required; the service role key
    bypasses RLS automatically in Supabase.
*/

DO $$
BEGIN
  -- user_profiles: is_pro
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user_profiles' AND column_name = 'is_pro'
  ) THEN
    ALTER TABLE user_profiles ADD COLUMN is_pro boolean DEFAULT false;
  END IF;

  -- user_profiles: stripe_customer_id
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user_profiles' AND column_name = 'stripe_customer_id'
  ) THEN
    ALTER TABLE user_profiles ADD COLUMN stripe_customer_id text;
  END IF;

  -- user_profiles: subscription_status
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user_profiles' AND column_name = 'subscription_status'
  ) THEN
    ALTER TABLE user_profiles ADD COLUMN subscription_status text;
  END IF;

  -- user_profiles: plan
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user_profiles' AND column_name = 'plan'
  ) THEN
    ALTER TABLE user_profiles ADD COLUMN plan text DEFAULT 'free';
  END IF;

  -- user_profiles: subscription_id
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user_profiles' AND column_name = 'subscription_id'
  ) THEN
    ALTER TABLE user_profiles ADD COLUMN subscription_id text;
  END IF;

  -- users: is_pro
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'users' AND column_name = 'is_pro'
  ) THEN
    ALTER TABLE users ADD COLUMN is_pro boolean DEFAULT false;
  END IF;

  -- users: stripe_customer_id
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'users' AND column_name = 'stripe_customer_id'
  ) THEN
    ALTER TABLE users ADD COLUMN stripe_customer_id text;
  END IF;

  -- users: subscription_status
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'users' AND column_name = 'subscription_status'
  ) THEN
    ALTER TABLE users ADD COLUMN subscription_status text;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_user_profiles_is_pro ON user_profiles(is_pro) WHERE is_pro = true;
CREATE INDEX IF NOT EXISTS idx_user_profiles_stripe_customer ON user_profiles(stripe_customer_id);
