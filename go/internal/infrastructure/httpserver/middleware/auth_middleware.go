package middleware

import (
	"net/http"

	"github.com/google/uuid"
	"github.com/labstack/echo/v4"
	"github.com/sirupsen/logrus"

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
			tokenString, err := helpers.GetJWTTokenFromContext(c)
			if err != nil {
				return err
			}

			claims, err := m.authService.StartSession(c.Request().Context(), tokenString, c.RealIP(), c.Request().UserAgent())
			if err != nil {
				if m.logger != nil {
					m.logger.WithFields(logrus.Fields{"ip": c.RealIP(), "path": c.Request().URL.Path, "error": err.Error()}).Warn("JWT validation failed")
				}
				return echo.NewHTTPError(http.StatusUnauthorized, err.Error())
			}

			c.Set("user_id", claims.UserID)
			c.Set("user_role", claims.Role)
			c.Set("user_email", claims.Email)

			userObj, err := m.userService.GetUser(c.Request().Context(), claims.UserID)
			if err == nil && userObj != nil {
				c.Set("audit_enabled", userObj.AuditEnabled)
			} else {
				c.Set("audit_enabled", true)
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
			c.Set("user_permissions", permissions)

			if tenantID, exists := c.Get("tenant_id").(uuid.UUID); exists {
				if claims.TenantID != tenantID {
					return echo.NewHTTPError(http.StatusForbidden, "user does not belong to this tenant")
				}
				c.Set("jwt_tenant_id", claims.TenantID)
			} else {
				c.Set("tenant_id", claims.TenantID)
				c.Set("jwt_tenant_id", claims.TenantID)
			}

			return next(c)
		}
	}
}
