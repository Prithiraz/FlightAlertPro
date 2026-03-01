-- Migration: Enterprise/Business tier — workspaces, memberships, invites, API keys
-- Phase 1: core workspace primitives

-- Workspaces table
CREATE TABLE IF NOT EXISTS workspaces (
  id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  name               text        NOT NULL,
  owner_user_id      text        NOT NULL,
  plan               text        NOT NULL DEFAULT 'free',
  stripe_customer_id text,
  created_at         timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workspaces_owner ON workspaces (owner_user_id);

ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Members can read their workspaces" ON workspaces;
CREATE POLICY "Members can read their workspaces" ON workspaces
  FOR SELECT TO authenticated
  USING (
    id IN (
      SELECT workspace_id FROM workspace_memberships WHERE user_id = auth.uid()::text
    )
  );

-- Workspace memberships table (one row per user per workspace)
CREATE TABLE IF NOT EXISTS workspace_memberships (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid        NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
  user_id      text        NOT NULL,
  role         text        NOT NULL DEFAULT 'member'
                           CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
  created_at   timestamptz DEFAULT now(),
  UNIQUE (workspace_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_workspace_memberships_workspace ON workspace_memberships (workspace_id);
CREATE INDEX IF NOT EXISTS idx_workspace_memberships_user      ON workspace_memberships (user_id);

ALTER TABLE workspace_memberships ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Members can read workspace memberships" ON workspace_memberships;
CREATE POLICY "Members can read workspace memberships" ON workspace_memberships
  FOR SELECT TO authenticated
  USING (
    workspace_id IN (
      SELECT workspace_id FROM workspace_memberships wm2 WHERE wm2.user_id = auth.uid()::text
    )
  );

-- Workspace invites table
CREATE TABLE IF NOT EXISTS workspace_invites (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id   uuid        NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
  invited_email  text        NOT NULL,
  role           text        NOT NULL DEFAULT 'member'
                             CHECK (role IN ('admin', 'member', 'viewer')),
  token          text        NOT NULL UNIQUE,
  invited_by     text        NOT NULL,
  accepted_at    timestamptz,
  created_at     timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workspace_invites_token     ON workspace_invites (token);
CREATE INDEX IF NOT EXISTS idx_workspace_invites_workspace ON workspace_invites (workspace_id);

ALTER TABLE workspace_invites ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Admins can manage invites" ON workspace_invites;
CREATE POLICY "Admins can manage invites" ON workspace_invites
  FOR ALL TO authenticated
  USING (
    workspace_id IN (
      SELECT workspace_id FROM workspace_memberships
      WHERE user_id = auth.uid()::text AND role IN ('owner', 'admin')
    )
  );

-- Workspace API keys table (Business tier)
CREATE TABLE IF NOT EXISTS workspace_api_keys (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid        NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
  name         text        NOT NULL,
  key_hash     text        NOT NULL UNIQUE,
  key_prefix   text        NOT NULL,
  created_by   text        NOT NULL,
  last_used_at timestamptz,
  revoked_at   timestamptz,
  created_at   timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workspace_api_keys_workspace ON workspace_api_keys (workspace_id);
CREATE INDEX IF NOT EXISTS idx_workspace_api_keys_hash      ON workspace_api_keys (key_hash);

ALTER TABLE workspace_api_keys ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Admins can manage API keys" ON workspace_api_keys;
CREATE POLICY "Admins can manage API keys" ON workspace_api_keys
  FOR ALL TO authenticated
  USING (
    workspace_id IN (
      SELECT workspace_id FROM workspace_memberships
      WHERE user_id = auth.uid()::text AND role IN ('owner', 'admin')
    )
  );

-- Phase 2: add workspace_id to price_alerts (nullable for backward compat)
ALTER TABLE price_alerts ADD COLUMN IF NOT EXISTS workspace_id uuid
  REFERENCES workspaces (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_price_alerts_workspace ON price_alerts (workspace_id);

-- Phase 5: add workspace_id to usage_events (nullable for backward compat)
ALTER TABLE usage_events ADD COLUMN IF NOT EXISTS workspace_id uuid
  REFERENCES workspaces (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_usage_events_workspace ON usage_events (workspace_id);
