package httpserver

import (
	"context"
	"fmt"
	"net/http"

	"github.com/labstack/echo/v4"
)

func (s *Server) Start() error {
	s.LogMetricsInitialization()

	addr := fmt.Sprintf("%s:%s", s.config.Host, s.config.Port)

	server := &http.Server{
		Addr:         addr,
		ReadTimeout:  s.config.ReadTimeout,
		WriteTimeout: s.config.WriteTimeout,
		IdleTimeout:  s.config.IdleTimeout,
	}

	if s.config.TLSCertFile != "" && s.config.TLSKeyFile != "" {
		s.logger.Infof("Starting HTTPS server on %s", addr)
		return s.echo.StartTLS(addr, s.config.TLSCertFile, s.config.TLSKeyFile)
	} else {
		s.logger.Infof("Starting HTTP server on %s", addr)
		s.logger.Warn("Running in HTTP mode - TLS certificates not configured")
		return s.echo.StartServer(server)
	}
}

func (s *Server) Shutdown(ctx context.Context) error {
	return s.echo.Shutdown(ctx)
}

func (s *Server) Echo() *echo.Echo {
	return s.echo
}
