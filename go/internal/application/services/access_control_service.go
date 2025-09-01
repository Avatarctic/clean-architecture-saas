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
	checkAllOrTenant := func(allPerm, tenantPerm permission.Permission, insuffMsg string) error {
		if a.permissionSvc.HasPermission(actorPermissions, allPerm) {
			return nil
		}
		if a.permissionSvc.HasPermission(actorPermissions, tenantPerm) {
			if actorTenantID == targetUser.TenantID {
				return nil
			}
			return ports.NewAccessControlError(ports.ACCodeForbidden, "actor not in same tenant")
		}
		return ports.NewAccessControlError(ports.ACCodeForbidden, insuffMsg)
	}

	// Table-driven mapping from action to permission pair and message reduces
	// cyclomatic complexity compared to a large switch with repeated logic.
	actionMap := map[ports.AccessAction]struct {
		allPerm    permission.Permission
		tenantPerm permission.Permission
		message    string
	}{
		ports.AccessActionReadUser:       {permission.ReadAllUsers, permission.ReadTenantUsers, "insufficient permissions: read tenant or all users"},
		ports.AccessActionUpdateUser:     {permission.UpdateAllUsers, permission.UpdateTenantUsers, "insufficient permissions: update tenant or all users"},
		ports.AccessActionDeleteUser:     {permission.DeleteAllUsers, permission.DeleteTenantUsers, "insufficient permissions: delete tenant or all users"},
		ports.AccessActionChangePassword: {permission.ChangeUserPassword, permission.ChangeTenantUserPassword, "insufficient permissions: change password for tenant or all users"},
		ports.AccessActionUpdateEmail:    {permission.UpdateUserEmail, permission.UpdateTenantUserEmail, "insufficient permissions: update email for tenant or all users"},
	}

	if m, ok := actionMap[action]; ok {
		return checkAllOrTenant(m.allPerm, m.tenantPerm, m.message)
	}
	return nil
}
