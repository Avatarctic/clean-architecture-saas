package httpserver

import (
	"context"
	"fmt"
	"net/http"
	"strconv"

	"github.com/avatarctic/clean-architecture-saas/go/internal/application/services"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/audit"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/tenant"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/httpserver/helpers"
	"github.com/google/uuid"
	"github.com/labstack/echo/v4"
)

func (s *Server) createTenant(c echo.Context) error {
	var req tenant.CreateTenantRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid request body")
	}
	if err := c.Validate(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}
	t, err := s.tenantService.CreateTenant(c.Request().Context(), &req)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, err.Error())
	}

	// Audit: tenant created
	if s.auditSvc != nil && helpers.GetAuditEnabled(c) {
		tenantID := t.ID
		// acting user may be nil for self-service or system actions
		actorID, _ := helpers.GetUserIDFromContext(c)
		ctxWithAudit := context.WithValue(c.Request().Context(), services.AuditEnabledCtxKey, helpers.GetAuditEnabled(c))
		details := map[string]any{"created": true}
		if helpers.GetAuditEnabled(c) {
			details["name"] = t.Name
			details["plan"] = t.Plan
		}
		_ = s.auditSvc.LogAction(ctxWithAudit, &audit.CreateAuditLogRequest{
			TenantID:   tenantID,
			UserID:     &actorID,
			Action:     audit.ActionCreate,
			Resource:   audit.ResourceTenant,
			ResourceID: &tenantID,
			Details:    details,
			IPAddress:  c.RealIP(),
			UserAgent:  c.Request().UserAgent(),
		})
	}
	return c.JSON(http.StatusCreated, t)
}

func (s *Server) getTenant(c echo.Context) error {
	targetTenantID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid tenant ID")
	}
	t, err := s.tenantService.GetTenant(c.Request().Context(), targetTenantID)
	if err != nil {
		return echo.NewHTTPError(http.StatusNotFound, err.Error())
	}
	return c.JSON(http.StatusOK, t)
}

func (s *Server) updateTenant(c echo.Context) error {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid tenant ID")
	}
	var req tenant.UpdateTenantRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid request body")
	}

	// Prevent status changes in general update - use dedicated status endpoints
	if req.Status != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "status changes not allowed in update endpoint, use dedicated status endpoints")
	}

	if err := c.Validate(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}
	t, err := s.tenantService.UpdateTenant(c.Request().Context(), id, &req)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, err.Error())
	}
	return c.JSON(http.StatusOK, t)
}

func (s *Server) listTenants(c echo.Context) error {
	limit := 20
	offset := 0
	if l := c.QueryParam("limit"); l != "" {
		if v, err := strconv.Atoi(l); err == nil {
			limit = v
		}
	}
	if o := c.QueryParam("offset"); o != "" {
		if v, err := strconv.Atoi(o); err == nil {
			offset = v
		}
	}
	ts, total, err := s.tenantService.ListTenants(c.Request().Context(), limit, offset)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, err.Error())
	}
	return c.JSON(http.StatusOK, map[string]interface{}{"tenants": ts, "total": total, "limit": limit, "offset": offset})
}

// createUserInTenant creates a user in a specific tenant (for super admin operations)
func (s *Server) createUserInTenant(c echo.Context) error {
	var req user.CreateUserRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid request body")
	}

	if err := c.Validate(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}

	// Get target tenant ID from URL parameter
	tenantID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid tenant ID")
	}

	createdUser, err := s.userService.CreateUserInTenant(c.Request().Context(), &req, tenantID)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "failed to create user")
	}

	if s.auditSvc != nil && helpers.GetAuditEnabled(c) {
		// Log user creation within tenant
		actorID, _ := helpers.GetUserIDFromContext(c)
		ctxWithAudit := context.WithValue(c.Request().Context(), services.AuditEnabledCtxKey, helpers.GetAuditEnabled(c))
		details := map[string]any{"created": true}
		if helpers.GetAuditEnabled(c) {
			details["email"] = createdUser.Email
			details["role"] = createdUser.Role
		}
		_ = s.auditSvc.LogAction(ctxWithAudit, &audit.CreateAuditLogRequest{
			TenantID:   tenantID,
			UserID:     &actorID,
			Action:     audit.ActionCreate,
			Resource:   audit.ResourceUser,
			ResourceID: &createdUser.ID,
			Details:    details,
			IPAddress:  c.RealIP(),
			UserAgent:  c.Request().UserAgent(),
		})
	}

	return c.JSON(http.StatusCreated, createdUser)
}

// Status management handlers

