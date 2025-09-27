package middleware

import (
	"fmt"
	"net/http"

	"github.com/labstack/echo/v4"
	"github.com/sirupsen/logrus"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/httpserver/helpers"
)

type RateLimitMiddleware struct {
	rateLimiter ports.RateLimiterService
	logger      *logrus.Logger
}

func NewRateLimitMiddleware(rateLimiter ports.RateLimiterService, logger *logrus.Logger) *RateLimitMiddleware {
	return &RateLimitMiddleware{rateLimiter: rateLimiter, logger: logger}
}

func (r *RateLimitMiddleware) Handler() echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			// Resolve tenant id from context; if not present, treat as unauthenticated and skip limiter
			tenantID, err := helpers.GetTenantIDFromContext(c)
			if err != nil {
				// No tenant context — proceed without limiting (could be changed to global limiter)
				return next(c)
			}

			allowed, remaining, limit, reset, rlErr := r.rateLimiter.Allow(c.Request().Context(), tenantID)
			// Set standard rate limit headers when available
			c.Response().Header().Set("X-RateLimit-Limit", fmt.Sprintf("%d", limit))
			c.Response().Header().Set("X-RateLimit-Remaining", fmt.Sprintf("%d", remaining))
			c.Response().Header().Set("X-RateLimit-Reset", fmt.Sprintf("%d", reset.Unix()))

			if rlErr != nil {
				if r.logger != nil {
					r.logger.WithError(rlErr).WithField("tenant_id", tenantID).Warn("rate limiter error; allowing request (fail-open)")
				}
				return next(c)
			}

			if !allowed {
				return echo.NewHTTPError(http.StatusTooManyRequests, "rate limit exceeded")
			}
			return next(c)
		}
	}
}
