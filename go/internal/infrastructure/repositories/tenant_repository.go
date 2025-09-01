package repositories

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/tenant"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/db"
	"github.com/google/uuid"
	"github.com/sirupsen/logrus"
)

// TenantRepository implements the tenant repository interface
type TenantRepository struct {
	db     *db.Database
	logger *logrus.Logger
}

// NewTenantRepository creates a new tenant repository
func NewTenantRepository(database *db.Database, logger *logrus.Logger) ports.TenantRepository {
	return &TenantRepository{
		db:     database,
		logger: logger,
	}
}

// Create creates a new tenant
func (r *TenantRepository) Create(ctx context.Context, t *tenant.Tenant) error {
	query := `
		INSERT INTO tenants (id, name, slug, domain, plan, status, settings)
		VALUES ($1, $2, $3, $4, $5, $6, $7)`

	settingsJSON, err := json.Marshal(t.Settings)
	if err != nil {
		return fmt.Errorf("failed to marshal settings: %w", err)
	}

	_, err = r.db.DB.ExecContext(ctx, query,
		t.ID, t.Name, t.Slug, t.Domain, t.Plan, t.Status, settingsJSON)
	if err != nil {
		return fmt.Errorf("failed to create tenant: %w", err)
	}

	return nil
}

// GetByID retrieves a tenant by ID
func (r *TenantRepository) GetByID(ctx context.Context, id uuid.UUID) (*tenant.Tenant, error) {
	var t tenant.Tenant
	var settingsJSON sql.NullString

	query := `
		SELECT id, name, slug, domain, plan, status, settings, created_at, updated_at
		FROM tenants 
		WHERE id = $1`

	err := r.db.DB.QueryRowContext(ctx, query, id).Scan(
		&t.ID, &t.Name, &t.Slug, &t.Domain, &t.Plan, &t.Status,
		&settingsJSON, &t.CreatedAt, &t.UpdatedAt,
	)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("tenant not found")
		}
		return nil, fmt.Errorf("failed to get tenant: %w", err)
	}

	// Parse settings JSON if present
	if settingsJSON.Valid && settingsJSON.String != "" {
		if err := json.Unmarshal([]byte(settingsJSON.String), &t.Settings); err != nil {
			return nil, fmt.Errorf("failed to parse settings: %w", err)
		}
	}

	return &t, nil
}

// GetBySlug retrieves a tenant by slug
func (r *TenantRepository) GetBySlug(ctx context.Context, slug string) (*tenant.Tenant, error) {
	var t tenant.Tenant
	var settingsJSON sql.NullString

	query := `
		SELECT id, name, slug, domain, plan, status, settings, created_at, updated_at
		FROM tenants 
		WHERE slug = $1`

	err := r.db.DB.QueryRowContext(ctx, query, slug).Scan(
		&t.ID, &t.Name, &t.Slug, &t.Domain, &t.Plan, &t.Status,
		&settingsJSON, &t.CreatedAt, &t.UpdatedAt,
	)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("tenant not found")
		}
		return nil, fmt.Errorf("failed to get tenant: %w", err)
	}

	// Parse settings JSON if present
	if settingsJSON.Valid && settingsJSON.String != "" {
		if err := json.Unmarshal([]byte(settingsJSON.String), &t.Settings); err != nil {
			return nil, fmt.Errorf("failed to parse settings: %w", err)
		}
	}

	return &t, nil
}

// Update updates an existing tenant
func (r *TenantRepository) Update(ctx context.Context, t *tenant.Tenant) error {
	settingsJSON, err := json.Marshal(t.Settings)
	if err != nil {
		return fmt.Errorf("failed to marshal settings: %w", err)
	}

	query := `
		UPDATE tenants 
		SET name = $2, slug = $3, domain = $4, plan = $5, status = $6, settings = $7
		WHERE id = $1`

	result, err := r.db.DB.ExecContext(ctx, query,
		t.ID, t.Name, t.Slug, t.Domain, t.Plan, t.Status, settingsJSON)
	if err != nil {
		return fmt.Errorf("failed to update tenant: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("tenant not found")
	}

	return nil
}

// Delete removes a tenant
func (r *TenantRepository) Delete(ctx context.Context, id uuid.UUID) error {
	query := `DELETE FROM tenants WHERE id = $1`

	result, err := r.db.DB.ExecContext(ctx, query, id)
	if err != nil {
		return fmt.Errorf("failed to delete tenant: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("tenant not found")
	}

	return nil
}

// List retrieves tenants with pagination
func (r *TenantRepository) List(ctx context.Context, limit, offset int) ([]*tenant.Tenant, error) {
	query := `
		SELECT id, name, slug, domain, plan, status, settings, created_at, updated_at
		FROM tenants 
		ORDER BY created_at DESC
		LIMIT $1 OFFSET $2`

	rows, err := r.db.DB.QueryContext(ctx, query, limit, offset)
	if err != nil {
		return nil, fmt.Errorf("failed to list tenants: %w", err)
	}
	defer rows.Close()

	var tenants []*tenant.Tenant
	for rows.Next() {
		t := &tenant.Tenant{}
		var settingsJSON sql.NullString

		err := rows.Scan(
			&t.ID, &t.Name, &t.Slug, &t.Domain, &t.Plan, &t.Status,
			&settingsJSON, &t.CreatedAt, &t.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan tenant: %w", err)
		}

		// Parse settings JSON if present
		if settingsJSON.Valid && settingsJSON.String != "" {
			if err := json.Unmarshal([]byte(settingsJSON.String), &t.Settings); err != nil {
				return nil, fmt.Errorf("failed to parse settings: %w", err)
			}
		}

		tenants = append(tenants, t)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("failed to iterate tenants: %w", err)
	}

	return tenants, nil
}

// Count returns the total number of tenants
func (r *TenantRepository) Count(ctx context.Context) (int, error) {
	var count int
	query := `SELECT COUNT(*) FROM tenants`

	err := r.db.DB.GetContext(ctx, &count, query)
	if err != nil {
		return 0, fmt.Errorf("failed to count tenants: %w", err)
	}

	return count, nil
}
