package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	config "github.com/avatarctic/clean-architecture-saas/go/configs"
	"github.com/avatarctic/clean-architecture-saas/go/internal/application/services"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/db"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/email"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/health"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/httpserver"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/redis"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/repositories"
	"github.com/sirupsen/logrus"
)

func main() {
	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatal("Failed to load configuration:", err)
	}

	// Setup logger
	logger := logrus.New()
	logger.SetFormatter(&logrus.JSONFormatter{})
	level, err := logrus.ParseLevel(cfg.Log.Level)
	if err != nil {
		logger.SetLevel(logrus.InfoLevel)
	} else {
		logger.SetLevel(level)
	}

	logger.Info("Starting Clean Architecture SaaS application...")

	// Initialize database (apply pool settings from config)
	database, err := db.NewDatabaseWithConfig(&cfg.Database)
	if err != nil {
		logger.Fatal("Failed to connect to database:", err)
	}
	defer database.Close()

	logger.Info("Connected to database successfully")

	// Initialize Redis client
	redisClient, err := redis.NewRedisClient(&cfg.Redis)
	if err != nil {
		logger.Fatal("Failed to connect to Redis:", err)
	}
	defer redisClient.Close()

	logger.Info("Connected to Redis successfully")

	// Run migrations
	if err := database.Migrate("./migrations"); err != nil {
		logger.Warn("Failed to run migrations:", err)
	}

	// Initialize Redis repository implementations (pass logger)
	redisTokenRepo := repositories.NewTokenRedisRepository(redisClient, logger)
	redisEmailTokenRepo := repositories.NewEmailTokenRedisRepository(redisClient, logger)
	redisRateLimitRepo := repositories.NewRateLimitRedisRepository(redisClient)

	// Initialize generic Redis cache for read-heavy entities
	redisCache := redis.NewRedisCache(redisClient, "appcache")

	// Initialize all db repository implementations
	baseUserRepo := repositories.NewUserRepository(database, logger)
	baseTenantRepo := repositories.NewTenantRepository(database, logger)
	baseFeatureFlagRepo := repositories.NewFeatureFlagRepository(database)
	basePermissionRepo := repositories.NewPermissionRepository(database, logger)
	auditRepo := repositories.NewAuditRepository(database, logger)
	dbTokenRepo := repositories.NewTokenDBRepository(database, logger)

	// Decorate with caching (choose TTLs)
	tenantRepo := repositories.NewCachingTenantRepository(baseTenantRepo, redisCache, 10*time.Minute)
	userRepo := repositories.NewCachingUserRepository(baseUserRepo, redisCache, 3*time.Minute)
	featureFlagRepo := repositories.NewCachingFeatureFlagRepository(baseFeatureFlagRepo, redisCache, 30*time.Minute)
	permissionRepo := repositories.NewCachingPermissionRepository(basePermissionRepo, redisCache, 30*time.Minute)

	tokenRepo := repositories.NewTokenRepository(dbTokenRepo, redisTokenRepo, logger)

	// Initialize services with proper repository dependencies
	emailConfig := &email.EmailConfig{
		SendGridAPIKey: cfg.Email.SendGridAPIKey,
		FromEmail:      cfg.Email.FromEmail,
		FromName:       cfg.Email.FromName,
		CompanyName:    cfg.Email.CompanyName,
		BaseURL:        cfg.Email.BaseURL,
	}
	emailService, err := email.NewEmailService(emailConfig, logger)
	if err != nil {
		logger.Fatal("Failed to initialize email service:", err)
	}

	// Wire all services with their repository dependencies
	userService := services.NewUserService(userRepo, emailService, tenantRepo, tokenRepo, redisEmailTokenRepo, logger)

	// Create JWT configuration using canonical configs.JWTConfig
	jwtConfig := &config.JWTConfig{
		Secret:          cfg.JWT.Secret,
		AccessTokenTTL:  cfg.JWT.AccessTokenTTL,
		RefreshTokenTTL: cfg.JWT.RefreshTokenTTL,
		SessionTimeout:  cfg.JWT.SessionTimeout,
	}

	authService := services.NewAuthService(userRepo, tenantRepo, tokenRepo, jwtConfig, logger)
	tenantService := services.NewTenantService(tenantRepo, userRepo, userService, emailService, logger)
	featureService := services.NewFeatureFlagService(featureFlagRepo)
	auditService := services.NewAuditService(auditRepo, logger)
	permissionService := services.NewPermissionService(permissionRepo, logger)
	accessControlService := services.NewAccessControlService(userService, tenantService, permissionService)

	rateLimiterConfig := &services.RateLimiterConfig{
		DefaultRequestsPerMinute: cfg.RateLimit.DefaultRequestsPerMinute,
		BurstMultiplier:          cfg.RateLimit.BurstMultiplier,
		Window:                   cfg.RateLimit.Window,
		KeyPrefix:                cfg.RateLimit.KeyPrefix,
	}
	rateLimiterService := services.NewRateLimiterService(redisRateLimitRepo, tenantRepo, rateLimiterConfig, logger)

	hcSlice := []ports.HealthChecker{health.NewDBHealthChecker(database), health.NewRedisHealthChecker(redisClient)}

	// Create server configuration
	serverConfig := &httpserver.ServerConfig{
		Host:           cfg.Server.Host,
		Port:           cfg.Server.Port,
		ReadTimeout:    cfg.Server.ReadTimeout,
		WriteTimeout:   cfg.Server.WriteTimeout,
		IdleTimeout:    cfg.Server.IdleTimeout,
		TLSCertFile:    cfg.Server.TLSCertFile,
		TLSKeyFile:     cfg.Server.TLSKeyFile,
		AllowedOrigins: cfg.Server.AllowedOrigins,
		Environment:    cfg.Server.Environment,
	}

	// Initialize HTTP server using ServerDeps for clearer wiring
	deps := httpserver.ServerDeps{
		UserService:          userService,
		AuthService:          authService,
		TenantService:        tenantService,
		FeatureFlagService:   featureService,
		AuditService:         auditService,
		PermissionService:    permissionService,
		AccessControlService: accessControlService,
		RateLimiterService:   rateLimiterService,
		HealthCheckers:       hcSlice,
	}

	server := httpserver.NewServer(serverConfig, cfg.JWT.Secret, logger, deps)

	// Start server in a goroutine
	go func() {
		if err := server.Start(); err != nil {
			logger.Fatal("Failed to start server:", err)
		}
	}()

	logger.Infof("Server started on %s:%s", cfg.Server.Host, cfg.Server.Port)

	// Wait for interrupt signal to gracefully shutdown the server
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Info("Shutting down server...")

	// Graceful shutdown with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		logger.Fatal("Server forced to shutdown:", err)
	}

	logger.Info("Server exited")
}
