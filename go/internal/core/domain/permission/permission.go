package permission

import "github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"

// Permission represents a specific permission in the system
type Permission string

const (
	// User Management Permissions
	CreateTenantUser         Permission = "create_tenant_user"          // Create users within same tenant
	CreateAllUsers           Permission = "create_all_users"            // Create users in any tenant (super admin only)
	ReadOwnProfile           Permission = "read_own_profile"            // Read current user's own profile
	ReadTenantUsers          Permission = "read_tenant_users"           // Read users within same tenant
	ReadAllUsers             Permission = "read_all_users"              // Read any user (super admin only)
	UpdateOwnProfile         Permission = "update_own_profile"          // Update own profile
	UpdateTenantUsers        Permission = "update_tenant_users"         // Update users within same tenant
	UpdateAllUsers           Permission = "update_all_users"            // Update any user (super admin only)
	DeleteTenantUsers        Permission = "delete_tenant_users"         // Delete users within same tenant
	DeleteAllUsers           Permission = "delete_all_users"            // Delete any user (super admin only)
	ChangeOwnPassword        Permission = "change_own_password"         // Change own password
	ChangeTenantUserPassword Permission = "change_tenant_user_password" // Change passwords of users within same tenant
	ChangeUserPassword       Permission = "change_user_password"        // Change any user's password (super admin only)
	UpdateOwnEmail           Permission = "update_own_email"            // Update own email
	UpdateTenantUserEmail    Permission = "update_tenant_user_email"    // Update email of users within same tenant
	UpdateUserEmail          Permission = "update_user_email"           // Update any user's email (super admin only)

	// Session Management Permissions
	ViewOwnSessions         Permission = "view_own_sessions"         // View own active sessions
	ViewTenantSessions      Permission = "view_tenant_sessions"      // View sessions of users within same tenant
	ViewAllSessions         Permission = "view_all_sessions"         // View sessions of any user (super admin only)
	TerminateOwnSessions    Permission = "terminate_own_sessions"    // Terminate own sessions
	TerminateTenantSessions Permission = "terminate_tenant_sessions" // Terminate sessions of users within same tenant
	TerminateAllSessions    Permission = "terminate_all_sessions"    // Terminate sessions of any user (super admin only)

	// Tenant Management Permissions
	CreateTenant       Permission = "create_tenant"        // Create new tenants (super admin)
	ReadOwnTenant      Permission = "read_own_tenant"      // Read own tenant info
	ReadAllTenants     Permission = "read_all_tenants"     // Read all tenants (super admin)
	UpdateTenant       Permission = "update_tenant"        // Update tenant settings
	ManageTenantStatus Permission = "manage_tenant_status" // Manage tenant status (suspend, activate, cancel)

	// Feature Flag Permissions
	CreateFeatureFlag Permission = "create_feature_flag" // Create feature flags
	ReadFeatureFlag   Permission = "read_feature_flag"   // Read and evaluate feature flags
	UpdateFeatureFlag Permission = "update_feature_flag" // Update feature flags
	DeleteFeatureFlag Permission = "delete_feature_flag" // Delete feature flags

	// Permission Management Permissions
	ViewPermissions   Permission = "view_permissions"   // View role permissions
	ManagePermissions Permission = "manage_permissions" // Manage role permissions

	// Audit & Monitoring Permissions
	ViewAuditLog Permission = "view_audit_log" // View audit logs
)

// String returns the string representation of the permission
func (p Permission) String() string {
	return string(p)
}

// IsValid checks if the permission is a valid system permission
func (p Permission) IsValid() bool {
	switch p {
	case CreateTenantUser, CreateAllUsers, ReadOwnProfile, ReadTenantUsers, ReadAllUsers,
		UpdateOwnProfile, UpdateTenantUsers, UpdateAllUsers, DeleteTenantUsers, DeleteAllUsers,
		ChangeOwnPassword, ChangeTenantUserPassword, ChangeUserPassword, UpdateOwnEmail, UpdateTenantUserEmail, UpdateUserEmail,
		ViewOwnSessions, ViewTenantSessions, ViewAllSessions, TerminateOwnSessions, TerminateTenantSessions, TerminateAllSessions,
		CreateTenant, ReadOwnTenant, ReadAllTenants, UpdateTenant,
		ManageTenantStatus,
		CreateFeatureFlag, ReadFeatureFlag, UpdateFeatureFlag, DeleteFeatureFlag,
		ViewPermissions, ManagePermissions,
		ViewAuditLog:
		return true
	default:
		return false
	}
}

// GetAllPermissions returns all available permissions in the system
func GetAllPermissions() []Permission {
	return []Permission{
		// User Management
		CreateTenantUser,
		CreateAllUsers,
		ReadOwnProfile,
		ReadTenantUsers,
		ReadAllUsers,
		UpdateOwnProfile,
		UpdateTenantUsers,
		UpdateAllUsers,
		DeleteTenantUsers,
		DeleteAllUsers,
		ChangeOwnPassword,
		ChangeTenantUserPassword,
		ChangeUserPassword,
		UpdateOwnEmail,
		UpdateTenantUserEmail,
		UpdateUserEmail,

		// Session Management
		ViewOwnSessions,
		ViewTenantSessions,
		ViewAllSessions,
		TerminateOwnSessions,
		TerminateTenantSessions,
		TerminateAllSessions,

		// Tenant Management
		CreateTenant,
		ReadOwnTenant,
		ReadAllTenants,
		UpdateTenant,
		ManageTenantStatus,

		// Feature Flags
		CreateFeatureFlag,
		ReadFeatureFlag,
		UpdateFeatureFlag,
		DeleteFeatureFlag,

		// Permission Management
		ViewPermissions,
		ManagePermissions,

		// Audit & Monitoring
		ViewAuditLog,
	}
}

// AddPermissionToRoleRequest represents the request to add a permission to a role
type AddPermissionToRoleRequest struct {
	Role       user.UserRole `json:"role" validate:"required"`
	Permission Permission    `json:"permission" validate:"required"`
}

// RemovePermissionFromRoleRequest represents the request to remove a permission from a role
type RemovePermissionFromRoleRequest struct {
	Role       user.UserRole `json:"role" validate:"required"`
	Permission Permission    `json:"permission" validate:"required"`
}

// SetRolePermissionsRequest represents the request to set all permissions for a role
type SetRolePermissionsRequest struct {
	Role        user.UserRole `json:"role" validate:"required"`
	Permissions []Permission  `json:"permissions" validate:"required"`
}

// GetRolePermissionsResponse represents the response for getting role permissions
type GetRolePermissionsResponse struct {
	Role        user.UserRole `json:"role"`
	Permissions []Permission  `json:"permissions"`
}

// PermissionCategoryResponse represents a categorized group of permissions
type PermissionCategoryResponse struct {
	UserManagement       []Permission `json:"user_management"`
	SessionManagement    []Permission `json:"session_management"`
	TenantManagement     []Permission `json:"tenant_management"`
	FeatureFlags         []Permission `json:"feature_flags"`
	PermissionManagement []Permission `json:"permission_management"`
	AuditMonitoring      []Permission `json:"audit_monitoring"`
}

// GetAvailablePermissionsResponse represents the response for getting all available permissions
type GetAvailablePermissionsResponse struct {
	Permissions            []Permission               `json:"permissions"`
	CategorizedPermissions PermissionCategoryResponse `json:"categorized_permissions"`
}
