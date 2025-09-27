package middleware

import (
	"net/http"

	"github.com/labstack/echo/v4"
	"github.com/sirupsen/logrus"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/auth"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/permission"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/httpserver/helpers"
)

type JWTMiddleware struct {
	authService       ports.AuthService
	userService       ports.UserService
	permissionService ports.PermissionService
	logger            *logrus.Logger
}

func NewJWTMiddleware(authService ports.AuthService, userService ports.UserService, permissionService ports.PermissionService, logger *logrus.Logger) *JWTMiddleware {
	return &JWTMiddleware{authService: authService, userService: userService, permissionService: permissionService, logger: logger}
}

// RequireJWT creates middleware that validates JWT tokens and sets user context
func (m *JWTMiddleware) RequireJWT() echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			// Validate token and start session
			claims, err := m.validateAndStartSession(c)
			if err != nil {
				return err
			}

			// populate context with user/permission information
			if err := m.populateContextWithClaims(c, claims); err != nil {
				return err
			}

			return next(c)
		}
	}
}

// validateAndStartSession retrieves the token from context and calls StartSession on the auth service.
func (m *JWTMiddleware) validateAndStartSession(c echo.Context) (*auth.Claims, error) {
	tokenString, err := helpers.GetJWTTokenFromContext(c)
	if err != nil {
		return nil, err
	}

	claims, err := m.authService.StartSession(c.Request().Context(), tokenString, c.RealIP(), c.Request().UserAgent())
	if err != nil {
		if m.logger != nil {
			m.logger.WithFields(logrus.Fields{"ip": c.RealIP(), "path": c.Request().URL.Path, "error": err.Error()}).Warn("JWT validation failed")
		}
		return nil, echo.NewHTTPError(http.StatusUnauthorized, err.Error())
	}
	return claims, nil
}

// populateContextWithClaims sets standard context keys and loads permissions and user info.
func (m *JWTMiddleware) populateContextWithClaims(c echo.Context, claims *auth.Claims) error {
	helpers.SetUserID(c, claims.UserID)
	helpers.SetUserRole(c, claims.Role)
	helpers.SetUserEmail(c, claims.Email)

	userObj, err := m.userService.GetUser(c.Request().Context(), claims.UserID)
	if err == nil && userObj != nil {
		helpers.SetAuditEnabled(c, userObj.AuditEnabled)
		// also populate the full current user into context to avoid redundant DB reads
		helpers.SetCurrentUser(c, userObj)
	} else {
		helpers.SetAuditEnabled(c, true)
	}

	if m.logger != nil {
		m.logger.WithFields(logrus.Fields{"user_id": claims.UserID, "role": claims.Role, "tenant_id": claims.TenantID}).Debug("jwt validated and user context set")
	}

	permissions, err := m.permissionService.GetRolePermissions(c.Request().Context(), claims.Role)
	if err != nil {
		if m.logger != nil {
			m.logger.WithFields(logrus.Fields{"role": claims.Role, "error": err.Error()}).Error("failed to load user permissions")
		}
		return echo.NewHTTPError(http.StatusInternalServerError, "failed to load user permissions")
	}

	if permissions == nil {
		permissions = []permission.Permission{}
	}
	helpers.SetUserPermissions(c, permissions)

	if tenantID, exists := helpers.GetTenantIDRaw(c); exists {
		if claims.TenantID != tenantID {
			return echo.NewHTTPError(http.StatusForbidden, "user does not belong to this tenant")
		}
	} else {
		helpers.SetTenantID(c, claims.TenantID)
	}
	return nil
}
