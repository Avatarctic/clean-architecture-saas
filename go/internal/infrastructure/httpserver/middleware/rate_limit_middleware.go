package middleware

import (
	"github.com/labstack/echo/v4"
	"github.com/sirupsen/logrus"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
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
			// rate limiting logic would call r.rateLimiter.Allow(...) etc.
			return next(c)
		}
	}
}
