package services

import (
	"context"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/permission"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/google/uuid"
)

// AccessControlService implements ports.AccessControlService
type AccessControlService struct {
	userSvc       ports.UserService
	tenantSvc     ports.TenantService
	permissionSvc ports.PermissionService
}

func NewAccessControlService(userSvc ports.UserService, tenantSvc ports.TenantService, permissionSvc ports.PermissionService) ports.AccessControlService {
	return &AccessControlService{
		userSvc:       userSvc,
		tenantSvc:     tenantSvc,
		permissionSvc: permissionSvc,
	}
}

// CanPerformAction enforces simple same-tenant vs cross-tenant permission checks.
func (a *AccessControlService) CanPerformAction(ctx context.Context, actorID uuid.UUID, actorTenantID uuid.UUID, actorPermissions []permission.Permission, targetUserID uuid.UUID, action ports.AccessAction) error {
	// Load target user
	targetUser, err := a.userSvc.GetUser(ctx, targetUserID)
	if err != nil {
		return ports.NewAccessControlError(ports.ACCodeNotFound, "target user not found")
	}
	return a.CanPerformActionWithTarget(ctx, actorID, actorTenantID, actorPermissions, targetUser, action)
}

// CanPerformActionWithTarget performs the authorization check using a preloaded target user
func (a *AccessControlService) CanPerformActionWithTarget(ctx context.Context, actorID uuid.UUID, actorTenantID uuid.UUID, actorPermissions []permission.Permission, targetUser *user.User, action ports.AccessAction) error {
	// If acting on self and own-permission exists, allow immediately.
	if actorID == targetUser.ID {
		switch action {
		case ports.AccessActionReadUser:
			if a.permissionSvc.HasPermission(actorPermissions, permission.ReadOwnProfile) {
				return nil
			}
		case ports.AccessActionUpdateUser:
			if a.permissionSvc.HasPermission(actorPermissions, permission.UpdateOwnProfile) {
				return nil
			}
		case ports.AccessActionChangePassword:
			if a.permissionSvc.HasPermission(actorPermissions, permission.ChangeOwnPassword) {
				return nil
			}
		}
		// If own-permission wasn't present, fall through to check elevated/tenant permissions
	}

	// General permission checks (applies to same-actor and different-actor cases).
	switch action {
	case ports.AccessActionReadUser:
		if a.permissionSvc.HasPermission(actorPermissions, permission.ReadAllUsers) {
			return nil
		}
		if a.permissionSvc.HasPermission(actorPermissions, permission.ReadTenantUsers) {
			if actorTenantID == targetUser.TenantID {
				return nil
			}
			return ports.NewAccessControlError(ports.ACCodeForbidden, "actor not in same tenant")
		}
		return ports.NewAccessControlError(ports.ACCodeForbidden, "insufficient permissions: read tenant or all users")

	case ports.AccessActionUpdateUser:
		if a.permissionSvc.HasPermission(actorPermissions, permission.UpdateAllUsers) {
			return nil
		}
		if a.permissionSvc.HasPermission(actorPermissions, permission.UpdateTenantUsers) {
			if actorTenantID == targetUser.TenantID {
				return nil
			}
			return ports.NewAccessControlError(ports.ACCodeForbidden, "actor not in same tenant")
		}
		return ports.NewAccessControlError(ports.ACCodeForbidden, "insufficient permissions: update tenant or all users")

	case ports.AccessActionDeleteUser:
		if a.permissionSvc.HasPermission(actorPermissions, permission.DeleteAllUsers) {
			return nil
		}
		if a.permissionSvc.HasPermission(actorPermissions, permission.DeleteTenantUsers) {
			if actorTenantID == targetUser.TenantID {
				return nil
			}
			return ports.NewAccessControlError(ports.ACCodeForbidden, "actor not in same tenant")
		}
		return ports.NewAccessControlError(ports.ACCodeForbidden, "insufficient permissions: delete tenant or all users")

	case ports.AccessActionChangePassword:
		if a.permissionSvc.HasPermission(actorPermissions, permission.ChangeUserPassword) {
			return nil
		}
		if a.permissionSvc.HasPermission(actorPermissions, permission.ChangeTenantUserPassword) {
			if actorTenantID == targetUser.TenantID {
				return nil
			}
			return ports.NewAccessControlError(ports.ACCodeForbidden, "actor not in same tenant")
		}
		return ports.NewAccessControlError(ports.ACCodeForbidden, "insufficient permissions: change password for tenant or all users")

	case ports.AccessActionUpdateEmail:
		if a.permissionSvc.HasPermission(actorPermissions, permission.UpdateUserEmail) {
			return nil
		}
		if a.permissionSvc.HasPermission(actorPermissions, permission.UpdateTenantUserEmail) {
			if actorTenantID == targetUser.TenantID {
				return nil
			}
			return ports.NewAccessControlError(ports.ACCodeForbidden, "actor not in same tenant")
		}
		return ports.NewAccessControlError(ports.ACCodeForbidden, "insufficient permissions: update email for tenant or all users")

	default:
		return nil
	}
}
