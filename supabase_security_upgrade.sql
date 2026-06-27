-- Run this in your Supabase SQL Editor
-- This automatically generates a secure cryptographic token the moment a flight enters the system
ALTER TABLE operational_ledger ADD COLUMN IF NOT EXISTS session_token UUID DEFAULT gen_random_uuid() UNIQUE;
