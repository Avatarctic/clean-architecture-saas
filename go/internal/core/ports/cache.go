package ports

import (
	"context"
	"time"
)

// Cache defines a minimal key-value cache contract.
// Implementations should degrade gracefully (returning an error without crashing callers)
// so that application logic can fall back to the primary datastore.
type Cache interface {
	// Get returns the raw bytes for key. ok=false if not found.
	Get(ctx context.Context, key string) ([]byte, bool, error)
	// Set stores value for key with TTL (0 or negative means no expiration if supported).
	Set(ctx context.Context, key string, value []byte, ttl time.Duration) error
	// Delete removes the key; absence is not an error.
	Delete(ctx context.Context, key string) error
}
