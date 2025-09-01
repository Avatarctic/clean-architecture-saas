package middleware

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/sirupsen/logrus"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
)

// MiddlewareCollection holds all middleware instances
type MiddlewareCollection struct {
	JWT           *JWTMiddleware
	Tenant        *TenantMiddleware
	Logging       *LoggingMiddleware
	Perm          *PermMiddleware
	AccessControl *AccessControlMiddleware
	RoleHierarchy *RoleHierarchyMiddleware
	RateLimit     *RateLimitMiddleware
	Metrics       *MetricsMiddleware
}

// NewMiddlewareCollection creates a new collection of all middleware
func NewMiddlewareCollection(
	authService ports.AuthService,
	tenantService ports.TenantService,
	userService ports.UserService,
	permissionService ports.PermissionService,
	accessControlService ports.AccessControlService,
	rateLimiterService ports.RateLimiterService,
	logger *logrus.Logger,
	jwtSecret string,
	requestsTotal *prometheus.CounterVec,
	requestDuration *prometheus.HistogramVec,
) *MiddlewareCollection {
	return &MiddlewareCollection{
		JWT:           NewJWTMiddleware(authService, userService, permissionService, logger),
		Tenant:        NewTenantMiddleware(tenantService, logger),
		Logging:       NewLoggingMiddleware(logger),
		Perm:          NewPermMiddleware(permissionService, userService, jwtSecret),
		AccessControl: NewAccessControlMiddleware(accessControlService, userService),
		RoleHierarchy: NewRoleHierarchyMiddleware(userService),
		RateLimit:     NewRateLimitMiddleware(rateLimiterService, logger),
		Metrics:       NewMetricsMiddleware(requestsTotal, requestDuration),
	}
}
