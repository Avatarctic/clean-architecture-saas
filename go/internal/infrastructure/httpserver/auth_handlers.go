package httpserver

import (
	"net/http"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/audit"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/auth"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/httpserver/helpers"
	"github.com/google/uuid"
	"github.com/labstack/echo/v4"
)

// Auth handlers
func (s *Server) login(c echo.Context) error {
	var req auth.LoginRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid request body")
	}

	if err := c.Validate(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}

	tokens, err := s.authSvc.Login(c.Request().Context(), &req)
	if err != nil {
		return echo.NewHTTPError(http.StatusUnauthorized, "invalid credentials")
	}

	// Audit login
	if s.auditSvc != nil {
		userID, _ := helpers.GetUserIDFromContext(c)
		tenantID, _ := helpers.GetTenantIDFromContext(c)
		_ = s.auditSvc.LogAction(c.Request().Context(), &audit.CreateAuditLogRequest{
			TenantID:   tenantID,
			UserID:     &userID,
			Action:     audit.ActionLogin,
			Resource:   audit.ResourceUser,
			ResourceID: &userID,
			Details:    map[string]any{"method": "password"},
			IPAddress:  c.RealIP(),
			UserAgent:  c.Request().UserAgent(),
		})
	}

	return c.JSON(http.StatusOK, tokens)
}

func (s *Server) refreshToken(c echo.Context) error {
	var req struct {
		RefreshToken string `json:"refresh_token" validate:"required"`
	}

	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid request body")
	}

	tokens, err := s.authSvc.RefreshToken(c.Request().Context(), req.RefreshToken)
	if err != nil {
		return echo.NewHTTPError(http.StatusUnauthorized, "invalid refresh token")
	}

	return c.JSON(http.StatusOK, tokens)
}

func (s *Server) logout(c echo.Context) error {
	token, err := helpers.GetJWTTokenFromContext(c)
	if err != nil {
		return err
	}

	// Extract user ID from context (set by JWT middleware)
	userID, err := helpers.GetUserIDFromContext(c)
	if err != nil {
		return err
	}

	// Logout from auth service (handles both token blacklisting and session cleanup)
	if err := s.authSvc.Logout(c.Request().Context(), userID, token); err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "failed to logout")
	}

	if s.auditSvc != nil {
		tenantID, _ := helpers.GetTenantIDFromContext(c)
		_ = s.auditSvc.LogAction(c.Request().Context(), &audit.CreateAuditLogRequest{
			TenantID:   tenantID,
			UserID:     &userID,
			Action:     audit.ActionLogout,
			Resource:   audit.ResourceUser,
			ResourceID: &userID,
			Details:    map[string]any{"token_hash": s.authSvc.GetTokenHash(token)},
			IPAddress:  c.RealIP(),
			UserAgent:  c.Request().UserAgent(),
		})
	}

	return c.NoContent(http.StatusOK)
}

// getOwnActiveSessions returns all active sessions for the current user
func (s *Server) getOwnActiveSessions(c echo.Context) error {
	userID, err := helpers.GetUserIDFromContext(c)
	if err != nil {
		return err
	}

	sessions, err := s.authSvc.GetUserSessions(c.Request().Context(), userID)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "failed to get user sessions")
	}

	return c.JSON(http.StatusOK, map[string]interface{}{
		"sessions": sessions,
		"count":    len(sessions),
	})
}

// terminateOwnSession terminates a specific session belonging to the current user
func (s *Server) terminateOwnSession(c echo.Context) error {
	userID, err := helpers.GetUserIDFromContext(c)
	if err != nil {
		return err
	}

	tokenHash := c.Param("token_hash")
	if tokenHash == "" {
		return echo.NewHTTPError(http.StatusBadRequest, "token_hash is required")
	}

	// Get current token hash to exclude from termination
	token, err := helpers.GetJWTTokenFromContext(c)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "unable to identify current session")
	}

	currentTokenHash := s.authSvc.GetTokenHash(token)
	if currentTokenHash == tokenHash {
		// Prevent termination of the current session
		return echo.NewHTTPError(http.StatusForbidden, "cannot terminate current session")
	}

	// Use the TerminateSession method with token hash
	err = s.authSvc.TerminateSession(c.Request().Context(), userID, tokenHash)
	if err != nil {
		if err.Error() == "session not found" {
			return echo.NewHTTPError(http.StatusNotFound, "session not found")
		}
		return echo.NewHTTPError(http.StatusInternalServerError, "failed to terminate session")
	}

	return c.JSON(http.StatusOK, map[string]string{
		"message": "session terminated successfully",
	})
}

