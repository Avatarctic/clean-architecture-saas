package httpserver

import (
	"net/http"
	"strings"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/audit"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/permission"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/httpserver/helpers"
	"github.com/labstack/echo/v4"
)

func (s *Server) getAvailablePermissions(c echo.Context) error {
	permissions := permission.GetAllPermissions()
	categorized := permission.PermissionCategoryResponse{
		UserManagement:       []permission.Permission{},
		TenantManagement:     []permission.Permission{},
		FeatureFlags:         []permission.Permission{},
		PermissionManagement: []permission.Permission{},
		AuditMonitoring:      []permission.Permission{},
	}
	for _, perm := range permissions {
		permStr := string(perm)
		switch {
		case contains(permStr, "user", "profile", "password", "email"):
			categorized.UserManagement = append(categorized.UserManagement, perm)
		case contains(permStr, "tenant"):
			categorized.TenantManagement = append(categorized.TenantManagement, perm)
		case contains(permStr, "feature"):
			categorized.FeatureFlags = append(categorized.FeatureFlags, perm)
		case contains(permStr, "permission"):
			categorized.PermissionManagement = append(categorized.PermissionManagement, perm)
		case contains(permStr, "audit", "metrics", "alerting"):
			categorized.AuditMonitoring = append(categorized.AuditMonitoring, perm)
		}
	}
	response := permission.GetAvailablePermissionsResponse{
		Permissions:            permissions,
		CategorizedPermissions: categorized,
	}
	return c.JSON(http.StatusOK, response)
}

func (s *Server) getRolePermissions(c echo.Context) error {
	roleStr := c.Param("role")
	role := user.UserRole(roleStr)
	if !role.IsValid() {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid role")
	}
	permissions, err := s.permissionSvc.GetRolePermissions(c.Request().Context(), role)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "Failed to get role permissions")
	}
	return c.JSON(http.StatusOK, permission.GetRolePermissionsResponse{Role: role, Permissions: permissions})
}

func (s *Server) addPermissionToRole(c echo.Context) error {
	roleStr := c.Param("role")
	role := user.UserRole(roleStr)
	if !role.IsValid() {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid role")
	}
	var req permission.AddPermissionToRoleRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid request body")
	}
	if err := c.Validate(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}
	req.Role = role
	if !req.Permission.IsValid() {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid permission")
	}
	err := s.permissionSvc.AddPermissionToRole(c.Request().Context(), req.Role, req.Permission)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "Failed to add permission to role")
	}
	if s.auditSvc != nil {
		actorID, _ := helpers.GetUserIDFromContext(c)
		tenantID, _ := helpers.GetTenantIDFromContext(c)
		_ = s.auditSvc.LogAction(c.Request().Context(), &audit.CreateAuditLogRequest{
			TenantID:  tenantID,
			UserID:    &actorID,
			Action:    audit.ActionUpdate,
			Resource:  audit.ResourcePermission,
			Details:   map[string]any{"role": req.Role, "permission": req.Permission},
			IPAddress: c.RealIP(),
			UserAgent: c.Request().UserAgent(),
		})
	}
	return c.JSON(http.StatusOK, map[string]string{"message": "Permission added successfully"})
}

func (s *Server) removePermissionFromRole(c echo.Context) error {
	roleStr := c.Param("role")
	role := user.UserRole(roleStr)
	if !role.IsValid() {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid role")
	}
	permissionStr := c.Param("permission")
	perm := permission.Permission(permissionStr)
	if !perm.IsValid() {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid permission")
	}
	err := s.permissionSvc.RemovePermissionFromRole(c.Request().Context(), role, perm)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "Failed to remove permission from role")
	}
	if s.auditSvc != nil {
		actorID, _ := helpers.GetUserIDFromContext(c)
		tenantID, _ := helpers.GetTenantIDFromContext(c)
		_ = s.auditSvc.LogAction(c.Request().Context(), &audit.CreateAuditLogRequest{
			TenantID:  tenantID,
			UserID:    &actorID,
			Action:    audit.ActionUpdate,
			Resource:  audit.ResourcePermission,
			Details:   map[string]any{"role": role, "permission": perm},
			IPAddress: c.RealIP(),
			UserAgent: c.Request().UserAgent(),
		})
	}
	return c.JSON(http.StatusOK, map[string]string{"message": "Permission removed successfully"})
}

func (s *Server) setRolePermissions(c echo.Context) error {
	roleStr := c.Param("role")
	role := user.UserRole(roleStr)
	if !role.IsValid() {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid role")
	}
	var req permission.SetRolePermissionsRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid request body")
	}
	if err := c.Validate(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}
	req.Role = role
	for _, perm := range req.Permissions {
		if !perm.IsValid() {
			return echo.NewHTTPError(http.StatusBadRequest, "Invalid permission: "+string(perm))
		}
	}
	err := s.permissionSvc.SetRolePermissions(c.Request().Context(), req.Role, req.Permissions)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "Failed to set role permissions")
	}
	if s.auditSvc != nil {
		actorID, _ := helpers.GetUserIDFromContext(c)
		tenantID, _ := helpers.GetTenantIDFromContext(c)
		_ = s.auditSvc.LogAction(c.Request().Context(), &audit.CreateAuditLogRequest{
			TenantID:  tenantID,
			UserID:    &actorID,
			Action:    audit.ActionUpdate,
			Resource:  audit.ResourcePermission,
			Details:   map[string]any{"role": req.Role, "permissions": req.Permissions},
			IPAddress: c.RealIP(),
			UserAgent: c.Request().UserAgent(),
		})
	}
	return c.JSON(http.StatusOK, map[string]string{"message": "Role permissions updated successfully"})
}

func contains(s string, substrs ...string) bool {
	for _, substr := range substrs {
		if strings.Contains(s, substr) {
			return true
		}
	}
	return false
}
