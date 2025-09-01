package httpserver

import (
	"github.com/labstack/echo/v4/middleware"
)

func (s *Server) setupMiddleware() {
	s.echo.Use(middleware.Logger())
	s.echo.Use(middleware.Recover())
	s.echo.Use(middleware.CORS())
	s.echo.Use(middleware.RequestID())

	s.echo.Use(s.middleware.Metrics.CollectHTTPMetrics())

	s.echo.Use(s.middleware.Tenant.ResolveTenant())
	s.echo.Use(s.middleware.Logging.RequestLogging())
	s.echo.Use(s.middleware.RateLimit.Handler())
}
