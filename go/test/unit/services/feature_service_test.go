package services_test

import (
	"context"
	"errors"
	"testing"

	impl "github.com/avatarctic/clean-architecture-saas/go/internal/application/services"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/feature"
	"github.com/google/uuid"
)

type ffRepoMock struct {
	createFn   func(ctx context.Context, f *feature.FeatureFlag) error
	getByKeyFn func(ctx context.Context, key string) (*feature.FeatureFlag, error)
}

func (m *ffRepoMock) Create(ctx context.Context, f *feature.FeatureFlag) error {
	if m.createFn != nil {
		return m.createFn(ctx, f)
	}
	return nil
}
func (m *ffRepoMock) GetByID(ctx context.Context, id uuid.UUID) (*feature.FeatureFlag, error) {
	return nil, errors.New("not found")
}
func (m *ffRepoMock) GetByKey(ctx context.Context, key string) (*feature.FeatureFlag, error) {
	if m.getByKeyFn != nil {
		return m.getByKeyFn(ctx, key)
	}
	return nil, errors.New("not found")
}
func (m *ffRepoMock) Update(ctx context.Context, f *feature.FeatureFlag) error { return nil }
func (m *ffRepoMock) Delete(ctx context.Context, id uuid.UUID) error {
	return nil
}
func (m *ffRepoMock) List(ctx context.Context, limit, offset int) ([]*feature.FeatureFlag, error) {
	return nil, nil
}
func (m *ffRepoMock) Count(ctx context.Context) (int, error) { return 0, nil }

func TestCreateFeatureFlag_KeyTaken(t *testing.T) {
	repo := &ffRepoMock{getByKeyFn: func(ctx context.Context, key string) (*feature.FeatureFlag, error) {
		return &feature.FeatureFlag{}, nil
	}}
	svc := impl.NewFeatureFlagService(repo)
	_, err := svc.CreateFeatureFlag(context.Background(), &feature.CreateFeatureFlagRequest{Key: "k", Name: "n", Type: feature.FlagTypeBoolean, IsEnabled: true})
	if err == nil {
		t.Fatalf("expected key taken error")
	}
}

func TestIsFeatureEnabled_NotFound(t *testing.T) {
	repo := &ffRepoMock{getByKeyFn: func(ctx context.Context, key string) (*feature.FeatureFlag, error) { return nil, errors.New("boom") }}
	svc := impl.NewFeatureFlagService(repo)
	_, err := svc.IsFeatureEnabled(context.Background(), "missing", &feature.FeatureFlagContext{})
	if err == nil {
		t.Fatalf("expected error when flag missing")
	}
}
