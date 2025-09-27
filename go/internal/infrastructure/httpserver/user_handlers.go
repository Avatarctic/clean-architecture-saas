package httpserver

import (
	"context"
	"net/http"
	"strconv"

	"github.com/avatarctic/clean-architecture-saas/go/internal/application/services"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/audit"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/httpserver/helpers"
	"github.com/google/uuid"
	"github.com/labstack/echo/v4"
)

// User handlers
func (s *Server) createUser(c echo.Context) error {
	// Validate tenant status first
	_, err := helpers.GetActiveTenantFromContext(c)
	if err != nil {
		return err
	}

	var req user.CreateUserRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid request body")
	}

	if err := c.Validate(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}

	tenantID, err := helpers.GetTenantIDFromContext(c)
	if err != nil {
		return err
	}

	createdUser, err := s.userService.CreateUser(c.Request().Context(), &req, tenantID)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "failed to create user")
	}

	// Audit log: user created
	if s.auditSvc != nil && helpers.GetAuditEnabled(c) {
		uID, _ := helpers.GetUserIDFromContext(c)
		ctxWithAudit := context.WithValue(c.Request().Context(), services.AuditEnabledCtxKey, helpers.GetAuditEnabled(c))
		details := map[string]any{"created": true}
		if helpers.GetAuditEnabled(c) {
			details["email"] = createdUser.Email
		}
		_ = s.auditSvc.LogAction(ctxWithAudit, &audit.CreateAuditLogRequest{
			TenantID:   tenantID,
			UserID:     &uID,
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

// getOwnProfile returns the current user's own profile (Case 1: Self-profile)
func (s *Server) getOwnProfile(c echo.Context) error {
	// Get user ID from JWT context
	// Prefer the full current user object from context (set by JWT middleware) to avoid DB roundtrip
	if userObj, err := helpers.GetCurrentUserFromContext(c); err == nil {
		return c.JSON(http.StatusOK, userObj)
	}

	// Fallback: fetch by ID if middleware did not populate the full user
	userID, err := helpers.GetUserIDFromContext(c)
	if err != nil {
		return err
	}

	userObj, err := s.userService.GetUser(c.Request().Context(), userID)
	if err != nil {
		return echo.NewHTTPError(http.StatusNotFound, "user not found")
	}

	return c.JSON(http.StatusOK, userObj)
}

func (s *Server) getUser(c echo.Context) error {
	// Parse the requested user ID from URL parameter
	userID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid user ID")
	}

	// Get the requesting user's context
	currentUserID, err := helpers.GetUserIDFromContext(c)
	if err != nil {
		return err
	}

	currentTenantID, err := helpers.GetTenantIDFromContext(c)
	if err != nil {
		return err
	}

	// Expect AccessControl middleware to have preloaded the target user
	targetUser, err := helpers.GetTargetUserFromContext(c)
	if err != nil {
		// Avoid performing an extra DB read here. If the target user wasn't preloaded,
		// the route is likely misconfigured. Surface a clear 500 to help detect this.
		return echo.NewHTTPError(http.StatusInternalServerError, "target user not preloaded; ensure AccessControl middleware is applied")
	} else {
		// If target user was preloaded, still ensure same-tenant operations use active tenant check
		if userID != currentUserID && targetUser.TenantID == currentTenantID {
			if _, err := helpers.GetActiveTenantFromContext(c); err != nil {
				return err
			}
		}
	}

	return c.JSON(http.StatusOK, targetUser)
}

func (s *Server) updateUser(c echo.Context) error {
	userID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid user ID")
	}

	// Get the requesting user's tenant context
	currentTenantID, err := helpers.GetTenantIDFromContext(c)
	if err != nil {
		return err
	}

	// Use preloaded target if available to avoid duplicate DB calls
	// Expect AccessControl middleware to have preloaded the target user
	targetUser, err := helpers.GetTargetUserFromContext(c)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "target user not preloaded; ensure AccessControl middleware is applied")
	}

	// If this is a same-tenant operation ensure tenant is active
	if targetUser.TenantID == currentTenantID {
		if _, err := helpers.GetActiveTenantFromContext(c); err != nil {
			return err
		}
	}

	var req user.UpdateUserRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid request body")
	}

	updatedUser, err := s.userService.UpdateUser(c.Request().Context(), userID, &req)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "failed to update user")
	}

	// Audit log: user updated
	if s.auditSvc != nil && helpers.GetAuditEnabled(c) {
		uID, _ := helpers.GetUserIDFromContext(c)
		ctxWithAudit := context.WithValue(c.Request().Context(), services.AuditEnabledCtxKey, helpers.GetAuditEnabled(c))
		details := map[string]any{"updated": true}
		if helpers.GetAuditEnabled(c) {
			details["fields"] = req
		}
		_ = s.auditSvc.LogAction(ctxWithAudit, &audit.CreateAuditLogRequest{
			TenantID:   updatedUser.TenantID,
			UserID:     &uID,
			Action:     audit.ActionUpdate,
			Resource:   audit.ResourceUser,
			ResourceID: &updatedUser.ID,
			Details:    details,
			IPAddress:  c.RealIP(),
			UserAgent:  c.Request().UserAgent(),
		})
	}

	return c.JSON(http.StatusOK, updatedUser)
}

