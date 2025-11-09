-- Consolidated schema additions for Python app

CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    slug VARCHAR(100) UNIQUE,
    domain VARCHAR(255),
    plan VARCHAR(50) NOT NULL DEFAULT 'free',
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    settings JSONB DEFAULT '{}' ,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ensure pgcrypto is available for crypt/gen_salt
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Trigger function to update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_tenants_updated_at BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- USERS
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(320) NOT NULL,
    hashed_password TEXT NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'member',
    email_verified BOOLEAN NOT NULL DEFAULT false,
    audit_enabled BOOLEAN NOT NULL DEFAULT false,
    last_login_at TIMESTAMP WITH TIME ZONE NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uix_tenant_email UNIQUE (tenant_id, email)
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    revoked BOOLEAN NOT NULL DEFAULT false,
    expires_at TIMESTAMP WITH TIME ZONE NULL
);

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS permissions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    tenant_id INTEGER NULL REFERENCES tenants(id) ON DELETE CASCADE,
    action VARCHAR(255) NOT NULL,
    resource VARCHAR(100),
    resource_id INTEGER,
    details JSONB DEFAULT '{}',
    ip_address VARCHAR(45),
    user_agent TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS blacklisted_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NULL,
    reason TEXT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS feature_flags (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NULL REFERENCES tenants(id) ON DELETE CASCADE,
    key VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(50) NOT NULL DEFAULT 'boolean',
    is_enabled BOOLEAN DEFAULT false,
    enabled_value JSONB,
    default_value JSONB,
    rules JSONB DEFAULT '[]',
    rollout JSONB DEFAULT '{"percentage": 0, "strategy": "random"}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uix_feature_key UNIQUE (key)
);

INSERT INTO roles (name, description) VALUES
('super_admin', 'Platform super admin'),
('admin', 'Tenant admin'),
('member', 'Tenant member'),
('guest', 'Guest')
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- SEED: Platform tenant and initial SuperAdmin user (idempotent upsert)
-- =============================================================================
WITH tenant_upsert AS (
    INSERT INTO tenants (name, slug, domain, plan, status, settings, created_at, updated_at)
    VALUES ('Platform', 'platform', NULL, 'platform', 'active', '{}', NOW(), NOW())
    ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
    RETURNING id
)
INSERT INTO users (tenant_id, email, hashed_password, first_name, last_name, role, is_active, email_verified, audit_enabled, created_at, updated_at)
SELECT t.id, 'admin@example.com', crypt('SuperAdmin123!', gen_salt('bf', 12)), 'Platform', 'Admin', 'super_admin', true, true, true, NOW(), NOW()
FROM tenant_upsert t
ON CONFLICT (tenant_id, email) DO NOTHING;

-- insert default permissions
-- Core permissions following CRUD pattern with scope levels:
-- Naming convention: {action}_{scope}_{resource}
-- Scopes: own (self), tenant (within tenant), all (platform-wide)
-- Actions: create, read, update, delete, manage, view, change, terminate

INSERT INTO permissions (name, description) VALUES
-- User Management Permissions
('create_tenant_user', 'Create users within tenant'),
('create_all_users', 'Create users across all tenants (platform admin)'),
('read_own_profile', 'Read own user profile'),
('read_tenant_users', 'Read users within tenant'),
('read_all_users', 'Read all users across tenants (platform admin)'),
('update_own_profile', 'Update own user profile'),
('update_tenant_users', 'Update users within tenant'),
('update_all_users', 'Update all users across tenants (platform admin)'),
('delete_tenant_users', 'Delete users within tenant'),
('delete_all_users', 'Delete users across tenants (platform admin)'),

-- Password Management Permissions
('change_own_password', 'Change own password'),
('change_tenant_user_password', 'Change password for users within tenant'),
('change_user_password', 'Change password for any user (platform admin)'),

-- Email Management Permissions
('update_own_email', 'Update own email address'),
('update_tenant_user_email', 'Update email for users within tenant'),
('update_user_email', 'Update email for any user (platform admin)'),

-- Session Management Permissions
('view_own_sessions', 'View own active sessions'),
('view_tenant_sessions', 'View sessions for users within tenant'),
('view_all_sessions', 'View all sessions across tenants (platform admin)'),
('terminate_own_sessions', 'Terminate own sessions'),
('terminate_tenant_sessions', 'Terminate sessions for users within tenant'),
('terminate_all_sessions', 'Terminate any sessions (platform admin)'),

-- Tenant Management Permissions
('create_tenant', 'Create new tenants (platform admin)'),
('read_own_tenant', 'Read own tenant information'),
('read_all_tenants', 'Read all tenants (platform admin)'),
('update_tenant', 'Update tenant information'),
('manage_tenant_status', 'Manage tenant status (suspend, activate, cancel)'),

