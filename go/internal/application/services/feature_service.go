package services

import (
	"context"
	"fmt"
	"time"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/feature"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/google/uuid"
	"github.com/sirupsen/logrus"
)

type FeatureFlagService struct {
	repo   ports.FeatureFlagRepository
	logger *logrus.Logger
}

func NewFeatureFlagService(repo ports.FeatureFlagRepository) ports.FeatureFlagService {
	return &FeatureFlagService{
		repo: repo,
	}
}

func (s *FeatureFlagService) CreateFeatureFlag(ctx context.Context, req *feature.CreateFeatureFlagRequest) (*feature.FeatureFlag, error) {
	// Validate key uniqueness
	if existingFlag, err := s.repo.GetByKey(ctx, req.Key); err == nil && existingFlag != nil {
		return nil, fmt.Errorf("feature flag key '%s' is already taken", req.Key)
	}

	featureFlag := &feature.FeatureFlag{
		ID:           uuid.New(),
		Name:         req.Name,
		Key:          req.Key,
		Description:  req.Description,
		Type:         req.Type,
		IsEnabled:    req.IsEnabled,
		EnabledValue: req.EnabledValue,
		DefaultValue: req.DefaultValue,
		Rules:        req.Rules,
		Rollout:      req.Rollout,
		CreatedAt:    time.Now(),
		UpdatedAt:    time.Now(),
	}
	if err := s.repo.Create(ctx, featureFlag); err != nil {
		if s.logger != nil {
			s.logger.WithFields(logrus.Fields{"key": req.Key, "name": req.Name}).WithError(err).Error("failed to create feature flag in repo")
		}
		return nil, fmt.Errorf("failed to create feature flag: %w", err)
	}
	if s.logger != nil {
		s.logger.WithFields(logrus.Fields{"key": featureFlag.Key, "id": featureFlag.ID}).Info("feature flag created")
	}
	return featureFlag, nil
}

func (s *FeatureFlagService) UpdateFeatureFlag(ctx context.Context, id uuid.UUID, req *feature.UpdateFeatureFlagRequest) (*feature.FeatureFlag, error) {
	featureFlag, err := s.repo.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}
	if err := s.applyUpdates(ctx, featureFlag, req); err != nil {
		return nil, err
	}

	if err := s.repo.Update(ctx, featureFlag); err != nil {
		if s.logger != nil {
			s.logger.WithFields(logrus.Fields{"id": id, "key": featureFlag.Key}).WithError(err).Error("failed to update feature flag in repo")
		}
		return nil, fmt.Errorf("failed to update feature flag: %w", err)
	}
	if s.logger != nil {
		s.logger.WithFields(logrus.Fields{"id": id, "key": featureFlag.Key}).Info("feature flag updated")
	}
	return featureFlag, nil
}

// applyUpdates applies the non-nil fields from the request to the feature flag
// and performs any necessary validation. Returns an error when validation fails.
func (s *FeatureFlagService) applyUpdates(ctx context.Context, featureFlag *feature.FeatureFlag, req *feature.UpdateFeatureFlagRequest) error {
	if req.Name != nil {
		featureFlag.Name = *req.Name
	}
	if req.Key != nil {
		// Validate key uniqueness if it's being changed
		if *req.Key != featureFlag.Key {
			if existing, err := s.repo.GetByKey(ctx, *req.Key); err == nil && existing != nil && existing.ID != featureFlag.ID {
				return fmt.Errorf("feature flag key '%s' is already taken", *req.Key)
			}
		}
		featureFlag.Key = *req.Key
	}
	if req.Description != nil {
		featureFlag.Description = *req.Description
	}
	if req.Type != nil {
		featureFlag.Type = *req.Type
	}
	if req.IsEnabled != nil {
		featureFlag.IsEnabled = *req.IsEnabled
	}
	if req.EnabledValue != nil {
		featureFlag.EnabledValue = *req.EnabledValue
	}
	if req.DefaultValue != nil {
		featureFlag.DefaultValue = *req.DefaultValue
	}
	if req.Rules != nil {
		featureFlag.Rules = *req.Rules
	}
	if req.Rollout != nil {
		featureFlag.Rollout = *req.Rollout
	}
	featureFlag.UpdatedAt = time.Now()
	return nil
}

func (s *FeatureFlagService) DeleteFeatureFlag(ctx context.Context, id uuid.UUID) error {
	return s.repo.Delete(ctx, id)
}

func (s *FeatureFlagService) ListFeatureFlags(ctx context.Context, limit, offset int) ([]*feature.FeatureFlag, int, error) {
	flags, err := s.repo.List(ctx, limit, offset)
	if err != nil {
		return nil, 0, err
	}

	count, err := s.repo.Count(ctx)
	if err != nil {
		return nil, 0, err
	}

	return flags, count, nil
}

func (s *FeatureFlagService) IsFeatureEnabled(ctx context.Context, key string, context *feature.FeatureFlagContext) (bool, error) {
	flag, err := s.repo.GetByKey(ctx, key)
	if err != nil {
		if s.logger != nil {
			s.logger.WithFields(logrus.Fields{"key": key}).WithError(err).Warn("feature flag not found or repo error")
		}
		return false, err
	}

	_, enabled := flag.Evaluate(context)
	if s.logger != nil {
		s.logger.WithFields(logrus.Fields{"key": key, "enabled": enabled}).Debug("feature flag evaluated")
	}
	return enabled, nil
}

func (s *FeatureFlagService) GetFeatureValue(ctx context.Context, key string, context *feature.FeatureFlagContext) (any, error) {
	flag, err := s.repo.GetByKey(ctx, key)
	if err != nil {
		return nil, err
	}

	val, _ := flag.Evaluate(context)
	return val, nil
}