// terminateAllOwnSessions terminates all sessions belonging to the current user except the current one
func (s *Server) terminateAllOwnSessions(c echo.Context) error {
	userID, err := helpers.GetUserIDFromContext(c)
	if err != nil {
		return err
	}

	// Get current token hash to exclude from termination
	token, err := helpers.GetJWTTokenFromContext(c)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "unable to identify current session")
	}

	currentTokenHash := s.authSvc.GetTokenHash(token)

	// Use the TerminateAllUserSessions method with token hash exclusion
	terminatedCount, err := s.authSvc.TerminateAllUserSessions(c.Request().Context(), userID, &currentTokenHash)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "failed to terminate sessions")
	}

	// Get remaining sessions count for the response
	remainingSessions, err := s.authSvc.GetUserSessions(c.Request().Context(), userID)
	if err != nil {
		// Log error but don't fail the response
		s.logger.Warnf("Failed to get remaining sessions count: %v", err)
	}

	return c.JSON(http.StatusOK, map[string]interface{}{
		"message":          "sessions terminated successfully",
		"terminated_count": terminatedCount,
		"remaining_count":  len(remainingSessions),
		"current_session":  "preserved",
	})
}

// Admin Session Management Handlers

// getUserSessions returns all active sessions for a specific user (admin only)
func (s *Server) getUserSessions(c echo.Context) error {
	// Parse user ID from URL parameter
	userIDStr := c.Param("id")
	userID, err := uuid.Parse(userIDStr)
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid user ID")
	}

	// Expect AccessControl middleware to have preloaded the target user
	if _, err := helpers.GetTargetUserFromContext(c); err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "target user not preloaded; ensure AccessControl middleware is applied")
	}

	// Get sessions for the target user
	sessions, err := s.authSvc.GetUserSessions(c.Request().Context(), userID)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "failed to get user sessions")
	}

	return c.JSON(http.StatusOK, map[string]interface{}{
		"sessions": sessions,
		"count":    len(sessions),
	})
}

// terminateUserSession terminates a specific session for a user (admin only)
func (s *Server) terminateUserSession(c echo.Context) error {
	// Parse user ID from URL parameter
	userIDStr := c.Param("id")
	userID, err := uuid.Parse(userIDStr)
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid user ID")
	}

	// Get token hash from URL parameter
	tokenHash := c.Param("token_hash")
	if tokenHash == "" {
		return echo.NewHTTPError(http.StatusBadRequest, "session ID is required")
	}

	// Expect AccessControl middleware to have preloaded the target user
	targetUser, err := helpers.GetTargetUserFromContext(c)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "target user not preloaded; ensure AccessControl middleware is applied")
	}

	// Get current token hash to exclude from termination
	token, err := helpers.GetJWTTokenFromContext(c)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "unable to identify current session")
	}

	currentTokenHash := s.authSvc.GetTokenHash(token)
	if currentTokenHash == tokenHash {
		// Prevent termination of the current session
		return echo.NewHTTPError(http.StatusForbidden, "cannot terminate current session")
	}

	// Terminate the session using the token hash
	err = s.authSvc.TerminateSession(c.Request().Context(), userID, tokenHash)
	if err != nil {
		if err.Error() == "session not found" {
			return echo.NewHTTPError(http.StatusNotFound, "session not found")
		}
		return echo.NewHTTPError(http.StatusInternalServerError, "failed to terminate session")
	}

	return c.JSON(http.StatusOK, map[string]interface{}{
		"message": "session terminated successfully",
		"user": map[string]interface{}{
			"id":    targetUser.ID,
			"email": targetUser.Email,
		},
		"token_hash": tokenHash,
	})
}

// terminateAllUserSessions terminates all sessions for a user (admin only)
func (s *Server) terminateAllUserSessions(c echo.Context) error {
	// Parse user ID from URL parameter
	userIDStr := c.Param("id")
	userID, err := uuid.Parse(userIDStr)
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid user ID")
	}

	// Expect AccessControl middleware to have preloaded the target user
	targetUser, err := helpers.GetTargetUserFromContext(c)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "target user not preloaded; ensure AccessControl middleware is applied")
	}

	// Get session count before termination for reporting
	sessionsBefore, err := s.authSvc.GetUserSessions(c.Request().Context(), userID)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "failed to get user sessions")
	}

	// Get current token hash to exclude from termination
	token, err := helpers.GetJWTTokenFromContext(c)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "unable to identify current session")
	}

	currentTokenHash := s.authSvc.GetTokenHash(token)

	// Terminate all sessions except the current one
	terminatedCount, err := s.authSvc.TerminateAllUserSessions(c.Request().Context(), userID, &currentTokenHash)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, "failed to terminate sessions")
	}

	return c.JSON(http.StatusOK, map[string]interface{}{
		"message": "all sessions terminated successfully",
		"user": map[string]interface{}{
			"id":    targetUser.ID,
			"email": targetUser.Email,
		},
		"terminated_count": terminatedCount,
		"total_sessions":   len(sessionsBefore),
	})
}
