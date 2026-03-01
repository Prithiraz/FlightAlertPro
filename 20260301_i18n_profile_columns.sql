-- Migration: Add i18n preference columns to user_profiles

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS locale TEXT NOT NULL DEFAULT 'en-US',
  ADD COLUMN IF NOT EXISTS timezone TEXT NOT NULL DEFAULT 'UTC',
  ADD COLUMN IF NOT EXISTS preferred_date_format TEXT;
