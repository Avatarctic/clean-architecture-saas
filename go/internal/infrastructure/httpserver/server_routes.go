package httpserver

import (
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/permission"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
)

func (s *Server) setupRoutes() {
	s.echo.GET("/health", s.healthCheck)
	s.echo.GET("/metrics", s.metricsEndpoint)

	api := s.echo.Group("/api/v1")
	auth := api.Group("/auth")
	auth.POST("/login", s.login)
	auth.POST("/refresh", s.refreshToken)

	auth.GET("/verify-email", s.verifyEmail)
	auth.POST("/verify-email", s.verifyEmail)
	auth.POST("/resend-verification", s.resendVerificationEmail)

	auth.GET("/confirm-email-update", s.confirmEmailUpdate)
	auth.POST("/confirm-email-update", s.confirmEmailUpdate)

	protected := api.Group("")
	protected.Use(s.middleware.JWT.RequireJWT())

	protected.POST("/auth/logout", s.logout)
	protected.GET("/auth/sessions", s.getOwnActiveSessions, s.middleware.Perm.RequirePermission(permission.ViewOwnSessions))
	protected.DELETE("/auth/sessions/:token_hash", s.terminateOwnSession, s.middleware.Perm.RequirePermission(permission.TerminateOwnSessions))
	protected.DELETE("/auth/sessions", s.terminateAllOwnSessions, s.middleware.Perm.RequirePermission(permission.TerminateOwnSessions))

	users := protected.Group("/users")
	users.GET("", s.listTenantUsers, s.middleware.Perm.RequirePermission(permission.ReadTenantUsers))
	users.GET("/me", s.getOwnProfile, s.middleware.Perm.RequirePermission(permission.ReadOwnProfile))
	users.POST("", s.createUser, s.middleware.Perm.RequirePermission(permission.CreateTenantUser), s.middleware.RoleHierarchy.RequireRoleHierarchyForUserManagement())
	users.GET("/:id", s.getUser, s.middleware.AccessControl.RequireUserAction(ports.AccessActionReadUser), s.middleware.RoleHierarchy.RequireRoleHierarchyForUserManagement())
	users.GET("/:id/sessions", s.getUserSessions, s.middleware.AccessControl.PreloadTargetUser(), s.middleware.Perm.RequireAnyPermission(permission.ViewTenantSessions, permission.ViewAllSessions), s.middleware.RoleHierarchy.RequireRoleHierarchyForUserManagement())
	users.DELETE("/:id/sessions/:token_hash", s.terminateUserSession, s.middleware.AccessControl.PreloadTargetUser(), s.middleware.Perm.RequireAnyPermission(permission.TerminateTenantSessions, permission.TerminateAllSessions), s.middleware.RoleHierarchy.RequireRoleHierarchyForUserManagement())
	users.DELETE("/:id/sessions", s.terminateAllUserSessions, s.middleware.AccessControl.PreloadTargetUser(), s.middleware.Perm.RequireAnyPermission(permission.TerminateTenantSessions, permission.TerminateAllSessions), s.middleware.RoleHierarchy.RequireRoleHierarchyForUserManagement())
	users.PUT("/:id", s.updateUser, s.middleware.AccessControl.RequireUserAction(ports.AccessActionUpdateUser), s.middleware.RoleHierarchy.RequireRoleHierarchyForUserManagement())
	users.DELETE("/:id", s.deleteUser, s.middleware.AccessControl.RequireUserAction(ports.AccessActionDeleteUser), s.middleware.RoleHierarchy.RequireRoleHierarchyForUserManagement())
	users.POST("/:id/password", s.changePassword, s.middleware.AccessControl.RequireUserAction(ports.AccessActionChangePassword))
	users.PATCH("/:id/email", s.requestEmailUpdate, s.middleware.AccessControl.RequireUserAction(ports.AccessActionUpdateEmail))

	tenants := protected.Group("/tenants")
	tenants.GET("", s.listTenants, s.middleware.Perm.RequirePermission(permission.ReadAllTenants))
	tenants.POST("", s.createTenant, s.middleware.Perm.RequirePermission(permission.CreateTenant))
	tenants.GET("/:id", s.getTenant, s.middleware.Perm.RequireAnyPermission(permission.ReadOwnTenant, permission.ReadAllTenants))
	tenants.PUT("/:id", s.updateTenant, s.middleware.Perm.RequirePermission(permission.UpdateTenant))
	tenants.PUT("/:id/suspend", s.suspendTenant, s.middleware.Perm.RequirePermission(permission.ManageTenantStatus))
	tenants.PUT("/:id/activate", s.activateTenant, s.middleware.Perm.RequirePermission(permission.ManageTenantStatus))
	tenants.PUT("/:id/cancel", s.cancelTenant, s.middleware.Perm.RequirePermission(permission.ManageTenantStatus))
	tenants.POST("/:id/users", s.createUserInTenant, s.middleware.Perm.RequirePermission(permission.CreateAllUsers), s.middleware.RoleHierarchy.RequireRoleHierarchyForUserManagement())

	features := protected.Group("/features")
	features.GET("", s.listFeatureFlags, s.middleware.Perm.RequirePermission(permission.ReadFeatureFlag))
	features.POST("", s.createFeatureFlag, s.middleware.Perm.RequirePermission(permission.CreateFeatureFlag))
	features.PUT("/:id", s.updateFeatureFlag, s.middleware.Perm.RequirePermission(permission.UpdateFeatureFlag))
	features.DELETE("/:id", s.deleteFeatureFlag, s.middleware.Perm.RequirePermission(permission.DeleteFeatureFlag))
	features.POST("/evaluate", s.evaluateFeatureFlag, s.middleware.Perm.RequirePermission(permission.ReadFeatureFlag))

	audit := protected.Group("/audit")
	audit.GET("/logs", s.getAuditLogs, s.middleware.Perm.RequirePermission(permission.ViewAuditLog))

	permissions := protected.Group("/permissions")
	permissions.GET("", s.getAvailablePermissions, s.middleware.Perm.RequirePermission(permission.ViewPermissions))
	permissions.GET("/roles/:role", s.getRolePermissions, s.middleware.Perm.RequirePermission(permission.ViewPermissions))
	permissions.PUT("/roles/:role", s.setRolePermissions, s.middleware.Perm.RequirePermission(permission.ManagePermissions))
	permissions.POST("/roles/:role/permissions", s.addPermissionToRole, s.middleware.Perm.RequirePermission(permission.ManagePermissions))
	permissions.DELETE("/roles/:role/permissions/:permission", s.removePermissionFromRole, s.middleware.Perm.RequirePermission(permission.ManagePermissions))
}
