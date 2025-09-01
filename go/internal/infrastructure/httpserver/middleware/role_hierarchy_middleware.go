package middleware

import (
	"github.com/labstack/echo/v4"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
)

type RoleHierarchyMiddleware struct {
	userService ports.UserService
}

func NewRoleHierarchyMiddleware(userService ports.UserService) *RoleHierarchyMiddleware {
	return &RoleHierarchyMiddleware{userService: userService}
}

func (r *RoleHierarchyMiddleware) RequireRoleHierarchyForUserManagement() echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			return next(c)
		}
	}
}
