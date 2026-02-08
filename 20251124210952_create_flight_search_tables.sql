/*
  # Flight Search Platform Database Schema

  1. New Tables
    - price_alerts - Store user price alert preferences
    - saved_searches - Store user saved flight searches
    - user_profiles - Store user preferences and profile data
    - analytics_events - Store anonymized analytics data

  2. Security
    - Enable RLS on all tables
    - Add policies for authenticated users
*/

CREATE TABLE IF NOT EXISTS price_alerts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_email text NOT NULL,
  from_iata text NOT NULL,
  to_iata text NOT NULL,
  max_price numeric NOT NULL,
  departure_date date,
  is_active boolean DEFAULT true,
  notification_channels text[] DEFAULT ARRAY['email']::text[],
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS saved_searches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_email text NOT NULL,
  from_iata text NOT NULL,
  to_iata text NOT NULL,
  departure_date date NOT NULL,
  return_date date,
  passengers integer DEFAULT 1,
  cabin_class text DEFAULT 'economy',
  search_name text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text UNIQUE NOT NULL,
  preferred_currency text DEFAULT 'USD',
  theme text DEFAULT 'light',
  frequent_flyer_programs jsonb DEFAULT '{}'::jsonb,
  preferred_airlines text[] DEFAULT ARRAY[]::text[],
  loyalty_tier text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analytics_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type text NOT NULL,
  route text,
  device_type text,
  timestamp timestamptz DEFAULT now(),
  metadata jsonb DEFAULT '{}'::jsonb
);

ALTER TABLE price_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE saved_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own price alerts"
  ON price_alerts
  FOR ALL
  TO authenticated
  USING (user_email = auth.jwt()->>'email')
  WITH CHECK (user_email = auth.jwt()->>'email');

CREATE POLICY "Users can manage own saved searches"
  ON saved_searches
  FOR ALL
  TO authenticated
  USING (user_email = auth.jwt()->>'email')
  WITH CHECK (user_email = auth.jwt()->>'email');

CREATE POLICY "Users can manage own profile"
  ON user_profiles
  FOR ALL
  TO authenticated
  USING (email = auth.jwt()->>'email')
  WITH CHECK (email = auth.jwt()->>'email');

CREATE POLICY "Anyone can log analytics"
  ON analytics_events
  FOR INSERT
  TO anon, authenticated
  WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_price_alerts_user ON price_alerts(user_email);
CREATE INDEX IF NOT EXISTS idx_price_alerts_route ON price_alerts(from_iata, to_iata);
CREATE INDEX IF NOT EXISTS idx_saved_searches_user ON saved_searches(user_email);
CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON user_profiles(email);
CREATE INDEX IF NOT EXISTS idx_analytics_events_type ON analytics_events(event_type);
CREATE INDEX IF NOT EXISTS idx_analytics_events_route ON analytics_events(route);