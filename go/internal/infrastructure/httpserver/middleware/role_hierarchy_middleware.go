package middleware

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"

	"github.com/labstack/echo/v4"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/httpserver/helpers"
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
			// Determine actor role
			actorRole, err := helpers.GetUserRoleFromContext(c)
			if err != nil {
				return echo.NewHTTPError(http.StatusUnauthorized, "missing actor role")
			}
			// If a target user was preloaded, enforce actor has higher rank than target
			if handled, err := enforcePreloadedTargetRole(c, actorRole); handled {
				return err
			}

			// No target user — this is likely a create request; inspect request body for requested role
			if err := enforceRequestedRoleFromBody(c, actorRole); err != nil {
				return err
			}
			return next(c)
		}
	}
}

// roleAllows returns true if actorRole is strictly higher than targetRole, or actor is super_admin
func roleAllows(actorRole user.UserRole, targetRole user.UserRole) bool {
	// Define rank ordering
	rank := func(r user.UserRole) int {
		switch r {
		case user.RoleSuperAdmin:
			return 4
		case user.RoleAdmin:
			return 3
		case user.RoleMember:
			return 2
		case user.RoleGuest:
			return 1
		default:
			return 0
		}
	}
	if actorRole == user.RoleSuperAdmin {
		return true
	}
	return rank(actorRole) > rank(targetRole)
}

// enforcePreloadedTargetRole returns (handled, error). If handled==true the middleware
// should return immediately with the provided error (which may be nil to continue).
func enforcePreloadedTargetRole(c echo.Context, actorRole user.UserRole) (bool, error) {
	if target, ok := helpers.GetTargetUserRaw(c); ok && target != nil {
		if !roleAllows(actorRole, target.Role) {
			return true, echo.NewHTTPError(http.StatusForbidden, "insufficient role hierarchy")
		}
		// handled and no error -> we should proceed to next handler
		return true, nil
	}
	return false, nil
}

// enforceRequestedRoleFromBody inspects a shallow request JSON body for a "role" field
// and enforces hierarchy rules if present.
func enforceRequestedRoleFromBody(c echo.Context, actorRole user.UserRole) error {
	if c.Request().Body == nil {
		return nil
	}
	b, _ := io.ReadAll(c.Request().Body)
	// restore body for downstream handlers
	c.Request().Body = io.NopCloser(bytes.NewReader(b))
	if len(b) == 0 {
		return nil
	}
	var payload map[string]any
	if err := json.Unmarshal(b, &payload); err != nil {
		return nil
	}
	if rVal, ok := payload["role"]; ok {
		if roleStr, ok := rVal.(string); ok {
			requested := user.UserRole(roleStr)
			if !roleAllows(actorRole, requested) {
				return echo.NewHTTPError(http.StatusForbidden, "insufficient role hierarchy for requested role")
			}
		}
	}
	return nil
}
