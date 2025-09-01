package ports

import (
	"context"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/tenant"
	"github.com/google/uuid"
)

// TenantRepository defines the interface for tenant data operations
type TenantRepository interface {
	Create(ctx context.Context, tenant *tenant.Tenant) error
	GetByID(ctx context.Context, id uuid.UUID) (*tenant.Tenant, error)
	GetBySlug(ctx context.Context, slug string) (*tenant.Tenant, error)
	Update(ctx context.Context, tenant *tenant.Tenant) error
	Delete(ctx context.Context, id uuid.UUID) error
	List(ctx context.Context, limit, offset int) ([]*tenant.Tenant, error)
	Count(ctx context.Context) (int, error)
}

// TenantService defines the interface for tenant business logic
type TenantService interface {
	CreateTenant(ctx context.Context, req *tenant.CreateTenantRequest) (*tenant.Tenant, error)
	GetTenant(ctx context.Context, id uuid.UUID) (*tenant.Tenant, error)
	GetTenantBySlug(ctx context.Context, slug string) (*tenant.Tenant, error)
	GetActiveTenant(ctx context.Context, id uuid.UUID) (*tenant.Tenant, error)
	UpdateTenant(ctx context.Context, id uuid.UUID, req *tenant.UpdateTenantRequest) (*tenant.Tenant, error)
	DeleteTenant(ctx context.Context, id uuid.UUID) error
	ListTenants(ctx context.Context, limit, offset int) ([]*tenant.Tenant, int, error)
}
