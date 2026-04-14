-- Migration: Add Post-Booking Travel Credit Engine columns to price_alerts
-- is_purchased: flags that this alert tracks a flight the user already bought
-- purchase_price: the price the user paid when booking the flight

ALTER TABLE price_alerts
  ADD COLUMN IF NOT EXISTS is_purchased BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS purchase_price NUMERIC;
