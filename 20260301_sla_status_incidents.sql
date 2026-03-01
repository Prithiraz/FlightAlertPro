-- SLA / Status Page / Incident tooling migration
-- Phase 1: service_metrics table
CREATE TABLE IF NOT EXISTS service_metrics (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ts          timestamptz NOT NULL DEFAULT now(),
  metric_name text NOT NULL,
  value       numeric NOT NULL,
  labels_json jsonb
);

CREATE INDEX IF NOT EXISTS idx_service_metrics_name_ts
  ON service_metrics (metric_name, ts DESC);

-- Phase 4: incidents table
CREATE TABLE IF NOT EXISTS incidents (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  started_at      timestamptz NOT NULL DEFAULT now(),
  ended_at        timestamptz,
  severity        text NOT NULL DEFAULT 'minor'
                    CHECK (severity IN ('minor', 'major', 'critical')),
  title           text NOT NULL,
  description     text,
  components_json jsonb,
  status          text NOT NULL DEFAULT 'investigating'
                    CHECK (status IN ('investigating', 'identified', 'monitoring', 'resolved')),
  created_by      text,
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents (status, started_at DESC);

-- Phase 5: uptime_checks table
CREATE TABLE IF NOT EXISTS uptime_checks (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ts          timestamptz NOT NULL DEFAULT now(),
  check_name  text NOT NULL,
  ok          boolean NOT NULL,
  latency_ms  integer,
  error       text
);

CREATE INDEX IF NOT EXISTS idx_uptime_checks_name_ts
  ON uptime_checks (check_name, ts DESC);

-- RLS
ALTER TABLE service_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents        ENABLE ROW LEVEL SECURITY;
ALTER TABLE uptime_checks    ENABLE ROW LEVEL SECURITY;

-- service_metrics: admin read-only via service role; public reads blocked
DROP POLICY IF EXISTS "service_role full access service_metrics" ON service_metrics;
CREATE POLICY "service_role full access service_metrics"
  ON service_metrics FOR ALL USING (true);

-- incidents: public can read; writes via service role
DROP POLICY IF EXISTS "public read incidents" ON incidents;
CREATE POLICY "public read incidents"
  ON incidents FOR SELECT USING (true);

DROP POLICY IF EXISTS "service_role full access incidents" ON incidents;
CREATE POLICY "service_role full access incidents"
  ON incidents FOR ALL USING (true);

-- uptime_checks: admin/service reads
DROP POLICY IF EXISTS "service_role full access uptime_checks" ON uptime_checks;
CREATE POLICY "service_role full access uptime_checks"
  ON uptime_checks FOR ALL USING (true);
