-- Migration: Add preferred_reward_program column to user_profiles
-- Accepted values: 'chase_ur', 'amex_mr', 'capital_one', 'none'

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS preferred_reward_program TEXT NOT NULL DEFAULT 'none'
  CHECK (preferred_reward_program IN ('chase_ur', 'amex_mr', 'capital_one', 'none'));