func (s *Server) deleteUser(c echo.Context) error {
	userID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid user ID")
	}

	// Get the requesting user's context
	currentUserID, err := helpers.GetUserIDFromContext(c)
	if err != nil {
		return err
	}

	// Prevent users from deleting themselves
	if userID == currentUserID {
		return echo.NewHTTPError(http.StatusBadRequest, "users cannot delete themselves")
	}

	currentTenantID, err := helpers.GetTenantIDFromContext(c)
	if err != nil {
		return err
	}

	// Use preloaded target if available and perform tenant active check for same-tenant
	// Expect AccessControl middleware to have preloaded the target user
	targetUser, err := helpers.GetTargetUserFromContext(c)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "target user not preloaded; ensure AccessControl middleware is applied")
	}

	if targetUser.TenantID == currentTenantID {
		if _, err := helpers.GetActiveTenantFromContext(c); err != nil {
			return err
		}
	}

	if err := s.userService.DeleteUser(c.Request().Context(), userID); err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "failed to delete user")
	}

	// Audit log: user deleted
	if s.auditSvc != nil && helpers.GetAuditEnabled(c) {
		uID, _ := helpers.GetUserIDFromContext(c)
		ctxWithAudit := context.WithValue(c.Request().Context(), services.AuditEnabledCtxKey, helpers.GetAuditEnabled(c))
		details := map[string]any{"deleted": true}
		if helpers.GetAuditEnabled(c) {
			details["email"] = targetUser.Email
		}
		_ = s.auditSvc.LogAction(ctxWithAudit, &audit.CreateAuditLogRequest{
			TenantID:   targetUser.TenantID,
			UserID:     &uID,
			Action:     audit.ActionDelete,
			Resource:   audit.ResourceUser,
			ResourceID: &userID,
			Details:    details,
			IPAddress:  c.RealIP(),
			UserAgent:  c.Request().UserAgent(),
		})
	}

	return c.NoContent(http.StatusNoContent)
}

func (s *Server) listTenantUsers(c echo.Context) error {
	// Validate tenant status first
	_, err := helpers.GetActiveTenantFromContext(c)
	if err != nil {
		return err
	}

	tenantID, err := helpers.GetTenantIDFromContext(c)
	if err != nil {
		return err
	}

	// Parse pagination parameters
	limit, _ := strconv.Atoi(c.QueryParam("limit"))
	if limit <= 0 {
		limit = 20
	}
	if limit > 100 {
		limit = 100
	}

	offset, _ := strconv.Atoi(c.QueryParam("offset"))
	if offset < 0 {
		offset = 0
	}

	users, total, err := s.userService.ListUsers(c.Request().Context(), tenantID, limit, offset)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "failed to list users")
	}

	response := map[string]interface{}{
		"users":  users,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	}

	return c.JSON(http.StatusOK, response)
}

// Email verification handlers
func (s *Server) verifyEmail(c echo.Context) error {
	var token string

	// Support both GET (from email links) and POST (API calls)
	if c.Request().Method == "GET" {
		token = c.QueryParam("token")
		if token == "" {
			return c.HTML(http.StatusBadRequest, `
                <!DOCTYPE html>
                <html>
                <head><title>Verification Failed</title></head>
                <body>
                    <h1>Verification Failed</h1>
                    <p>Missing verification token.</p>
                    <a href="/resend-verification">Request New Verification Email</a>
                </body>
                </html>
            `)
		}
	} else {
		// POST request - JSON body
		var req user.VerifyEmailRequest
		if err := c.Bind(&req); err != nil {
			return echo.NewHTTPError(http.StatusBadRequest, "invalid request body")
		}
		if err := c.Validate(&req); err != nil {
			return echo.NewHTTPError(http.StatusBadRequest, err.Error())
		}
		token = req.Token
	}

	verifiedUser, err := s.userService.VerifyEmail(c.Request().Context(), token)
	if err != nil {
		if c.Request().Method == "GET" {
			return c.HTML(http.StatusBadRequest, `
				<!DOCTYPE html>
				<html>
				<head><title>Verification Failed</title></head>
				<body>
					<h1>Verification Failed</h1>
					<p>The verification link is invalid or has expired.</p>
					<a href="/resend-verification">Request New Verification Email</a>
				</body>
				</html>
			`)
		}
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}

	// Audit log: email verified
	if s.auditSvc != nil && verifiedUser != nil && helpers.GetAuditEnabled(c) {
		ctxWithAudit := context.WithValue(c.Request().Context(), services.AuditEnabledCtxKey, helpers.GetAuditEnabled(c))
		_ = s.auditSvc.LogAction(ctxWithAudit, &audit.CreateAuditLogRequest{
			TenantID:   verifiedUser.TenantID,
			UserID:     &verifiedUser.ID,
			Action:     audit.ActionUpdate,
			Resource:   audit.ResourceUser,
			ResourceID: &verifiedUser.ID,
			Details:    map[string]any{"email_verified": true},
			IPAddress:  c.RealIP(),
			UserAgent:  c.Request().UserAgent(),
		})
	}

	if c.Request().Method == "GET" {
		return c.HTML(http.StatusOK, `
            <!DOCTYPE html>
            <html>
            <head><title>Email Verified</title></head>
            <body>
                <h1>Email Verified Successfully!</h1>
                <p>Your email has been verified. You can now close this window.</p>
                <a href="/login">Continue to Login</a>
            </body>
            </html>
        `)
	}

	return c.JSON(http.StatusOK, map[string]interface{}{
		"message":  "email verified successfully",
		"verified": true,
	})
}

