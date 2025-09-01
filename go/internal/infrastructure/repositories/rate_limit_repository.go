package repositories

import (
	"context"
	"fmt"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
)

// RateLimitRedisRepository implements rate limiting counter storage with Redis.
type RateLimitRedisRepository struct {
	r redis.Cmdable
}

func NewRateLimitRedisRepository(r redis.Cmdable) *RateLimitRedisRepository {
	return &RateLimitRedisRepository{r: r}
}

// IncrementWindow increments a per-tenant counter for a fixed window.
func (repo *RateLimitRedisRepository) IncrementWindow(ctx context.Context, tenantID uuid.UUID, window time.Duration, keyPrefix string, ttl time.Duration) (int, time.Time, error) {
	now := time.Now()
	windowStart := now.Truncate(window)
	key := fmt.Sprintf("%s:%s:%d", keyPrefix, tenantID.String(), windowStart.Unix())
	pipe := repo.r.TxPipeline()
	incr := pipe.Incr(ctx, key)
	pipe.Expire(ctx, key, ttl)
	if _, err := pipe.Exec(ctx); err != nil {
		return 0, windowStart, err
	}
	return int(incr.Val()), windowStart, nil
}
