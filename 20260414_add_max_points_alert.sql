-- Migration: Add max_points column to price_alerts for Business-tier point-based thresholds

ALTER TABLE price_alerts
  ADD COLUMN IF NOT EXISTS max_points INTEGER;