func (s *Server) resendVerificationEmail(c echo.Context) error {
	var req user.ResendVerificationRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid request body")
	}

	if err := c.Validate(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}

	if err := s.userService.ResendVerificationEmail(c.Request().Context(), req.Email); err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, err.Error())
	}

	// Audit log: verification email resent (global context)
	if s.auditSvc != nil && helpers.GetAuditEnabled(c) {
		ctxWithAudit := context.WithValue(c.Request().Context(), services.AuditEnabledCtxKey, helpers.GetAuditEnabled(c))
		details := map[string]any{"resend_verification": true}
		if helpers.GetAuditEnabled(c) {
			details["email"] = req.Email
		}
		_ = s.auditSvc.LogAction(ctxWithAudit, &audit.CreateAuditLogRequest{
			TenantID:   uuid.Nil,
			UserID:     nil,
			Action:     audit.ActionUpdate,
			Resource:   audit.ResourceUser,
			ResourceID: nil,
			Details:    details,
			IPAddress:  c.RealIP(),
			UserAgent:  c.Request().UserAgent(),
		})
	}

	return c.JSON(http.StatusOK, map[string]string{
		"message": "verification email sent successfully",
	})
}

// requestEmailUpdate handles email update requests
func (s *Server) requestEmailUpdate(c echo.Context) error {
	userID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid user ID")
	}

	// Get the requesting user's context
	currentUserID, err := helpers.GetUserIDFromContext(c)
	if err != nil {
		return err
	}

	currentTenantID, err := helpers.GetTenantIDFromContext(c)
	if err != nil {
		return err
	}

	// Use preloaded target if available and ensure tenant active for same-tenant
	// Expect AccessControl middleware to have preloaded the target user
	targetUser, err := helpers.GetTargetUserFromContext(c)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "target user not preloaded; ensure AccessControl middleware is applied")
	}

	if userID != currentUserID && targetUser.TenantID == currentTenantID {
		if _, err := helpers.GetActiveTenantFromContext(c); err != nil {
			return err
		}
	}

	var req user.UpdateEmailRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid request body")
	}

	if err := c.Validate(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}

	if err := s.userService.RequestEmailUpdate(c.Request().Context(), userID, &req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}

	// Audit log: email update requested
	if s.auditSvc != nil && helpers.GetAuditEnabled(c) {
		ctxWithAudit := context.WithValue(c.Request().Context(), services.AuditEnabledCtxKey, helpers.GetAuditEnabled(c))
		uID, _ := helpers.GetUserIDFromContext(c)
		details := map[string]any{"email_update_requested": true}
		if helpers.GetAuditEnabled(c) {
			details["new_email"] = req.NewEmail
		}
		_ = s.auditSvc.LogAction(ctxWithAudit, &audit.CreateAuditLogRequest{
			TenantID:   targetUser.TenantID,
			UserID:     &uID,
			Action:     audit.ActionUpdate,
			Resource:   audit.ResourceUser,
			ResourceID: &userID,
			Details:    details,
			IPAddress:  c.RealIP(),
			UserAgent:  c.Request().UserAgent(),
		})
	}

	return c.JSON(http.StatusOK, map[string]string{
		"message": "email update confirmation sent to your new email address",
	})
}

