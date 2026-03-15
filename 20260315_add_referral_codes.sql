-- Migration: referral_codes table
-- Stores one referral code per user for the FlightAlertPro referral programme.
-- Referrers earn account credits when a referred user upgrades to a paid plan.

CREATE TABLE IF NOT EXISTS referral_codes (
    id                 BIGSERIAL PRIMARY KEY,
    code               VARCHAR(20)    UNIQUE NOT NULL,
    user_email         TEXT           NOT NULL,
    uses               INTEGER        NOT NULL DEFAULT 0,
    credits_earned_usd NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    created_at         TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_referral_codes_email
    ON referral_codes (user_email);

CREATE INDEX IF NOT EXISTS idx_referral_codes_code
    ON referral_codes (code);
