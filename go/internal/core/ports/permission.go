package ports

import (
	"context"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/permission"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
)

// PermissionRepository defines the interface for permission data operations
type PermissionRepository interface {
	// Role permission operations
	GetRolePermissions(ctx context.Context, role user.UserRole) ([]permission.Permission, error)
	AddPermissionToRole(ctx context.Context, role user.UserRole, perm permission.Permission) error
	RemovePermissionFromRole(ctx context.Context, role user.UserRole, perm permission.Permission) error
	SetRolePermissions(ctx context.Context, role user.UserRole, permissions []permission.Permission) error
}

// PermissionService defines the interface for permission business logic
type PermissionService interface {
	// Role permission operations
	GetRolePermissions(ctx context.Context, role user.UserRole) ([]permission.Permission, error)
	AddPermissionToRole(ctx context.Context, role user.UserRole, perm permission.Permission) error
	RemovePermissionFromRole(ctx context.Context, role user.UserRole, perm permission.Permission) error
	SetRolePermissions(ctx context.Context, role user.UserRole, permissions []permission.Permission) error

	// In-memory permission checking (for cached permissions)
	HasPermission(permissions []permission.Permission, targetPermission permission.Permission) bool
	HasAnyPermission(permissions []permission.Permission, targetPermissions ...permission.Permission) bool
	HasAllPermissions(permissions []permission.Permission, targetPermissions ...permission.Permission) bool

	// Validation and available permissions
	ValidatePermission(perm permission.Permission) bool
	GetAvailablePermissions() []permission.Permission
}
