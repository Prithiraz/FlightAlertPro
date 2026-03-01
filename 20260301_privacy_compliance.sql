-- Phase 2: deletion_requests table
-- Stores account deletion requests.  After deletion completes the user_id is
-- set to NULL and email_hash retains a one-way hash for audit purposes.

CREATE TABLE IF NOT EXISTS deletion_requests (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       uuid,                      -- set to NULL after deletion completes
    email_hash    text NOT NULL,             -- SHA-256(email)[:32]
    token_hash    text NOT NULL,             -- SHA-256(confirm_token)[:32]
    status        text NOT NULL DEFAULT 'pending',  -- pending | processing | done
    requested_at  timestamptz NOT NULL DEFAULT now(),
    processed_at  timestamptz
);

-- Index for fast token lookup
CREATE INDEX IF NOT EXISTS deletion_requests_token_hash_idx ON deletion_requests (token_hash);
CREATE INDEX IF NOT EXISTS deletion_requests_user_id_idx    ON deletion_requests (user_id);

-- Phase 4: consent / communications preference columns on user_profiles
ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS marketing_opt_in       boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS product_updates_opt_in boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS transactional_only     boolean NOT NULL DEFAULT false;
