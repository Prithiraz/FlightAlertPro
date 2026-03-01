-- Migration: Add user_profiles onboarding columns and saved_searches, alert_templates, notification_log tables

-- Extend user_profiles with onboarding fields (add columns if not exist)
ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS home_currency TEXT NOT NULL DEFAULT 'USD',
  ADD COLUMN IF NOT EXISTS default_channels TEXT[] NOT NULL DEFAULT ARRAY['email'],
  ADD COLUMN IF NOT EXISTS onboarded BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- saved_searches
CREATE TABLE IF NOT EXISTS saved_searches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  name TEXT NOT NULL,
  params_json JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_saved_searches_user_id ON saved_searches(user_id);

-- Row-level security: users can only access their own rows
ALTER TABLE saved_searches ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS saved_searches_owner ON saved_searches
  USING (user_id = auth.uid());

-- alert_templates
CREATE TABLE IF NOT EXISTS alert_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  name TEXT NOT NULL,
  template_json JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_templates_user_id ON alert_templates(user_id);

ALTER TABLE alert_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS alert_templates_owner ON alert_templates
  USING (user_id = auth.uid());

-- notification_log (if not already present from worker)
CREATE TABLE IF NOT EXISTS notification_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID,
  alert_id UUID,
  channel TEXT,
  payload JSONB,
  status TEXT,
  error TEXT,
  sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notification_log_user_id ON notification_log(user_id);
CREATE INDEX IF NOT EXISTS idx_notification_log_sent_at ON notification_log(sent_at DESC);
