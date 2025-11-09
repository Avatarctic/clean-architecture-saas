package httpserver

import (
	"net/http"
	"strings"

	"github.com/labstack/echo/v4"
	"github.com/labstack/echo/v4/middleware"
)

// securityHeadersMiddleware adds security headers to all responses
func securityHeadersMiddleware() echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			resp := c.Response()
			req := c.Request()

			// Prevent MIME type sniffing
			resp.Header().Set("X-Content-Type-Options", "nosniff")

			// Prevent clickjacking
			resp.Header().Set("X-Frame-Options", "DENY")

			// XSS protection (legacy browsers)
			resp.Header().Set("X-XSS-Protection", "1; mode=block")

			// Referrer policy
			resp.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")

			// Permissions policy
			resp.Header().Set("Permissions-Policy", "geolocation=(), microphone=(), camera=()")

			// Content Security Policy
			resp.Header().Set("Content-Security-Policy",
				"default-src 'self'; "+
					"script-src 'self' 'unsafe-inline'; "+
					"style-src 'self' 'unsafe-inline'; "+
					"img-src 'self' data: https:; "+
					"font-src 'self' data:; "+
					"connect-src 'self'; "+
					"frame-ancestors 'none'")

			// HSTS - only add with HTTPS
			if req.TLS != nil || req.Header.Get("X-Forwarded-Proto") == "https" {
				resp.Header().Set("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
			}

			return next(c)
		}
	}
}

// httpsRedirectMiddleware redirects HTTP to HTTPS in production
func httpsRedirectMiddleware(environment string) echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			// Only redirect in production
			if strings.ToLower(environment) != "production" {
				return next(c)
			}

			req := c.Request()

			// Skip if already HTTPS
			if req.TLS != nil {
				return next(c)
			}

			// Check proxy headers
			if req.Header.Get("X-Forwarded-Proto") == "https" {
				return next(c)
			}

			// Redirect to HTTPS
			url := "https://" + req.Host + req.RequestURI
			return c.Redirect(http.StatusTemporaryRedirect, url)
		}
	}
}

func (s *Server) setupMiddleware() {
	// Security headers should be first
	s.echo.Use(securityHeadersMiddleware())

	// HTTPS redirect in production
	s.echo.Use(httpsRedirectMiddleware(s.config.Environment))

	s.echo.Use(middleware.Logger())
	s.echo.Use(middleware.Recover())

	// CORS with explicit configuration
	s.echo.Use(middleware.CORSWithConfig(middleware.CORSConfig{
		AllowOrigins:     s.config.AllowedOrigins,
		AllowMethods:     []string{http.MethodGet, http.MethodPost, http.MethodPut, http.MethodPatch, http.MethodDelete, http.MethodOptions},
		AllowHeaders:     []string{"Origin", "Content-Type", "Accept", "Authorization"},
		AllowCredentials: true,
		MaxAge:           600, // 10 minutes
	}))

	s.echo.Use(middleware.RequestID())

	s.echo.Use(s.middleware.Metrics.CollectHTTPMetrics())

	s.echo.Use(s.middleware.Tenant.ResolveTenant())
	s.echo.Use(s.middleware.Logging.RequestLogging())
	s.echo.Use(s.middleware.RateLimit.Handler())
}
