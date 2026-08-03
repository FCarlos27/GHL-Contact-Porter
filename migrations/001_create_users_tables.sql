-- Migration: 001_create_users_tables.sql
-- Creates the `users` and `user_locations` tables for GHL dashboard auth.

-- 1. users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ghl_user_id TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    first_name TEXT,
    last_name TEXT,
    password_hash TEXT,
    is_agency_owner BOOLEAN NOT NULL DEFAULT false,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. user_locations junction table
CREATE TABLE IF NOT EXISTS user_locations (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    location_id TEXT NOT NULL REFERENCES locations(location_id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, location_id)
);

-- Index for lookups by location_id (agency-owner expansion / location-based queries)
CREATE INDEX IF NOT EXISTS idx_user_locations_location_id ON user_locations (location_id);
