package services

import (
	"context"
	"time"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/audit"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/sirupsen/logrus"
)

type AuditService struct {
	repo   ports.AuditRepository
	logger *logrus.Logger
}

func NewAuditService(repo ports.AuditRepository, logger *logrus.Logger) ports.AuditService {
	return &AuditService{
		repo:   repo,
		logger: logger,
	}
}

const (
	auditEnabledCtxKey = "audit_enabled"
)

// AuditEnabled checks whether auditing is enabled for the current user (from context)
func (s *AuditService) AuditEnabled(ctx context.Context) bool {
	v := ctx.Value(auditEnabledCtxKey)
	if enabled, ok := v.(bool); ok {
		return enabled
	}
	// Default to true if not set
	return true
}

func (s *AuditService) LogAction(ctx context.Context, req *audit.CreateAuditLogRequest) error {
	// short-circuit if audit disabled for this user (from context)
	if !s.AuditEnabled(ctx) {
		if s.logger != nil {
			s.logger.WithFields(logrus.Fields{"tenant_id": req.TenantID, "user_id": req.UserID}).Debug("audit disabled for user; skipping log")
		}
		return nil
	}

	auditLog := &audit.AuditLog{
		UserID:     req.UserID,
		TenantID:   req.TenantID,
		Action:     string(req.Action),
		Timestamp:  time.Now(),
		Resource:   string(req.Resource),
		ResourceID: req.ResourceID,
		Details:    req.Details,
		IPAddress:  req.IPAddress,
		UserAgent:  req.UserAgent,
	}

	err := s.repo.Create(ctx, auditLog)
	if err != nil {
		if s.logger != nil {
			s.logger.WithFields(logrus.Fields{"tenant_id": req.TenantID, "user_id": req.UserID, "action": req.Action, "resource": req.Resource}).WithError(err).Error("failed to persist audit log")
		}
		return err
	}
	if s.logger != nil {
		s.logger.WithFields(logrus.Fields{"tenant_id": req.TenantID, "user_id": req.UserID, "action": req.Action, "resource": req.Resource, "resource_id": req.ResourceID}).Debug("audit log persisted")
	}
	return nil
}

func (s *AuditService) GetAuditLogs(ctx context.Context, filter *audit.AuditLogFilter) ([]*audit.AuditLog, int, error) {
	logs, err := s.repo.List(ctx, filter)
	if err != nil {
		return nil, 0, err
	}

	total, err := s.repo.Count(ctx, filter)
	if err != nil {
		return nil, 0, err
	}

	return logs, total, nil
}
