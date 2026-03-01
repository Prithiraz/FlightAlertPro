/*
  # Add price history, last_triggered_at, and notification_log improvements

  1. Changes to price_alerts
     - Add `last_triggered_at` timestamptz for persistent cooldown tracking

  2. New table: price_history
     - Stores the lowest price found per alert check
     - Used by the history endpoint and the frontend chart

  3. Changes to notification_log
     - Add `alert_id` for linking notifications to alerts
     - Add `dedupe_key` with a unique constraint for idempotent sends
*/

-- Add last_triggered_at to price_alerts for persistent cooldown
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'price_alerts' AND column_name = 'last_triggered_at'
  ) THEN
    ALTER TABLE price_alerts ADD COLUMN last_triggered_at timestamptz;
  END IF;
END $$;

-- Price history per alert check
CREATE TABLE IF NOT EXISTS price_history (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  alert_id    uuid REFERENCES price_alerts(id) ON DELETE CASCADE,
  checked_at  timestamptz DEFAULT now(),
  lowest_price numeric(12,2) NOT NULL,
  currency    text DEFAULT 'USD',
  provider    text
);

CREATE INDEX IF NOT EXISTS idx_price_history_alert_time
  ON price_history(alert_id, checked_at DESC);

ALTER TABLE price_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read own price history" ON price_history;
CREATE POLICY "Users can read own price history" ON price_history
  FOR SELECT TO authenticated
  USING (
    alert_id IN (
      SELECT id FROM price_alerts WHERE user_email = auth.jwt()->>'email'
    )
  );

-- Add alert_id and dedupe_key to notification_log (idempotency)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'notification_log' AND column_name = 'alert_id'
  ) THEN
    ALTER TABLE notification_log ADD COLUMN alert_id uuid;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'notification_log' AND column_name = 'dedupe_key'
  ) THEN
    ALTER TABLE notification_log ADD COLUMN dedupe_key text;
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_notification_log_dedupe
  ON notification_log(dedupe_key)
  WHERE dedupe_key IS NOT NULL;
