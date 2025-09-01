package helpers

import (
	"github.com/google/uuid"
	"github.com/labstack/echo/v4"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/permission"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/tenant"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
)

type ctxKey string

const (
	keyTenant          ctxKey = "tenant"
	keyUserID          ctxKey = "user_id"
	keyTenantID        ctxKey = "tenant_id"
	keyUserRole        ctxKey = "user_role"
	keyUserPermissions ctxKey = "user_permissions"
	keyUserEmail       ctxKey = "user_email"
	keyTargetUser      ctxKey = "target_user"
	keyAuditEnabled    ctxKey = "audit_enabled"
	keyJWTTenantID     ctxKey = "jwt_tenant_id"
)

func SetTenant(c echo.Context, t *tenant.Tenant) { c.Set(string(keyTenant), t) }
func GetTenant(c echo.Context) (*tenant.Tenant, bool) {
	v := c.Get(string(keyTenant))
	t, ok := v.(*tenant.Tenant)
	return t, ok
}

func SetUserID(c echo.Context, id uuid.UUID) { c.Set(string(keyUserID), id) }
func GetUserIDRaw(c echo.Context) (uuid.UUID, bool) {
	v := c.Get(string(keyUserID))
	id, ok := v.(uuid.UUID)
	return id, ok
}

func SetTenantID(c echo.Context, id uuid.UUID) { c.Set(string(keyTenantID), id) }
func GetTenantIDRaw(c echo.Context) (uuid.UUID, bool) {
	v := c.Get(string(keyTenantID))
	id, ok := v.(uuid.UUID)
	return id, ok
}

func SetUserRole(c echo.Context, r user.UserRole) { c.Set(string(keyUserRole), r) }
func GetUserRoleRaw(c echo.Context) (user.UserRole, bool) {
	v := c.Get(string(keyUserRole))
	r, ok := v.(user.UserRole)
	return r, ok
}

func SetUserPermissions(c echo.Context, perms []permission.Permission) {
	c.Set(string(keyUserPermissions), perms)
}
func GetUserPermissionsRaw(c echo.Context) ([]permission.Permission, bool) {
	v := c.Get(string(keyUserPermissions))
	p, ok := v.([]permission.Permission)
	return p, ok
}

func SetUserEmail(c echo.Context, email string) { c.Set(string(keyUserEmail), email) }
func GetUserEmailRaw(c echo.Context) (string, bool) {
	v := c.Get(string(keyUserEmail))
	s, ok := v.(string)
	return s, ok
}

func SetTargetUser(c echo.Context, u *user.User) { c.Set(string(keyTargetUser), u) }
func GetTargetUserRaw(c echo.Context) (*user.User, bool) {
	v := c.Get(string(keyTargetUser))
	u, ok := v.(*user.User)
	return u, ok
}

func SetAuditEnabled(c echo.Context, enabled bool) { c.Set(string(keyAuditEnabled), enabled) }
func GetAuditEnabledRaw(c echo.Context) (bool, bool) {
	v := c.Get(string(keyAuditEnabled))
	b, ok := v.(bool)
	return b, ok
}

func SetJWTTenantID(c echo.Context, id uuid.UUID) { c.Set(string(keyJWTTenantID), id) }
func GetJWTTenantIDRaw(c echo.Context) (uuid.UUID, bool) {
	v := c.Get(string(keyJWTTenantID))
	id, ok := v.(uuid.UUID)
	return id, ok
}
