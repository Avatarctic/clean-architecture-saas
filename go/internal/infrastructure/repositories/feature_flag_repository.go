package repositories

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/feature"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/db"
	"github.com/google/uuid"
)

// FeatureFlagRepository implements the feature flag repository interface
type FeatureFlagRepository struct {
	db *db.Database
}

// NewFeatureFlagRepository creates a new feature flag repository
func NewFeatureFlagRepository(database *db.Database) ports.FeatureFlagRepository {
	return &FeatureFlagRepository{
		db: database,
	}
}

// Create creates a new feature flag
func (r *FeatureFlagRepository) Create(ctx context.Context, flag *feature.FeatureFlag) error {
	query := `
		INSERT INTO feature_flags (id, name, key, description, type, is_enabled, enabled_value, default_value, rules, rollout)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`

	_, err := r.db.DB.ExecContext(ctx, query,
		flag.ID, flag.Name, flag.Key, flag.Description, flag.Type, flag.IsEnabled,
		flag.EnabledValue, flag.DefaultValue, flag.Rules, flag.Rollout)
	if err != nil {
		return fmt.Errorf("failed to create feature flag: %w", err)
	}

	return nil
}

// GetByID retrieves a feature flag by ID
func (r *FeatureFlagRepository) GetByID(ctx context.Context, id uuid.UUID) (*feature.FeatureFlag, error) {
	var flag feature.FeatureFlag
	query := `
		SELECT id, name, key, description, type, is_enabled, enabled_value, default_value, rules, rollout, created_at, updated_at
		FROM feature_flags 
		WHERE id = $1`

	err := r.db.DB.GetContext(ctx, &flag, query, id)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("feature flag with ID %s not found", id)
		}
		return nil, fmt.Errorf("failed to get feature flag by ID: %w", err)
	}

	return &flag, nil
}

// GetByKey retrieves a feature flag by key
func (r *FeatureFlagRepository) GetByKey(ctx context.Context, key string) (*feature.FeatureFlag, error) {
	var flag feature.FeatureFlag
	query := `
		SELECT id, name, key, description, type, is_enabled, enabled_value, default_value, rules, rollout, created_at, updated_at
		FROM feature_flags 
		WHERE key = $1`

	err := r.db.DB.GetContext(ctx, &flag, query, key)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("feature flag with key %s not found", key)
		}
		return nil, fmt.Errorf("failed to get feature flag by key: %w", err)
	}

	return &flag, nil
}

// Update updates an existing feature flag
func (r *FeatureFlagRepository) Update(ctx context.Context, flag *feature.FeatureFlag) error {
	query := `
		UPDATE feature_flags 
		SET name = $2, key = $3, description = $4, type = $5, is_enabled = $6, 
		    enabled_value = $7, default_value = $8, rules = $9, rollout = $10, updated_at = $11
		WHERE id = $1`

	result, err := r.db.DB.ExecContext(ctx, query,
		flag.ID, flag.Name, flag.Key, flag.Description, flag.Type, flag.IsEnabled,
		flag.EnabledValue, flag.DefaultValue, flag.Rules, flag.Rollout, flag.UpdatedAt)
	if err != nil {
		return fmt.Errorf("failed to update feature flag: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("feature flag with ID %s not found", flag.ID)
	}

	return nil
}

// Delete deletes a feature flag by ID
func (r *FeatureFlagRepository) Delete(ctx context.Context, id uuid.UUID) error {
	query := `DELETE FROM feature_flags WHERE id = $1`

	result, err := r.db.DB.ExecContext(ctx, query, id)
	if err != nil {
		return fmt.Errorf("failed to delete feature flag: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("feature flag with ID %s not found", id)
	}

	return nil
}

// List retrieves feature flags with pagination
func (r *FeatureFlagRepository) List(ctx context.Context, limit, offset int) ([]*feature.FeatureFlag, error) {
	var flags []*feature.FeatureFlag
	query := `
		SELECT id, name, key, description, type, is_enabled, enabled_value, default_value, rules, rollout, created_at, updated_at
		FROM feature_flags 
		ORDER BY created_at DESC
		LIMIT $1 OFFSET $2`

	err := r.db.DB.SelectContext(ctx, &flags, query, limit, offset)
	if err != nil {
		return nil, fmt.Errorf("failed to list feature flags: %w", err)
	}

	return flags, nil
}

// Count returns the total number of feature flags
func (r *FeatureFlagRepository) Count(ctx context.Context) (int, error) {
	var count int
	query := `SELECT COUNT(*) FROM feature_flags`

	err := r.db.DB.GetContext(ctx, &count, query)
	if err != nil {
		return 0, fmt.Errorf("failed to count feature flags: %w", err)
	}

	return count, nil
}
