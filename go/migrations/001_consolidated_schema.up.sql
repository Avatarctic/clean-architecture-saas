-- =============================================================================
-- CLEAN ARCHITECTURE SAAS - CONSOLIDATED DATABASE SCHEMA
-- =============================================================================
-- This migration creates the complete database schema for the Clean Architecture SaaS application
-- Includes: Tenants, Users, Feature Flags, Audit Logs, Auth Tokens, and Permissions

-- =============================================================================
-- CORE TABLES
-- =============================================================================

-- Create tenants table
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    domain VARCHAR(255),
    plan VARCHAR(50) NOT NULL DEFAULT 'free',
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'member',
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    audit_enabled BOOLEAN DEFAULT true,
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- FEATURE FLAGS
-- =============================================================================

-- Create feature_flags table
CREATE TABLE IF NOT EXISTS feature_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    key VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    type VARCHAR(50) NOT NULL DEFAULT 'boolean',
    is_enabled BOOLEAN DEFAULT false,
    enabled_value JSONB, -- Value for users in rollout
    default_value JSONB, -- Value for users outside rollout
    rules JSONB DEFAULT '[]',
    rollout JSONB DEFAULT '{"percentage": 0, "strategy": "random"}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);


-- =============================================================================
-- AUDIT LOGGING
-- =============================================================================

-- Create audit_logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(100) NOT NULL,
    resource_id UUID,
    details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- AUTHENTICATION TOKEN MANAGEMENT
-- =============================================================================

-- Create refresh_tokens table for JWT refresh tokens
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create blacklisted_tokens table for invalidated tokens
CREATE TABLE IF NOT EXISTS blacklisted_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE, -- Optional: for user-specific blacklisting
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    reason TEXT -- Optional: reason for blacklisting (logout, security, etc.)
);


-- =============================================================================
-- ROLE-BASED PERMISSIONS
-- =============================================================================

-- Create role_permissions table for dynamic permission management
CREATE TABLE IF NOT EXISTS role_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role VARCHAR(50) NOT NULL,
    permission VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Ensure unique role-permission combinations
    UNIQUE(role, permission)
);

-- =============================================================================
-- INDEXES FOR PERFORMANCE
-- =============================================================================

-- Core table indexes
CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_tenant_created_at ON users(tenant_id, created_at DESC);

-- Audit log indexes
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_id ON audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_timestamp ON audit_logs(tenant_id, timestamp DESC);

-- (removed DB-backed email_tokens indexes; email tokens are stored in Redis)

-- Auth token indexes
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);

CREATE INDEX IF NOT EXISTS idx_blacklisted_tokens_token_hash ON blacklisted_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_blacklisted_tokens_expires_at ON blacklisted_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_blacklisted_tokens_user_id ON blacklisted_tokens(user_id) WHERE user_id IS NOT NULL;


-- Permission indexes
CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role);

-- =============================================================================
-- TRIGGERS AND FUNCTIONS
-- =============================================================================

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_tenants_updated_at BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_feature_flags_updated_at BEFORE UPDATE ON feature_flags FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- COMMENTS FOR DOCUMENTATION
-- =============================================================================

COMMENT ON TABLE tenants IS 'Multi-tenant organizations with isolated data';
COMMENT ON TABLE users IS 'User accounts belonging to tenants';
COMMENT ON TABLE feature_flags IS 'Dynamic feature toggles and A/B testing';
COMMENT ON TABLE audit_logs IS 'Comprehensive audit trail for all actions';
COMMENT ON TABLE refresh_tokens IS 'JWT refresh tokens for authentication';
COMMENT ON TABLE blacklisted_tokens IS 'Invalidated JWT tokens to prevent reuse';
COMMENT ON TABLE role_permissions IS 'Dynamic role-based access control';

COMMENT ON COLUMN blacklisted_tokens.user_id IS 'Optional user association for user-specific token invalidation';
COMMENT ON COLUMN blacklisted_tokens.reason IS 'Reason for token blacklisting (logout, security breach, etc.)';
-- (removed DB-backed email_tokens comments)

-- =============================================================================
-- DEFAULT ROLE PERMISSIONS
-- =============================================================================

-- Insert default permissions for SuperAdmin (full access)
INSERT INTO role_permissions (role, permission) VALUES
-- User Management - Full access
('super_admin', 'create_tenant_user'),
('super_admin', 'create_all_users'),
('super_admin', 'read_own_profile'),
('super_admin', 'read_tenant_users'),
('super_admin', 'read_all_users'),
('super_admin', 'update_own_profile'),
('super_admin', 'update_tenant_users'),
('super_admin', 'update_all_users'),
('super_admin', 'delete_tenant_users'),
('super_admin', 'delete_all_users'),
('super_admin', 'change_own_password'),
('super_admin', 'change_tenant_user_password'),
('super_admin', 'change_user_password'),
('super_admin', 'update_own_email'),
('super_admin', 'update_tenant_user_email'),
('super_admin', 'update_user_email'),

