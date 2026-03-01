-- Migration: Growth Engine Tables
-- Phase 2: Referral system
-- Phase 4: Growth events tracking
-- Phase 3: Lifecycle email flags added to user_profiles

-- ============================================================
-- 1. Referral codes (one per user)
-- ============================================================
CREATE TABLE IF NOT EXISTS referral_codes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    code        TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_referral_codes_user_id ON referral_codes(user_id);
CREATE INDEX IF NOT EXISTS idx_referral_codes_code ON referral_codes(code);

-- ============================================================
-- 2. Referral events (visits, signups, paid conversions)
-- ============================================================
CREATE TABLE IF NOT EXISTS referral_events (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    referrer_user_id  UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    code              TEXT NOT NULL,
    event_type        TEXT NOT NULL CHECK (event_type IN ('visit', 'signup', 'paid')),
    ip_hash           TEXT,
    user_agent        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_referral_events_code ON referral_events(code);
CREATE INDEX IF NOT EXISTS idx_referral_events_referrer ON referral_events(referrer_user_id);

-- ============================================================
-- 3. User attribution (which referral code brought a user)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_attribution (
    user_id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    referred_by_code     TEXT,
    referred_by_user_id  UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    first_seen_at        TIMESTAMPTZ DEFAULT now(),
    signup_at            TIMESTAMPTZ,
    paid_at              TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 4. Growth / funnel events table
-- ============================================================
CREATE TABLE IF NOT EXISTS growth_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_name  TEXT NOT NULL,
    user_id     UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    props_json  JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_growth_events_event_name ON growth_events(event_name);
CREATE INDEX IF NOT EXISTS idx_growth_events_created_at ON growth_events(created_at);
CREATE INDEX IF NOT EXISTS idx_growth_events_user_id ON growth_events(user_id);

-- ============================================================
-- 5. Add lifecycle email columns to user_profiles
--    (safe – IF NOT EXISTS / DO NOTHING pattern)
-- ============================================================
ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS lifecycle_emails_opt_in       BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS lifecycle_welcome_sent        BOOLEAN,
    ADD COLUMN IF NOT EXISTS lifecycle_nudge_sent          BOOLEAN,
    ADD COLUMN IF NOT EXISTS lifecycle_tips_sent           BOOLEAN,
    ADD COLUMN IF NOT EXISTS lifecycle_reengagement_sent   BOOLEAN;

-- ============================================================
-- RLS policies
-- ============================================================

-- referral_codes: users can read their own code
ALTER TABLE referral_codes ENABLE ROW LEVEL SECURITY;
CREATE POLICY referral_codes_select_own ON referral_codes
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY referral_codes_insert_own ON referral_codes
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- referral_events: public insert (anon visits), no user reads needed
ALTER TABLE referral_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY referral_events_insert_all ON referral_events
    FOR INSERT WITH CHECK (true);

-- user_attribution: users can read their own row
ALTER TABLE user_attribution ENABLE ROW LEVEL SECURITY;
CREATE POLICY user_attribution_select_own ON user_attribution
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY user_attribution_insert_own ON user_attribution
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- growth_events: authenticated and anonymous inserts allowed
ALTER TABLE growth_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY growth_events_insert_all ON growth_events
    FOR INSERT WITH CHECK (true);
