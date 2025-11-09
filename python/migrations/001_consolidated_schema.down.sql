-- Down migration for consolidated schema additions (feature flags)
DROP TRIGGER IF EXISTS update_feature_flags_updated_at ON feature_flags;
DROP FUNCTION IF EXISTS update_updated_at_column();
DROP TABLE IF EXISTS feature_flags;
DROP TABLE IF EXISTS audit_events;
DROP TABLE IF EXISTS role_permissions;
DROP TABLE IF EXISTS permissions;
DROP TABLE IF EXISTS roles;
