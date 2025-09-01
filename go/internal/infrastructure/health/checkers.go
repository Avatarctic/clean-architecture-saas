package health

import (
	"context"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	infraDB "github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/db"
	"github.com/go-redis/redis/v8"
)

// dbHealthChecker wraps the database for health checks.
type dbHealthChecker struct{ db *infraDB.Database }

func (d *dbHealthChecker) Name() string                    { return "database" }
func (d *dbHealthChecker) Check(ctx context.Context) error { return d.db.DB.PingContext(ctx) }

// redisHealthChecker wraps the redis client for health checks.
type redisHealthChecker struct{ client *redis.Client }

func (r *redisHealthChecker) Name() string                    { return "redis" }
func (r *redisHealthChecker) Check(ctx context.Context) error { return r.client.Ping(ctx).Err() }

// NewDBHealthChecker creates a health checker for the database.
func NewDBHealthChecker(db *infraDB.Database) ports.HealthChecker { return &dbHealthChecker{db: db} }

// NewRedisHealthChecker creates a health checker for Redis.
func NewRedisHealthChecker(client *redis.Client) ports.HealthChecker {
	return &redisHealthChecker{client: client}
}