func (s *Server) suspendTenant(c echo.Context) error {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid tenant ID")
	}

	// Get current tenant
	currentTenant, err := helpers.GetTenantFromContext(c)
	if err != nil {
		return echo.NewHTTPError(http.StatusNotFound, err.Error())
	}

	// Check if suspension is valid
	if !currentTenant.CanTransitionTo(tenant.TenantStatusSuspended) {
		return echo.NewHTTPError(http.StatusBadRequest,
			fmt.Sprintf("cannot suspend tenant in %s status", currentTenant.Status))
	}

	// Update status
	suspendedStatus := tenant.TenantStatusSuspended
	req := &tenant.UpdateTenantRequest{
		Status: &suspendedStatus,
	}

	updatedTenant, err := s.tenantService.UpdateTenant(c.Request().Context(), id, req)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, err.Error())
	}

	if s.auditSvc != nil && helpers.GetAuditEnabled(c) {
		actorID, _ := helpers.GetUserIDFromContext(c)
		ctxWithAudit := context.WithValue(c.Request().Context(), services.AuditEnabledCtxKey, helpers.GetAuditEnabled(c))
		details := map[string]any{"status": updatedTenant.Status}
		if helpers.GetAuditEnabled(c) {
			details["name"] = updatedTenant.Name
		}
		_ = s.auditSvc.LogAction(ctxWithAudit, &audit.CreateAuditLogRequest{
			TenantID:   id,
			UserID:     &actorID,
			Action:     audit.ActionUpdate,
			Resource:   audit.ResourceTenant,
			ResourceID: &id,
			Details:    details,
			IPAddress:  c.RealIP(),
			UserAgent:  c.Request().UserAgent(),
		})
	}

	return c.JSON(http.StatusOK, updatedTenant)
}

func (s *Server) activateTenant(c echo.Context) error {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid tenant ID")
	}

	// Get target tenant
	targetTenant, err := helpers.GetTenantFromContext(c)
	if err != nil {
		return echo.NewHTTPError(http.StatusNotFound, err.Error())
	}

	// Check if activation is valid
	if !targetTenant.CanTransitionTo(tenant.TenantStatusActive) {
		return echo.NewHTTPError(http.StatusBadRequest,
			fmt.Sprintf("cannot activate tenant in %s status", targetTenant.Status))
	}

	// Update status
	activeStatus := tenant.TenantStatusActive
	req := &tenant.UpdateTenantRequest{
		Status: &activeStatus,
	}

	updatedTenant, err := s.tenantService.UpdateTenant(c.Request().Context(), id, req)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, err.Error())
	}

	if s.auditSvc != nil && helpers.GetAuditEnabled(c) {
		actorID, _ := helpers.GetUserIDFromContext(c)
		ctxWithAudit := context.WithValue(c.Request().Context(), services.AuditEnabledCtxKey, helpers.GetAuditEnabled(c))
		details := map[string]any{"status": updatedTenant.Status}
		_ = s.auditSvc.LogAction(ctxWithAudit, &audit.CreateAuditLogRequest{
			TenantID:   id,
			UserID:     &actorID,
			Action:     audit.ActionUpdate,
			Resource:   audit.ResourceTenant,
			ResourceID: &id,
			Details:    details,
			IPAddress:  c.RealIP(),
			UserAgent:  c.Request().UserAgent(),
		})
	}

	return c.JSON(http.StatusOK, updatedTenant)
}

func (s *Server) cancelTenant(c echo.Context) error {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid tenant ID")
	}

	// Get current tenant
	currentTenant, err := helpers.GetTenantFromContext(c)
	if err != nil {
		return echo.NewHTTPError(http.StatusNotFound, err.Error())
	}

	// Check if cancellation is valid
	if !currentTenant.CanTransitionTo(tenant.TenantStatusCanceled) {
		return echo.NewHTTPError(http.StatusBadRequest,
			fmt.Sprintf("cannot cancel tenant in %s status", currentTenant.Status))
	}

	// Update status
	canceledStatus := tenant.TenantStatusCanceled
	req := &tenant.UpdateTenantRequest{
		Status: &canceledStatus,
	}

	updatedTenant, err := s.tenantService.UpdateTenant(c.Request().Context(), id, req)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, err.Error())
	}

	if s.auditSvc != nil && helpers.GetAuditEnabled(c) {
		actorID, _ := helpers.GetUserIDFromContext(c)
		ctxWithAudit := context.WithValue(c.Request().Context(), services.AuditEnabledCtxKey, helpers.GetAuditEnabled(c))
		_ = s.auditSvc.LogAction(ctxWithAudit, &audit.CreateAuditLogRequest{
			TenantID:   id,
			UserID:     &actorID,
			Action:     audit.ActionUpdate,
			Resource:   audit.ResourceTenant,
			ResourceID: &id,
			Details:    map[string]any{"status": updatedTenant.Status},
			IPAddress:  c.RealIP(),
			UserAgent:  c.Request().UserAgent(),
		})
	}

	return c.JSON(http.StatusOK, updatedTenant)
}
