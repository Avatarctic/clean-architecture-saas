package httpserver

import (
	"context"
	"net/http"
	"time"

	"github.com/labstack/echo/v4"
)

// Health check handler
func (s *Server) healthCheck(c echo.Context) error {
	ctx, cancel := context.WithTimeout(c.Request().Context(), 2*time.Second)
	defer cancel()

	deps := make(map[string]string)
	overall := "healthy"
	for _, hc := range s.healthCheckers {
		if hc == nil {
			continue
		}
		if err := hc.Check(ctx); err != nil {
			deps[hc.Name()] = "unhealthy"
			if overall == "healthy" {
				overall = "degraded"
			}
		} else {
			deps[hc.Name()] = "healthy"
		}
	}
	health := map[string]interface{}{
		"status":       overall,
		"timestamp":    time.Now().UTC().Format(time.RFC3339),
		"version":      "1.0.0",
		"service":      "clean-architecture-saas",
		"dependencies": deps,
	}
	code := http.StatusOK
	if overall != "healthy" {
		code = http.StatusServiceUnavailable
	}
	return c.JSON(code, health)
}
