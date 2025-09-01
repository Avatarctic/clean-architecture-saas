-- =============================================================================
-- CLEAN ARCHITECTURE SAAS - CONSOLIDATED SCHEMA ROLLBACK
-- =============================================================================
-- This migration removes the complete database schema for the Clean Architecture SaaS application

-- Drop triggers first
DROP TRIGGER IF EXISTS update_tenants_updated_at ON tenants;
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
DROP TRIGGER IF EXISTS update_feature_flags_updated_at ON feature_flags;

-- Drop function
DROP FUNCTION IF EXISTS update_updated_at_column();

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS role_permissions;
DROP TABLE IF EXISTS blacklisted_tokens;
DROP TABLE IF EXISTS refresh_tokens;
DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS feature_flags;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS tenants;
