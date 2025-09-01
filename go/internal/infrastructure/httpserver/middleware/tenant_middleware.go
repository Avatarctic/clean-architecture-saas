package middleware

import (
	"github.com/labstack/echo/v4"
	"github.com/sirupsen/logrus"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
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
			// tenant resolution logic (subdomain lookup) omitted in tests
			return next(c)
		}
	}
}
