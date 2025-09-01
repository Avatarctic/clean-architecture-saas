package httpserver

import (
	"net/http"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/audit"
	"github.com/labstack/echo/v4"
)

func (s *Server) getAuditLogs(c echo.Context) error {
	var filter audit.AuditLogFilter
	if err := c.Bind(&filter); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid request body")
	}
	logs, total, err := s.auditSvc.GetAuditLogs(c.Request().Context(), &filter)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, err.Error())
	}
	return c.JSON(http.StatusOK, map[string]interface{}{"logs": logs, "total": total})
}
