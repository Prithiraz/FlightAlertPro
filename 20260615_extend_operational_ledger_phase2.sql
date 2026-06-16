-- Migration: Phase 2 extends operational_ledger into the FBO 'data moat'.
-- Adds explicit ground-truth columns alongside the existing event timestamps so
-- predicted vs. actual ready times and late-pickup outcomes can train
-- FBO-specific micro-models.

ALTER TABLE operational_ledger
  ADD COLUMN IF NOT EXISTS airport_code text,
  ADD COLUMN IF NOT EXISTS predicted_ready_time timestamptz,
  ADD COLUMN IF NOT EXISTS actual_ready_time timestamptz,
  ADD COLUMN IF NOT EXISTS late_pickup_boolean boolean;

CREATE INDEX IF NOT EXISTS operational_ledger_airport_code_idx ON operational_ledger (airport_code);
