package services_test

import (
	"context"
	"errors"
	"testing"
	"time"

	impl "github.com/avatarctic/clean-architecture-saas/go/internal/application/services"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/audit"
	"github.com/google/uuid"
)

type auditRepoMock struct {
	createFn func(ctx context.Context, l *audit.AuditLog) error
	listFn   func(ctx context.Context, f *audit.AuditLogFilter) ([]*audit.AuditLog, error)
	countFn  func(ctx context.Context, f *audit.AuditLogFilter) (int, error)
}

func (m *auditRepoMock) Create(ctx context.Context, l *audit.AuditLog) error {
	if m.createFn != nil {
		return m.createFn(ctx, l)
	}
	return nil
}
func (m *auditRepoMock) List(ctx context.Context, f *audit.AuditLogFilter) ([]*audit.AuditLog, error) {
	if m.listFn != nil {
		return m.listFn(ctx, f)
	}
	return nil, nil
}
func (m *auditRepoMock) Count(ctx context.Context, f *audit.AuditLogFilter) (int, error) {
	if m.countFn != nil {
		return m.countFn(ctx, f)
	}
	return 0, nil
}

func TestLogAction_SkipsWhenDisabled(t *testing.T) {
	repo := &auditRepoMock{createFn: func(ctx context.Context, l *audit.AuditLog) error {
		t.Fatal("should not be called when disabled")
		return nil
	}}
	svc := impl.NewAuditService(repo, nil)

	// Service expects the context key "audit_enabled" as a string.
	ctx := context.WithValue(context.Background(), "audit_enabled", false)

	err := svc.LogAction(ctx, &audit.CreateAuditLogRequest{TenantID: uuid.Nil, UserID: nil, Action: audit.AuditAction("test")})
	if err != nil {
		t.Fatalf("expected no error when audit disabled, got: %v", err)
	}
}

func TestGetAuditLogs_ReturnsListAndCount(t *testing.T) {
	now := time.Now()
	sample := &audit.AuditLog{UserID: nil, TenantID: uuid.Nil, Action: "a", Timestamp: now}
	repo := &auditRepoMock{
		listFn: func(ctx context.Context, f *audit.AuditLogFilter) ([]*audit.AuditLog, error) {
			return []*audit.AuditLog{sample}, nil
		},
		countFn: func(ctx context.Context, f *audit.AuditLogFilter) (int, error) { return 1, nil },
	}
	svc := impl.NewAuditService(repo, nil)

	logs, total, err := svc.GetAuditLogs(context.Background(), &audit.AuditLogFilter{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if total != 1 {
		t.Fatalf("expected total 1, got %d", total)
	}
	if len(logs) != 1 || logs[0].Timestamp != now {
		t.Fatalf("unexpected logs returned")
	}
}

func TestGetAuditLogs_RepoError(t *testing.T) {
	repo := &auditRepoMock{listFn: func(ctx context.Context, f *audit.AuditLogFilter) ([]*audit.AuditLog, error) {
		return nil, errors.New("boom")
	}}
	svc := impl.NewAuditService(repo, nil)
	_, _, err := svc.GetAuditLogs(context.Background(), &audit.AuditLogFilter{})
	if err == nil {
		t.Fatalf("expected error from repo")
	}
}