// confirmEmailUpdate handles email update confirmation
func (s *Server) confirmEmailUpdate(c echo.Context) error {
	var token string

	// Support both GET (from email links) and POST (API calls)
	if c.Request().Method == "GET" {
		token = c.QueryParam("token")
		if token == "" {
			return c.HTML(http.StatusBadRequest, `
                <!DOCTYPE html>
                <html>
                <head><title>Email Update Failed</title></head>
                <body>
                    <h1>Email Update Failed</h1>
                    <p>Missing email update token.</p>
                </body>
                </html>
            `)
		}
	} else {
		// POST request - JSON body
		var req user.ConfirmEmailUpdateRequest
		if err := c.Bind(&req); err != nil {
			return echo.NewHTTPError(http.StatusBadRequest, "invalid request body")
		}
		if err := c.Validate(&req); err != nil {
			return echo.NewHTTPError(http.StatusBadRequest, err.Error())
		}
		token = req.Token
	}

	updatedUser, err := s.userService.ConfirmEmailUpdate(c.Request().Context(), token)
	if err != nil {
		if c.Request().Method == "GET" {
			return c.HTML(http.StatusBadRequest, `
                <!DOCTYPE html>
                <html>
                <head><title>Email Update Failed</title></head>
                <body>
                    <h1>Email Update Failed</h1>
                    <p>The email update link is invalid or has expired.</p>
                </body>
                </html>
            `)
		}
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}

	// Audit log: email update confirmed
	if s.auditSvc != nil && updatedUser != nil && helpers.GetAuditEnabled(c) {
		ctxWithAudit := context.WithValue(c.Request().Context(), services.AuditEnabledCtxKey, helpers.GetAuditEnabled(c))
		details := map[string]any{"email_updated": true}
		if helpers.GetAuditEnabled(c) {
			details["email"] = updatedUser.Email
		}
		_ = s.auditSvc.LogAction(ctxWithAudit, &audit.CreateAuditLogRequest{
			TenantID:   updatedUser.TenantID,
			UserID:     &updatedUser.ID,
			Action:     audit.ActionUpdate,
			Resource:   audit.ResourceUser,
			ResourceID: &updatedUser.ID,
			Details:    details,
			IPAddress:  c.RealIP(),
			UserAgent:  c.Request().UserAgent(),
		})
	}

	if c.Request().Method == "GET" {
		return c.HTML(http.StatusOK, `
            <!DOCTYPE html>
            <html>
            <head><title>Email Updated</title></head>
            <body>
                <h1>Email Updated Successfully!</h1>
                <p>Your email address has been updated. You will receive a verification email at your new address.</p>
                <a href="/login">Continue to Login</a>
            </body>
            </html>
        `)
	}

	return c.JSON(http.StatusOK, map[string]interface{}{
		"message": "email updated successfully",
		"updated": true,
	})
}

// ChangePasswordRequest represents the request to change a user's password
type ChangePasswordRequest struct {
	OldPassword string `json:"old_password" validate:"required"`
	NewPassword string `json:"new_password" validate:"required,min=8"`
}

// changePassword handles password change requests
func (s *Server) changePassword(c echo.Context) error {
	userID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid user ID")
	}

	// Get the requesting user's context
	currentUserID, err := helpers.GetUserIDFromContext(c)
	if err != nil {
		return err
	}

	currentTenantID, err := helpers.GetTenantIDFromContext(c)
	if err != nil {
		return err
	}

	// Expect AccessControl middleware to have preloaded the target user
	targetUser, err := helpers.GetTargetUserFromContext(c)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "target user not preloaded; ensure AccessControl middleware is applied")
	}

	if userID != currentUserID && targetUser.TenantID == currentTenantID {
		if _, err := helpers.GetActiveTenantFromContext(c); err != nil {
			return err
		}
	}

	var req ChangePasswordRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid request body")
	}
	if err := c.Validate(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}

	if err := s.userService.ChangePassword(c.Request().Context(), userID, req.OldPassword, req.NewPassword); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}

	// Audit log: password changed
	if s.auditSvc != nil && helpers.GetAuditEnabled(c) {
		ctxWithAudit := context.WithValue(c.Request().Context(), services.AuditEnabledCtxKey, helpers.GetAuditEnabled(c))
		uID, _ := helpers.GetUserIDFromContext(c)
		details := map[string]any{"password_changed": true}
		// Do not include any PII in password-change audit even when enabled; only indicate the event
		auditReq := audit.CreateAuditLogRequest{
			TenantID:   targetUser.TenantID,
			UserID:     &uID,
			Action:     audit.ActionUpdate,
			Resource:   audit.ResourceUser,
			ResourceID: &userID,
			Details:    details,
			IPAddress:  c.RealIP(),
			UserAgent:  c.Request().UserAgent(),
		}
		_ = s.auditSvc.LogAction(ctxWithAudit, &auditReq)
	}

	return c.JSON(http.StatusOK, map[string]string{"message": "password changed successfully"})
}
