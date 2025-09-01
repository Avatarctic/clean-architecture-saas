package services

import (
	"context"
	"slices"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/permission"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/sirupsen/logrus"
)

type PermissionService struct {
	repo   ports.PermissionRepository
	logger *logrus.Logger
}

func NewPermissionService(repo ports.PermissionRepository, logger *logrus.Logger) ports.PermissionService {
	return &PermissionService{
		repo:   repo,
		logger: logger,
	}
}

// GetRolePermissions returns all permissions for a given role
func (s *PermissionService) GetRolePermissions(ctx context.Context, role user.UserRole) ([]permission.Permission, error) {
	perms, err := s.repo.GetRolePermissions(ctx, role)
	if err != nil {
		if s.logger != nil {
			s.logger.WithFields(logrus.Fields{"role": role}).WithError(err).Error("failed to get role permissions")
		}
		return nil, err
	}
	if s.logger != nil {
		s.logger.WithFields(logrus.Fields{"role": role, "count": len(perms)}).Debug("retrieved role permissions")
	}
	return perms, nil
}

// HasPermission checks if a permission exists in a slice of permissions
// This is a helper method for in-memory permission checking
func (s *PermissionService) HasPermission(permissions []permission.Permission, targetPermission permission.Permission) bool {
	return slices.Contains(permissions, targetPermission)
}

// HasAnyPermission checks if any of the target permissions exist in the permissions slice
func (s *PermissionService) HasAnyPermission(permissions []permission.Permission, targetPermissions ...permission.Permission) bool {
	for _, targetPerm := range targetPermissions {
		if s.HasPermission(permissions, targetPerm) {
			return true
		}
	}
	return false
}

// HasAllPermissions checks if all target permissions exist in the permissions slice
func (s *PermissionService) HasAllPermissions(permissions []permission.Permission, targetPermissions ...permission.Permission) bool {
	for _, targetPerm := range targetPermissions {
		if !s.HasPermission(permissions, targetPerm) {
			return false
		}
	}
	return true
}

// AddPermissionToRole adds a permission to a role
func (s *PermissionService) AddPermissionToRole(ctx context.Context, role user.UserRole, perm permission.Permission) error {
	if err := s.repo.AddPermissionToRole(ctx, role, perm); err != nil {
		if s.logger != nil {
			s.logger.WithFields(logrus.Fields{"role": role, "permission": perm}).WithError(err).Error("failed to add permission to role")
		}
		return err
	}
	if s.logger != nil {
		s.logger.WithFields(logrus.Fields{"role": role, "permission": perm}).Info("permission added to role")
	}
	return nil
}

// RemovePermissionFromRole removes a permission from a role
func (s *PermissionService) RemovePermissionFromRole(ctx context.Context, role user.UserRole, perm permission.Permission) error {
	if err := s.repo.RemovePermissionFromRole(ctx, role, perm); err != nil {
		if s.logger != nil {
			s.logger.WithFields(logrus.Fields{"role": role, "permission": perm}).WithError(err).Error("failed to remove permission from role")
		}
		return err
	}
	if s.logger != nil {
		s.logger.WithFields(logrus.Fields{"role": role, "permission": perm}).Info("permission removed from role")
	}
	return nil
}

// SetRolePermissions replaces all permissions for a role
func (s *PermissionService) SetRolePermissions(ctx context.Context, role user.UserRole, permissions []permission.Permission) error {
	if err := s.repo.SetRolePermissions(ctx, role, permissions); err != nil {
		if s.logger != nil {
			s.logger.WithFields(logrus.Fields{"role": role, "permissions": permissions}).WithError(err).Error("failed to set role permissions")
		}
		return err
	}
	if s.logger != nil {
		s.logger.WithFields(logrus.Fields{"role": role, "permissions_count": len(permissions)}).Info("role permissions set")
	}
	return nil
}

// ValidatePermission checks if a permission exists in the system
func (s *PermissionService) ValidatePermission(perm permission.Permission) bool {
	return perm.IsValid()
}

// GetAvailablePermissions returns all available permissions in the system
func (s *PermissionService) GetAvailablePermissions() []permission.Permission {
	return permission.GetAllPermissions()
}
