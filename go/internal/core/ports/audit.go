package ports

import (
	"context"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/audit"
)

// AuditRepository defines the interface for audit log data operations
type AuditRepository interface {
	Create(ctx context.Context, log *audit.AuditLog) error
	List(ctx context.Context, filter *audit.AuditLogFilter) ([]*audit.AuditLog, error)
	Count(ctx context.Context, filter *audit.AuditLogFilter) (int, error)
}

// AuditService defines the interface for audit logging business logic
type AuditService interface {
	LogAction(ctx context.Context, req *audit.CreateAuditLogRequest) error
	GetAuditLogs(ctx context.Context, filter *audit.AuditLogFilter) ([]*audit.AuditLog, int, error)
}
