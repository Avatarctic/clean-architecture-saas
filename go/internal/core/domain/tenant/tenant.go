package tenant

import (
	"slices"
	"time"

	"github.com/google/uuid"
)

type Tenant struct {
	ID        uuid.UUID        `json:"id" db:"id"`
	Name      string           `json:"name" db:"name"`
	Slug      string           `json:"slug" db:"slug"`
	Domain    string           `json:"domain" db:"domain"`
	Plan      SubscriptionPlan `json:"plan" db:"plan"`
	Status    TenantStatus     `json:"status" db:"status"`
	Settings  TenantSettings   `json:"settings" db:"settings"`
	CreatedAt time.Time        `json:"created_at" db:"created_at"`
	UpdatedAt time.Time        `json:"updated_at" db:"updated_at"`
}

type TenantStatus string

const (
	TenantStatusActive    TenantStatus = "active"
	TenantStatusSuspended TenantStatus = "suspended"
	TenantStatusCanceled  TenantStatus = "canceled"
)

// ValidTransitions returns the valid status transitions from current status
func (ts TenantStatus) ValidTransitions() []TenantStatus {
	switch ts {
	case TenantStatusActive:
		return []TenantStatus{TenantStatusSuspended, TenantStatusCanceled}
	case TenantStatusSuspended:
		return []TenantStatus{TenantStatusActive, TenantStatusCanceled}
	case TenantStatusCanceled:
		return []TenantStatus{} // No transitions from canceled
	default:
		return []TenantStatus{}
	}
}

// IsValidTransition checks if transition to new status is valid
func (ts TenantStatus) IsValidTransition(newStatus TenantStatus) bool {
	validTransitions := ts.ValidTransitions()
	return slices.Contains(validTransitions, newStatus)
}

// Tenant domain methods

// CanAccess returns true if the tenant can access the application
func (t *Tenant) CanAccess() bool {
	return t.Status == TenantStatusActive
}

// CanTransitionTo checks if the tenant can transition to a new status
func (t *Tenant) CanTransitionTo(newStatus TenantStatus) bool {
	return t.Status.IsValidTransition(newStatus)
}

type SubscriptionPlan string

const (
	PlanFree       SubscriptionPlan = "free"
	PlanStarter    SubscriptionPlan = "starter"
	PlanPro        SubscriptionPlan = "pro"
	PlanEnterprise SubscriptionPlan = "enterprise"
)

type TenantSettings struct {
	Limits        TenantLimits   `json:"limits"`
	Customization map[string]any `json:"customization"`
}

type TenantLimits struct {
	MaxUsers          int `json:"max_users"`
	RequestsPerMinute int `json:"requests_per_minute"`
}

// CreateTenantRequest represents the request to create a new tenant
type CreateTenantRequest struct {
	Name     string           `json:"name" validate:"required"`
	Slug     string           `json:"slug" validate:"required,alphanum"`
	Domain   string           `json:"domain" validate:"omitempty,fqdn"`
	Plan     SubscriptionPlan `json:"plan" validate:"required,oneof=free starter pro enterprise"`
	Settings TenantSettings   `json:"settings" validate:"required"`

	// Initial admin user details
	AdminUser CreateTenantAdminRequest `json:"admin_user" validate:"required"`
}

// CreateTenantAdminRequest represents the initial admin user for a new tenant
type CreateTenantAdminRequest struct {
	Email     string `json:"email" validate:"required,email"`
	Password  string `json:"password" validate:"required,min=8"`
	FirstName string `json:"first_name" validate:"required"`
	LastName  string `json:"last_name" validate:"required"`
}

// UpdateTenantRequest represents the request to update a tenant
type UpdateTenantRequest struct {
	Name     *string           `json:"name,omitempty"`
	Slug     *string           `json:"slug,omitempty" validate:"omitempty,alphanum"`
	Domain   *string           `json:"domain,omitempty"`
	Plan     *SubscriptionPlan `json:"plan,omitempty"`
	Status   *TenantStatus     `json:"status,omitempty"`
	Settings *TenantSettings   `json:"settings,omitempty"`
}
