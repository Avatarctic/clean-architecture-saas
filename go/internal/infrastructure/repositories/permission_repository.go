package repositories

import (
	"context"
	"fmt"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/permission"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/db"
	"github.com/sirupsen/logrus"
)

// PermissionRepository implements the permission repository interface
type PermissionRepository struct {
	db     *db.Database
	logger *logrus.Logger
}

// NewPermissionRepository creates a new permission repository
func NewPermissionRepository(database *db.Database, logger *logrus.Logger) ports.PermissionRepository {
	return &PermissionRepository{
		db:     database,
		logger: logger,
	}
}

// GetRolePermissions returns all permissions for a given role
func (r *PermissionRepository) GetRolePermissions(ctx context.Context, role user.UserRole) ([]permission.Permission, error) {
	query := `
		SELECT permission 
		FROM role_permissions 
		WHERE role = $1
		ORDER BY permission`

	var permissions []permission.Permission
	err := r.db.DB.SelectContext(ctx, &permissions, query, role)
	if err != nil {
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"role": role}).WithError(err).Error("db: failed to get permissions for role")
		}
		return nil, fmt.Errorf("failed to get permissions for role %s: %w", role, err)
	}

	return permissions, nil
}

// AddPermissionToRole adds a permission to a role
func (r *PermissionRepository) AddPermissionToRole(ctx context.Context, role user.UserRole, perm permission.Permission) error {
	query := `
		INSERT INTO role_permissions (role, permission) 
		VALUES ($1, $2)
		ON CONFLICT (role, permission) DO NOTHING`

	_, err := r.db.DB.ExecContext(ctx, query, role, perm)
	if err != nil {
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"role": role, "permission": perm}).WithError(err).Error("db: failed to add permission to role")
		}
		return fmt.Errorf("failed to add permission %s to role %s: %w", perm, role, err)
	}
	if r.logger != nil {
		r.logger.WithFields(logrus.Fields{"role": role, "permission": perm}).Info("db: permission added to role")
	}

	return nil
}

// RemovePermissionFromRole removes a permission from a role
func (r *PermissionRepository) RemovePermissionFromRole(ctx context.Context, role user.UserRole, perm permission.Permission) error {
	query := `
		DELETE FROM role_permissions 
		WHERE role = $1 AND permission = $2`

	result, err := r.db.DB.ExecContext(ctx, query, role, perm)
	if err != nil {
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"role": role, "permission": perm}).WithError(err).Error("db: failed to remove permission from role")
		}
		return fmt.Errorf("failed to remove permission %s from role %s: %w", perm, role, err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("permission %s not found for role %s", perm, role)
	}

	return nil
}

// SetRolePermissions replaces all permissions for a role
func (r *PermissionRepository) SetRolePermissions(ctx context.Context, role user.UserRole, permissions []permission.Permission) error {
	tx, err := r.db.DB.BeginTxx(ctx, nil)
	if err != nil {
		if r.logger != nil {
			r.logger.WithError(err).Error("db: failed to begin transaction for set role permissions")
		}
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() {
		_ = tx.Rollback()
	}()

	// Remove all existing permissions for the role
	_, err = tx.ExecContext(ctx, "DELETE FROM role_permissions WHERE role = $1", role)
	if err != nil {
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"role": role}).WithError(err).Error("db: failed to delete existing permissions for role")
		}
		return fmt.Errorf("failed to delete existing permissions for role %s: %w", role, err)
	}

	// Add new permissions
	for _, perm := range permissions {
		_, err = tx.ExecContext(ctx,
			"INSERT INTO role_permissions (role, permission) VALUES ($1, $2)",
			role, perm)
		if err != nil {
			if r.logger != nil {
				r.logger.WithFields(logrus.Fields{"role": role, "permission": perm}).WithError(err).Error("db: failed to insert permission for role")
			}
			return fmt.Errorf("failed to insert permission %s for role %s: %w", perm, role, err)
		}
	}

	err = tx.Commit()
	if err != nil {
		if r.logger != nil {
			r.logger.WithError(err).Error("db: failed to commit transaction for set role permissions")
		}
		return fmt.Errorf("failed to commit transaction: %w", err)
	}
	if r.logger != nil {
		r.logger.WithFields(logrus.Fields{"role": role, "permissions_count": len(permissions)}).Info("db: role permissions set")
	}

	return nil
}
