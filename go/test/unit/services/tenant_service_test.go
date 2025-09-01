package services_test

import (
	"context"
	"testing"

	impl "github.com/avatarctic/clean-architecture-saas/go/internal/application/services"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/tenant"
	tmocks "github.com/avatarctic/clean-architecture-saas/go/test/mocks"
)

// tenant repo: use tmocks.TenantRepositoryMock in tests

func TestCreateTenant_SlugTaken(t *testing.T) {
	repo := &tmocks.TenantRepositoryMock{GetBySlugFn: func(ctx context.Context, slug string) (*tenant.Tenant, error) { return &tenant.Tenant{}, nil }}
	svc := impl.NewTenantService(repo, &tmocks.UserRepositoryMock{}, &tmocks.UserServiceMock{}, nil, nil)

	_, err := svc.CreateTenant(context.Background(), &tenant.CreateTenantRequest{Name: "x", Slug: "s", Domain: "d", Plan: tenant.PlanFree, Settings: tenant.TenantSettings{}, AdminUser: tenant.CreateTenantAdminRequest{Email: "a@b.com", Password: "pass", FirstName: "A", LastName: "B"}})
	if err == nil {
		t.Fatalf("expected slug taken error")
	}
}

func TestCreateTenant_Success(t *testing.T) {
	repo := &tmocks.TenantRepositoryMock{}
	ur := &tmocks.UserRepositoryMock{}
	svc := impl.NewTenantService(repo, ur, &tmocks.UserServiceMock{}, nil, nil)
	req := &tenant.CreateTenantRequest{Name: "n", Slug: "unique", Domain: "d", Plan: tenant.PlanFree, Settings: tenant.TenantSettings{}, AdminUser: tenant.CreateTenantAdminRequest{Email: "a@b.com", Password: "pass12!", FirstName: "A", LastName: "B"}}
	_, err := svc.CreateTenant(context.Background(), req)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}
