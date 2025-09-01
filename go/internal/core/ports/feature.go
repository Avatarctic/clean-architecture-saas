package ports

import (
	"context"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/feature"
	"github.com/google/uuid"
)

// FeatureFlagRepository defines the interface for feature flag data operations
type FeatureFlagRepository interface {
	Create(ctx context.Context, flag *feature.FeatureFlag) error
	GetByID(ctx context.Context, id uuid.UUID) (*feature.FeatureFlag, error)
	GetByKey(ctx context.Context, key string) (*feature.FeatureFlag, error)
	Update(ctx context.Context, flag *feature.FeatureFlag) error
	Delete(ctx context.Context, id uuid.UUID) error
	List(ctx context.Context, limit, offset int) ([]*feature.FeatureFlag, error)
	Count(ctx context.Context) (int, error)
}

// FeatureFlagService defines the interface for feature flag business logic
type FeatureFlagService interface {
	CreateFeatureFlag(ctx context.Context, req *feature.CreateFeatureFlagRequest) (*feature.FeatureFlag, error)
	UpdateFeatureFlag(ctx context.Context, id uuid.UUID, req *feature.UpdateFeatureFlagRequest) (*feature.FeatureFlag, error)
	DeleteFeatureFlag(ctx context.Context, id uuid.UUID) error
	ListFeatureFlags(ctx context.Context, limit, offset int) ([]*feature.FeatureFlag, int, error)
	IsFeatureEnabled(ctx context.Context, key string, context *feature.FeatureFlagContext) (bool, error)
	GetFeatureValue(ctx context.Context, key string, context *feature.FeatureFlagContext) (any, error)
}
