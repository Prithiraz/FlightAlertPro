-- Migration: create push_subscriptions table for Web Push notifications
-- Run this migration in your Supabase SQL editor or database migration tool.

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    user_email  TEXT NOT NULL,
    endpoint    TEXT NOT NULL,
    p256dh      TEXT NOT NULL,
    auth        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- One subscription per (user, endpoint) – upsert target
    UNIQUE (user_id, endpoint)
);

-- Index for fast lookup by user (used when sending alerts)
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_user_email
    ON push_subscriptions (user_email);

-- Auto-update updated_at on row modification
CREATE OR REPLACE FUNCTION _update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'push_subscriptions_updated_at'
    ) THEN
        CREATE TRIGGER push_subscriptions_updated_at
            BEFORE UPDATE ON push_subscriptions
            FOR EACH ROW EXECUTE FUNCTION _update_updated_at();
    END IF;
END $$;

COMMENT ON TABLE push_subscriptions IS
    'Web Push (VAPID) subscriptions per user device. Used by the alert worker to send browser push notifications.';
