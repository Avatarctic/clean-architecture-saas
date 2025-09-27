package middleware

import (
	"strings"

	"github.com/labstack/echo/v4"
	"github.com/sirupsen/logrus"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/httpserver/helpers"
)

type TenantMiddleware struct {
	tenantService ports.TenantService
	logger        *logrus.Logger
}

func NewTenantMiddleware(tenantService ports.TenantService, logger *logrus.Logger) *TenantMiddleware {
	return &TenantMiddleware{tenantService: tenantService, logger: logger}
}

func (t *TenantMiddleware) ResolveTenant() echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			slug := extractTenantSlug(c)
			if slug != "" {
				t.resolveAndSetTenant(c, slug)
			}
			return next(c)
		}
	}
}

// extractTenantSlug gets tenant slug from X-Tenant-Slug header or hostname subdomain.
func extractTenantSlug(c echo.Context) string {
	if v := c.Request().Header.Get("X-Tenant-Slug"); v != "" {
		return v
	}
	host := c.Request().Host
	// strip port if present
	if idx := strings.Index(host, ":"); idx != -1 {
		host = host[:idx]
	}
	parts := strings.Split(host, ".")
	if len(parts) > 1 && parts[0] != "localhost" {
		return parts[0]
	}
	return ""
}

// resolveAndSetTenant looks up tenant by slug and sets it in context if found.
func (t *TenantMiddleware) resolveAndSetTenant(c echo.Context, slug string) {
	if t.tenantService == nil {
		return
	}
	tenant, err := t.tenantService.GetTenantBySlug(c.Request().Context(), slug)
	if err == nil && tenant != nil {
		helpers.SetTenant(c, tenant)
		helpers.SetTenantID(c, tenant.ID)
		if t.logger != nil {
			t.logger.WithFields(logrus.Fields{"tenant_slug": slug, "tenant_id": tenant.ID}).Debug("resolved tenant from request")
		}
		return
	}
	if t.logger != nil {
		t.logger.WithFields(logrus.Fields{"tenant_slug": slug, "error": err}).Debug("tenant resolution failed; continuing without tenant")
	}
}
