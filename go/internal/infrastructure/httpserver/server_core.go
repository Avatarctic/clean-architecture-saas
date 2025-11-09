package httpserver

import (
	"time"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	customMiddleware "github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/httpserver/middleware"
	"github.com/labstack/echo/v4"
	"github.com/sirupsen/logrus"
)

type ServerConfig struct {
	Host           string
	Port           string
	ReadTimeout    time.Duration
	WriteTimeout   time.Duration
	IdleTimeout    time.Duration
	TLSCertFile    string
	TLSKeyFile     string
	AllowedOrigins []string
	Environment    string
}

type ServerDeps struct {
	UserService          ports.UserService
	AuthService          ports.AuthService
	TenantService        ports.TenantService
	FeatureFlagService   ports.FeatureFlagService
	AuditService         ports.AuditService
	PermissionService    ports.PermissionService
	AccessControlService ports.AccessControlService
	RateLimiterService   ports.RateLimiterService
	HealthCheckers       []ports.HealthChecker
}

type Server struct {
	echo           *echo.Echo
	config         *ServerConfig
	logger         *logrus.Logger
	userService    ports.UserService
	authSvc        ports.AuthService
	tenantService  ports.TenantService
	featureSvc     ports.FeatureFlagService
	auditSvc       ports.AuditService
	permissionSvc  ports.PermissionService
	accessControl  ports.AccessControlService
	middleware     *customMiddleware.MiddlewareCollection
	healthCheckers []ports.HealthChecker
}

func NewServer(serverConfig *ServerConfig, jwtSecret string, logger *logrus.Logger, deps ServerDeps) *Server {
	e := echo.New()

	server := &Server{
		echo:           e,
		config:         serverConfig,
		logger:         logger,
		userService:    deps.UserService,
		authSvc:        deps.AuthService,
		tenantService:  deps.TenantService,
		featureSvc:     deps.FeatureFlagService,
		auditSvc:       deps.AuditService,
		permissionSvc:  deps.PermissionService,
		accessControl:  deps.AccessControlService,
		healthCheckers: deps.HealthCheckers,
		middleware: customMiddleware.NewMiddlewareCollection(
			deps.AuthService,
			deps.TenantService,
			deps.UserService,
			deps.PermissionService,
			deps.AccessControlService,
			deps.RateLimiterService,
			logger,
			jwtSecret,
			GetRequestsTotal(),
			GetRequestDuration(),
		),
	}

	server.setupMiddleware()
	server.setupRoutes()

	return server
}
