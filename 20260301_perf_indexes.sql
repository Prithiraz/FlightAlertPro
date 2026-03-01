-- Performance indexes for common query patterns
-- Phase 6: DB query optimization

-- Alerts: fast lookup by user + active state
CREATE INDEX IF NOT EXISTS idx_price_alerts_user_active
  ON price_alerts (user_id, active);

-- Notification log: user + time range queries
CREATE INDEX IF NOT EXISTS idx_notification_log_user_created
  ON notification_log (user_id, created_at DESC);

-- Price history: alert + time range queries (most recent first)
CREATE INDEX IF NOT EXISTS idx_price_history_alert_checked
  ON price_history (alert_id, checked_at DESC);
