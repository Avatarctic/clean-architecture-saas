package middleware

import (
	"net/http"

	"github.com/labstack/echo/v4"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/permission"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/httpserver/helpers"
)

type PermMiddleware struct {
	permissionService ports.PermissionService
	userService       ports.UserService
	jwtSecret         string
}

func NewPermMiddleware(permissionService ports.PermissionService, userService ports.UserService, jwtSecret string) *PermMiddleware {
	return &PermMiddleware{permissionService: permissionService, userService: userService, jwtSecret: jwtSecret}
}

func (m *PermMiddleware) RequirePermission(p permission.Permission) echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			perms, err := helpers.GetUserPermissionsFromContext(c)
			if err != nil {
				return echo.NewHTTPError(http.StatusUnauthorized, "missing permissions")
			}
			if !m.permissionService.HasPermission(perms, p) {
				return echo.NewHTTPError(http.StatusForbidden, "forbidden")
			}
			return next(c)
		}
	}
}

func (m *PermMiddleware) RequireAnyPermission(perms ...permission.Permission) echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			existing, err := helpers.GetUserPermissionsFromContext(c)
			if err != nil {
				return echo.NewHTTPError(http.StatusUnauthorized, "missing permissions")
			}
			if !m.permissionService.HasAnyPermission(existing, perms...) {
				return echo.NewHTTPError(http.StatusForbidden, "forbidden")
			}
			return next(c)
		}
	}
}
