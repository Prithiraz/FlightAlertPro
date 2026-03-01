-- Phase 2: Audit log table
-- Records sensitive actions for compliance and security review.
CREATE TABLE IF NOT EXISTS audit_log (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     text,
  email       text,
  action      text        NOT NULL,
  target_type text,
  target_id   text,
  ip_hash     text,
  user_agent  text,
  metadata    jsonb,
  created_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_user_id    ON audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action     ON audit_log (action);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log (created_at DESC);

-- Phase 4: Abuse events table
-- Tracks suspicious IP / user behaviour for automated blocking decisions.
CREATE TABLE IF NOT EXISTS abuse_events (
  id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  ip_hash    text,
  user_id    text,
  event_type text        NOT NULL,
  detail     text,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_abuse_events_ip_hash    ON abuse_events (ip_hash);
CREATE INDEX IF NOT EXISTS idx_abuse_events_user_id    ON abuse_events (user_id);
CREATE INDEX IF NOT EXISTS idx_abuse_events_created_at ON abuse_events (created_at DESC);