-- Session Management - Full access
('super_admin', 'view_own_sessions'),
('super_admin', 'view_tenant_sessions'),
('super_admin', 'view_all_sessions'),
('super_admin', 'terminate_own_sessions'),
('super_admin', 'terminate_tenant_sessions'),
('super_admin', 'terminate_all_sessions'),

-- Tenant Management - Full access
('super_admin', 'create_tenant'),
('super_admin', 'read_own_tenant'),
('super_admin', 'read_all_tenants'),
('super_admin', 'update_tenant'),
('super_admin', 'manage_tenant_status'),

-- Feature Flags - Full access
('super_admin', 'create_feature_flag'),
('super_admin', 'read_feature_flag'),
('super_admin', 'update_feature_flag'),
('super_admin', 'delete_feature_flag'),

-- Billing & Administration
('super_admin', 'view_audit_log'),

-- Permission Management
('super_admin', 'manage_permissions'),
('super_admin', 'assign_permissions'),
('super_admin', 'view_permissions')
ON CONFLICT (role, permission) DO NOTHING;

-- Insert default permissions for Admin (tenant scope)
INSERT INTO role_permissions (role, permission) VALUES
-- User Management - Tenant scope
('admin', 'create_tenant_user'),
('admin', 'read_own_profile'),
('admin', 'read_tenant_users'),
('admin', 'update_own_profile'),
('admin', 'update_tenant_users'),
('admin', 'delete_tenant_users'),
('admin', 'change_own_password'),
('admin', 'change_tenant_user_password'),
('admin', 'update_own_email'),
('admin', 'update_tenant_user_email'),

-- Session Management - Tenant scope
('admin', 'view_own_sessions'),
('admin', 'view_tenant_sessions'),
('admin', 'terminate_own_sessions'),
('admin', 'terminate_tenant_sessions'),

-- Tenant Management - Own tenant only
('admin', 'read_own_tenant'),
('admin', 'update_tenant'),

-- Feature Flags & Billing
('admin', 'read_feature_flag'),
('admin', 'view_audit_log'),

-- Limited permission management
('admin', 'view_permissions')
ON CONFLICT (role, permission) DO NOTHING;

-- Insert default permissions for Member (limited access)
INSERT INTO role_permissions (role, permission) VALUES
-- User Management - Self and limited tenant access
('member', 'read_own_profile'),
('member', 'update_own_profile'),
('member', 'read_tenant_users'),
('member', 'change_own_password'),
('member', 'update_own_email'),

-- Session Management - Own sessions only
('member', 'view_own_sessions'),
('member', 'terminate_own_sessions'),

-- Tenant Management - Read only
('member', 'read_own_tenant'),

-- Feature Flags - Read only
('member', 'read_feature_flag')
ON CONFLICT (role, permission) DO NOTHING;

-- Insert default permissions for Guest (minimal access)
INSERT INTO role_permissions (role, permission) VALUES
-- User Management - Very limited
('guest', 'read_own_profile'),

-- Session Management - Own sessions only
('guest', 'view_own_sessions'),
('guest', 'terminate_own_sessions'),

-- Tenant Management - Basic read
('guest', 'read_own_tenant'),

-- Feature Flags - Read only
('guest', 'read_feature_flag')
ON CONFLICT (role, permission) DO NOTHING;

-- =============================================================================
-- SEED: Platform tenant and initial SuperAdmin user
-- The following block is idempotent: it upserts the tenant by slug and inserts the admin user
-- The password is stored using bcrypt provided by the pgcrypto extension
-- =============================================================================

-- Ensure pgcrypto is available for crypt/gen_salt
CREATE EXTENSION IF NOT EXISTS pgcrypto;

WITH tenant_upsert AS (
    INSERT INTO tenants (id, name, slug, domain, plan, status, settings, created_at, updated_at)
    VALUES (gen_random_uuid(), 'Platform', 'platform', NULL, 'platform', 'active', '{}', NOW(), NOW())
    ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
    RETURNING id
)
INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name, role, is_active, email_verified, audit_enabled, created_at, updated_at)
SELECT
    gen_random_uuid(),
    t.id,
    'admin@example.com',
    crypt('SuperAdmin123!', gen_salt('bf', 12)), -- bcrypt-hashed password
    'Platform',
    'Admin',
    'super_admin',
    true,
    true,
    true,
    NOW(),
    NOW()
FROM tenant_upsert t
ON CONFLICT (email) DO NOTHING;
