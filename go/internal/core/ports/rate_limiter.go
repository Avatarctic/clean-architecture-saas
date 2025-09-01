package ports

import (
	"context"
	"time"

	"github.com/google/uuid"
)

// RateLimitRepository provides low-level atomic operations for rate limiting counters.
// It abstracts storage (e.g., Redis). Implementation should be concurrency-safe.
type RateLimitRepository interface {
	// IncrementWindow atomically increments the request counter for tenant in the current window
	// and ensures the key expires after ttl. Returns the updated count and the window start time.
	IncrementWindow(ctx context.Context, tenantID uuid.UUID, window time.Duration, keyPrefix string, ttl time.Duration) (count int, windowStart time.Time, err error)
}

// RateLimiterService defines a tenant-scoped rate limiting capability.
// Implementations encapsulate algorithm & storage (e.g., Redis) and MUST be safe for concurrent use.
type RateLimiterService interface {
	// Allow consumes one request unit for the tenant and reports whether it is permitted.
	// remaining: number of additional requests allowed in current window after this one (>=0)
	// limit: configured max requests per window
	// reset: time when the current window resets (Unix semantics for headers)
	Allow(ctx context.Context, tenantID uuid.UUID) (allowed bool, remaining int, limit int, reset time.Time, err error)
}