-- Feature Flag Permissions
('create_feature_flag', 'Create feature flags'),
('read_feature_flag', 'Read feature flags'),
('update_feature_flag', 'Update feature flags'),
('delete_feature_flag', 'Delete feature flags'),

-- Audit & Compliance Permissions
('view_audit_log', 'View audit logs for compliance and security'),

-- Permission Management
('view_permissions', 'View available permissions'),
('manage_permissions', 'Manage role permissions assignments'),
('assign_permissions', 'Assign permissions to roles')

ON CONFLICT (name) DO NOTHING;

-- assign permissions to roles (idempotent)
-- assign permissions to roles (idempotent) - seed expanded to match Go defaults
-- Super Admin: full access
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'create_tenant_user' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'create_all_users' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'read_own_profile' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'read_tenant_users' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'read_all_users' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'update_own_profile' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'update_tenant_users' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'update_all_users' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'delete_tenant_users' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'delete_all_users' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'change_own_password' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'change_tenant_user_password' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'change_user_password' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'update_own_email' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'update_tenant_user_email' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'update_user_email' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;

-- Session Management
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'view_own_sessions' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'view_tenant_sessions' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'view_all_sessions' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'terminate_own_sessions' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'terminate_tenant_sessions' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'terminate_all_sessions' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;

-- Tenant Management
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'create_tenant' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'read_own_tenant' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'read_all_tenants' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'update_tenant' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'manage_tenant_status' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;

-- Feature Flags, Billing & Admin
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'create_feature_flag' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'read_feature_flag' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'update_feature_flag' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'delete_feature_flag' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;

-- Audit & Permission Management
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'view_audit_log' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'manage_permissions' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'assign_permissions' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'view_permissions' WHERE r.name = 'super_admin' ON CONFLICT DO NOTHING;

-- Admin: tenant-scoped capabilities
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'create_tenant_user' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'read_own_profile' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'read_tenant_users' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'update_own_profile' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'update_tenant_users' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'delete_tenant_users' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'change_own_password' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'change_tenant_user_password' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'update_own_email' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'update_tenant_user_email' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'view_own_sessions' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'view_tenant_sessions' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'terminate_own_sessions' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'terminate_tenant_sessions' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'read_own_tenant' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'update_tenant' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'read_feature_flag' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'view_audit_log' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'view_permissions' WHERE r.name = 'admin' ON CONFLICT DO NOTHING;

-- Member: limited capabilities
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'read_own_profile' WHERE r.name = 'member' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'update_own_profile' WHERE r.name = 'member' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'read_tenant_users' WHERE r.name = 'member' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'change_own_password' WHERE r.name = 'member' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'update_own_email' WHERE r.name = 'member' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'view_own_sessions' WHERE r.name = 'member' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'terminate_own_sessions' WHERE r.name = 'member' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'read_own_tenant' WHERE r.name = 'member' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'read_feature_flag' WHERE r.name = 'member' ON CONFLICT DO NOTHING;

-- Guest: minimal access
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'read_own_profile' WHERE r.name = 'guest' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'view_own_sessions' WHERE r.name = 'guest' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'terminate_own_sessions' WHERE r.name = 'guest' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'read_own_tenant' WHERE r.name = 'guest' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name = 'read_feature_flag' WHERE r.name = 'guest' ON CONFLICT DO NOTHING;

-- Trigger function to update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_feature_flags_updated_at BEFORE UPDATE ON feature_flags FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger for users.updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Indexes for performance optimization
-- Users table indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users(tenant_id);

-- Tenants table indexes
CREATE INDEX IF NOT EXISTS idx_tenants_slug ON tenants(slug);
CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status);

-- Refresh tokens indexes
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);

-- Audit events indexes
CREATE INDEX IF NOT EXISTS idx_audit_events_tenant_id ON audit_events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_user_id ON audit_events(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp ON audit_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_events_action ON audit_events(action);
CREATE INDEX IF NOT EXISTS idx_audit_events_resource ON audit_events(resource);
CREATE INDEX IF NOT EXISTS idx_audit_events_resource_id ON audit_events(resource_id);

-- Feature flags indexes
CREATE INDEX IF NOT EXISTS idx_feature_flags_tenant_id ON feature_flags(tenant_id);
CREATE INDEX IF NOT EXISTS idx_feature_flags_key ON feature_flags(key);

-- Blacklisted tokens indexes
CREATE INDEX IF NOT EXISTS idx_blacklisted_tokens_expires_at ON blacklisted_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_blacklisted_tokens_user_id ON blacklisted_tokens(user_id);

-- Roles and permissions indexes
CREATE INDEX IF NOT EXISTS idx_roles_name ON roles(name);
CREATE INDEX IF NOT EXISTS idx_permissions_name ON permissions(name);

-- Role-permission lookup indexes
CREATE INDEX IF NOT EXISTS idx_role_permissions_role_id ON role_permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_role_permissions_permission_id ON role_permissions(permission_id);
