package helpers

import (
	"fmt"
	"net/http"
	"strings"

	"github.com/google/uuid"
	"github.com/labstack/echo/v4"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/permission"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/tenant"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
)

func GetTenantFromContext(c echo.Context) (*tenant.Tenant, error) {
	t, ok := GetTenant(c)
	if !ok || t == nil {
		return nil, echo.NewHTTPError(http.StatusUnauthorized, "invalid tenant context")
	}
	return t, nil
}

func GetActiveTenantFromContext(c echo.Context) (*tenant.Tenant, error) {
	t, err := GetTenantFromContext(c)
	if err != nil {
		return nil, err
	}
	if !t.CanAccess() {
		return nil, echo.NewHTTPError(http.StatusForbidden, fmt.Sprintf("tenant is %s", t.Status))
	}
	return t, nil
}

func GetUserIDFromContext(c echo.Context) (uuid.UUID, error) {
	id, ok := GetUserIDRaw(c)
	if !ok {
		return uuid.Nil, echo.NewHTTPError(http.StatusUnauthorized, "invalid user context")
	}
	return id, nil
}

func GetTenantIDFromContext(c echo.Context) (uuid.UUID, error) {
	id, ok := GetTenantIDRaw(c)
	if !ok {
		return uuid.Nil, echo.NewHTTPError(http.StatusUnauthorized, "invalid tenant context")
	}
	return id, nil
}

func GetUserRoleFromContext(c echo.Context) (user.UserRole, error) {
	r, ok := GetUserRoleRaw(c)
	if !ok {
		return "", echo.NewHTTPError(http.StatusUnauthorized, "invalid role context")
	}
	return r, nil
}

func GetUserPermissionsFromContext(c echo.Context) ([]permission.Permission, error) {
	p, ok := GetUserPermissionsRaw(c)
	if !ok {
		return nil, echo.NewHTTPError(http.StatusUnauthorized, "user permissions not found")
	}
	return p, nil
}

func GetUserEmailFromContext(c echo.Context) (string, error) {
	s, ok := GetUserEmailRaw(c)
	if !ok {
		return "", echo.NewHTTPError(http.StatusUnauthorized, "invalid user email context")
	}
	return s, nil
}

func GetJWTTokenFromContext(c echo.Context) (string, error) {
	authHeader := c.Request().Header.Get("Authorization")
	if authHeader == "" {
		return "", echo.NewHTTPError(http.StatusUnauthorized, "missing authorization header")
	}
	if !strings.HasPrefix(authHeader, "Bearer ") {
		return "", echo.NewHTTPError(http.StatusUnauthorized, "invalid authorization header format")
	}
	token := strings.TrimPrefix(authHeader, "Bearer ")
	if token == "" {
		return "", echo.NewHTTPError(http.StatusUnauthorized, "empty token")
	}
	return token, nil
}

func GetAuditEnabled(c echo.Context) bool {
	if b, ok := GetAuditEnabledRaw(c); ok {
		return b
	}
	return true
}

// GetCurrentUserFromContext returns the full acting user object set by JWT middleware
func GetCurrentUserFromContext(c echo.Context) (*user.User, error) {
	u, ok := GetCurrentUserRaw(c)
	if !ok || u == nil {
		return nil, echo.NewHTTPError(http.StatusUnauthorized, "invalid user context")
	}
	return u, nil
}
