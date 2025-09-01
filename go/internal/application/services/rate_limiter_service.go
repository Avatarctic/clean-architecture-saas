package services

import (
	"context"
	"time"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/google/uuid"
	"github.com/sirupsen/logrus"
)

// RateLimiterService implements RateLimiter using a single static policy.
type RateLimiterService struct {
	repo            ports.RateLimitRepository
	tenantRepo      ports.TenantRepository
	defaultLimit    int
	burstMultiplier float64
	window          time.Duration
	keyPrefix       string
	logger          *logrus.Logger
}

// RateLimiterConfig groups configuration parameters for the rate limiter.
type RateLimiterConfig struct {
	DefaultRequestsPerMinute int
	BurstMultiplier          float64
	Window                   time.Duration
	KeyPrefix                string
}

func NewRateLimiterService(repo ports.RateLimitRepository, tenantRepo ports.TenantRepository, cfg *RateLimiterConfig, logger *logrus.Logger) *RateLimiterService {
	// Apply defaults
	dl := 120
	bm := 2.0
	w := time.Minute
	kp := "ratelimit:tenant"
	if cfg != nil {
		if cfg.DefaultRequestsPerMinute > 0 {
			dl = cfg.DefaultRequestsPerMinute
		}
		if cfg.BurstMultiplier > 0 {
			bm = cfg.BurstMultiplier
		}
		if cfg.Window > 0 {
			w = cfg.Window
		}
		if cfg.KeyPrefix != "" {
			kp = cfg.KeyPrefix
		}
	}
	return &RateLimiterService{repo: repo, tenantRepo: tenantRepo, defaultLimit: dl, burstMultiplier: bm, window: w, keyPrefix: kp, logger: logger}
}

func (s *RateLimiterService) Allow(ctx context.Context, tenantID uuid.UUID) (bool, int, int, time.Time, error) {
	// Determine tenant-specific limit
	limit := s.defaultLimit
	if s.tenantRepo != nil {
		if t, err := s.tenantRepo.GetByID(ctx, tenantID); err == nil && t != nil {
			if t.Settings.Limits.RequestsPerMinute > 0 {
				limit = t.Settings.Limits.RequestsPerMinute
			}
		}
	}
	ttl := s.window * 2 // retain overlap window
	count, windowStart, err := s.repo.IncrementWindow(ctx, tenantID, s.window, s.keyPrefix, ttl)
	reset := windowStart.Add(s.window)
	burst := int(float64(limit) * s.burstMultiplier)
	if err != nil {
		if s.logger != nil {
			s.logger.WithFields(logrus.Fields{"tenant_id": tenantID}).WithError(err).Error("rate limiter: failed to increment window")
		}
		// fail open
		return true, burst, limit, reset, err
	}
	if s.logger != nil {
		s.logger.WithFields(logrus.Fields{"tenant_id": tenantID, "count": count, "burst": burst, "limit": limit}).Debug("rate limiter window state")
	}
	if count > burst {
		return false, 0, limit, reset, nil
	}
	remaining := burst - count
	return true, remaining, limit, reset, nil
}
