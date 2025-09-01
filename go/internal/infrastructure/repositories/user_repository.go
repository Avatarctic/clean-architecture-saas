package repositories

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/db"
	"github.com/google/uuid"
	"github.com/sirupsen/logrus"
)

// UserRepository implements the user repository interface
type UserRepository struct {
	db     *db.Database
	logger *logrus.Logger
}

// NewUserRepository creates a new user repository
func NewUserRepository(database *db.Database, logger *logrus.Logger) ports.UserRepository {
	return &UserRepository{
		db:     database,
		logger: logger,
	}
}

// Create creates a new user
func (r *UserRepository) Create(ctx context.Context, u *user.User) error {
	query := `
		INSERT INTO users (id, email, password_hash, first_name, last_name, role, tenant_id, is_active, email_verified, audit_enabled)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`

	_, err := r.db.DB.ExecContext(ctx, query,
		u.ID, u.Email, u.PasswordHash, u.FirstName, u.LastName, u.Role,
		u.TenantID, u.IsActive, u.EmailVerified, u.AuditEnabled)
	if err != nil {
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"user_id": u.ID, "email": u.Email}).WithError(err).Error("db: failed to create user")
		}
		return fmt.Errorf("failed to create user: %w", err)
	}
	if r.logger != nil {
		r.logger.WithFields(logrus.Fields{"user_id": u.ID, "email": u.Email}).Info("db: user created")
	}

	return nil
}

// GetByID retrieves a user by ID
func (r *UserRepository) GetByID(ctx context.Context, id uuid.UUID) (*user.User, error) {
	var u user.User
	query := `
		SELECT id, email, password_hash, first_name, last_name, role, tenant_id, 
			   is_active, email_verified, audit_enabled, last_login_at, created_at, updated_at
		FROM users 
		WHERE id = $1`

	err := r.db.DB.GetContext(ctx, &u, query, id)
	if err != nil {
		if err == sql.ErrNoRows {
			if r.logger != nil {
				r.logger.WithFields(logrus.Fields{"user_id": id}).Debug("db: user not found by ID")
			}
			return nil, fmt.Errorf("user with ID %s not found", id)
		}
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"user_id": id}).WithError(err).Error("db: failed to get user by ID")
		}
		return nil, fmt.Errorf("failed to get user by ID: %w", err)
	}

	return &u, nil
}

// GetByEmail retrieves a user by email
func (r *UserRepository) GetByEmail(ctx context.Context, email string) (*user.User, error) {
	var u user.User
	query := `
		SELECT id, email, password_hash, first_name, last_name, role, tenant_id, 
			   is_active, email_verified, audit_enabled, last_login_at, created_at, updated_at
		FROM users 
		WHERE email = $1`

	err := r.db.DB.GetContext(ctx, &u, query, email)
	if err != nil {
		if err == sql.ErrNoRows {
			if r.logger != nil {
				r.logger.WithFields(logrus.Fields{"email": email}).Debug("db: user not found by email")
			}
			return nil, fmt.Errorf("user with email %s not found", email)
		}
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"email": email}).WithError(err).Error("db: failed to get user by email")
		}
		return nil, fmt.Errorf("failed to get user by email: %w", err)
	}

	return &u, nil
}

// Update updates an existing user
func (r *UserRepository) Update(ctx context.Context, u *user.User) error {
	query := `
		UPDATE users 
		SET email = $2, password_hash = $3, first_name = $4, last_name = $5, 
			role = $6, is_active = $7, email_verified = $8, audit_enabled = $9, last_login_at = $10, updated_at = $11
		WHERE id = $1`

	result, err := r.db.DB.ExecContext(ctx, query,
		u.ID, u.Email, u.PasswordHash, u.FirstName, u.LastName, u.Role,
		u.IsActive, u.EmailVerified, u.AuditEnabled, u.LastLoginAt, u.UpdatedAt)
	if err != nil {
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"user_id": u.ID}).WithError(err).Error("db: failed to update user")
		}
		return fmt.Errorf("failed to update user: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"user_id": u.ID}).WithError(err).Error("db: failed to get rows affected on update")
		}
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"user_id": u.ID}).Debug("db: update affected 0 rows - user not found")
		}
		return fmt.Errorf("user with ID %s not found", u.ID)
	}

	return nil
}

// Delete deletes a user by ID
func (r *UserRepository) Delete(ctx context.Context, id uuid.UUID) error {
	query := `DELETE FROM users WHERE id = $1`

	result, err := r.db.DB.ExecContext(ctx, query, id)
	if err != nil {
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"user_id": id}).WithError(err).Error("db: failed to delete user")
		}
		return fmt.Errorf("failed to delete user: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"user_id": id}).WithError(err).Error("db: failed to get rows affected on delete")
		}
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"user_id": id}).Debug("db: delete affected 0 rows - user not found")
		}
		return fmt.Errorf("user with ID %s not found", id)
	}

	return nil
}

// List retrieves users for a tenant with pagination
func (r *UserRepository) List(ctx context.Context, tenantID uuid.UUID, limit, offset int) ([]*user.User, error) {
	var users []*user.User
	query := `
		SELECT id, email, password_hash, first_name, last_name, role, tenant_id, 
		       is_active, email_verified, last_login_at, created_at, updated_at
		FROM users 
		WHERE tenant_id = $1
		ORDER BY created_at DESC
		LIMIT $2 OFFSET $3`

	err := r.db.DB.SelectContext(ctx, &users, query, tenantID, limit, offset)
	if err != nil {
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"tenant_id": tenantID}).WithError(err).Error("db: failed to list users")
		}
		return nil, fmt.Errorf("failed to list users: %w", err)
	}

	return users, nil
}

// Count returns the total number of users for a tenant
func (r *UserRepository) Count(ctx context.Context, tenantID uuid.UUID) (int, error) {
	var count int
	query := `SELECT COUNT(*) FROM users WHERE tenant_id = $1`

	err := r.db.DB.GetContext(ctx, &count, query, tenantID)
	if err != nil {
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"tenant_id": tenantID}).WithError(err).Error("db: failed to count users")
		}
		return 0, fmt.Errorf("failed to count users: %w", err)
	}

	return count, nil
}
