package ports

import "context"

// HealthChecker abstracts a dependency health probe.
// Implementations should return error if unhealthy.
type HealthChecker interface {
	Name() string
	Check(ctx context.Context) error
}
