-- Migration: add usage_events table for admin analytics
-- Records per-user search/action events used by the admin dashboard.

CREATE TABLE IF NOT EXISTS usage_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid,
  ts timestamptz NOT NULL DEFAULT now(),
  type text NOT NULL,          -- 'search', 'alert_create', 'notification', etc.
  provider text,               -- flight provider used (if applicable)
  count int DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_usage_events_user_ts ON usage_events(user_id, ts);
CREATE INDEX IF NOT EXISTS idx_usage_events_type_ts ON usage_events(type, ts);

ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read their own events only
DROP POLICY IF EXISTS "Users can read own usage events" ON usage_events;
CREATE POLICY "Users can read own usage events" ON usage_events
  FOR SELECT TO authenticated USING (auth.uid() = user_id);
