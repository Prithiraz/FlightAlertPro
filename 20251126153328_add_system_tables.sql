/*
  # Add System Tables for Flight Alert Pro

  ## New Columns Added to Existing Tables
  
  ### users table
  - `phone` (text) - WhatsApp phone number
  - `telegram_chat_id` (text) - Telegram chat ID
  - `plan` (text) - Subscription plan
  - `subscription_id` (text) - Stripe subscription ID
  - `subscription_expires_at` (timestamptz) - Expiry date
  - `api_calls_count` (int) - API usage counter
  - `notification_credits` (int) - Available notification credits

  ## New Tables
  
  ### 1. notification_log
  - Tracks all sent notifications
  - Records provider message IDs and status
  
  ### 2. payments
  - Tracks Stripe payments and subscriptions
  
  ### 3. user_api_keys
  - API keys for Business plan users
  
  ### 4. provider_metrics
  - Provider performance metrics
  
  ### 5. experiments & experiment_assignments
  - A/B testing infrastructure
  
  ### 6. message_templates
  - Notification templates
  
  ### 7. offers_cache & price_points
  - Flight data caching and price history

  ## Security
  - All new tables have RLS enabled
  - Policies ensure users only see their own data
*/

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'users' AND column_name = 'phone'
  ) THEN
    ALTER TABLE users ADD COLUMN phone text;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'users' AND column_name = 'telegram_chat_id'
  ) THEN
    ALTER TABLE users ADD COLUMN telegram_chat_id text;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'users' AND column_name = 'plan'
  ) THEN
    ALTER TABLE users ADD COLUMN plan text DEFAULT 'free';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'users' AND column_name = 'subscription_id'
  ) THEN
    ALTER TABLE users ADD COLUMN subscription_id text;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'users' AND column_name = 'subscription_expires_at'
  ) THEN
    ALTER TABLE users ADD COLUMN subscription_expires_at timestamptz;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'users' AND column_name = 'api_calls_count'
  ) THEN
    ALTER TABLE users ADD COLUMN api_calls_count int DEFAULT 0;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'users' AND column_name = 'notification_credits'
  ) THEN
    ALTER TABLE users ADD COLUMN notification_credits int DEFAULT 20;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS notification_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  channel text NOT NULL,
  provider text,
  provider_message_id text,
  status text NOT NULL CHECK (status IN ('sent', 'failed', 'queued')),
  message_content text,
  error_message text,
  sent_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS payments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  subscription_id text NOT NULL,
  plan text NOT NULL,
  amount numeric,
  currency text DEFAULT 'GBP',
  status text NOT NULL,
  stripe_event_id text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_api_keys (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  key_hash text UNIQUE NOT NULL,
  key_prefix text NOT NULL,
  name text,
  is_active boolean DEFAULT true,
  last_used_at timestamptz,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON user_api_keys(key_hash);

CREATE TABLE IF NOT EXISTS provider_metrics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider text NOT NULL,
  call_count int DEFAULT 0,
  success_count int DEFAULT 0,
  fail_count int DEFAULT 0,
  avg_latency_ms int,
  last_failure_at timestamptz,
  date date DEFAULT current_date
);

CREATE INDEX IF NOT EXISTS idx_provider_metrics ON provider_metrics(provider, date);

CREATE TABLE IF NOT EXISTS experiments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text UNIQUE NOT NULL,
  variants jsonb NOT NULL,
  is_active boolean DEFAULT true,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS experiment_assignments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_id uuid NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  variant text NOT NULL,
  converted boolean DEFAULT false,
  assigned_at timestamptz DEFAULT now(),
  UNIQUE(experiment_id, user_id)
);

CREATE TABLE IF NOT EXISTS message_templates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text UNIQUE NOT NULL,
  channel text NOT NULL CHECK (channel IN ('whatsapp', 'email', 'telegram')),
  template_body text NOT NULL,
  required_params jsonb,
  is_active boolean DEFAULT true,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS offers_cache (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider text NOT NULL,
  from_iata text NOT NULL,
  to_iata text NOT NULL,
  departure timestamptz NOT NULL,
  arrival timestamptz,
  price numeric NOT NULL,
  currency text DEFAULT 'GBP',
  airline text,
  stops int DEFAULT 0,
  booking_link text,
  raw_data jsonb,
  cached_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_offers_route_cache ON offers_cache(from_iata, to_iata, cached_at);

CREATE TABLE IF NOT EXISTS price_points (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  route text NOT NULL,
  price_gbp numeric NOT NULL,
  provider text,
  recorded_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_price_points_route_time ON price_points(route, recorded_at);

ALTER TABLE notification_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE provider_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE experiments ENABLE ROW LEVEL SECURITY;
ALTER TABLE experiment_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE offers_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_points ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read own notifications" ON notification_log;
CREATE POLICY "Users can read own notifications" ON notification_log FOR SELECT TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can read own payments" ON payments;
CREATE POLICY "Users can read own payments" ON payments FOR SELECT TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can read own API keys" ON user_api_keys;
CREATE POLICY "Users can read own API keys" ON user_api_keys FOR SELECT TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can create own API keys" ON user_api_keys;
CREATE POLICY "Users can create own API keys" ON user_api_keys FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own API keys" ON user_api_keys;
CREATE POLICY "Users can update own API keys" ON user_api_keys FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own API keys" ON user_api_keys;
CREATE POLICY "Users can delete own API keys" ON user_api_keys FOR DELETE TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Authenticated users can read metrics" ON provider_metrics;
CREATE POLICY "Authenticated users can read metrics" ON provider_metrics FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "Authenticated users can read experiments" ON experiments;
CREATE POLICY "Authenticated users can read experiments" ON experiments FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "Users can read own assignments" ON experiment_assignments;
CREATE POLICY "Users can read own assignments" ON experiment_assignments FOR SELECT TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Authenticated users can read templates" ON message_templates;
CREATE POLICY "Authenticated users can read templates" ON message_templates FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "Authenticated users can read offers" ON offers_cache;
CREATE POLICY "Authenticated users can read offers" ON offers_cache FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "Authenticated users can read price points" ON price_points;
CREATE POLICY "Authenticated users can read price points" ON price_points FOR SELECT TO authenticated USING (true);
