package redis

import (
	"context"
	"time"

	"github.com/go-redis/redis/v8"
)

// RedisCache implements ports.Cache using a Redis client.
type RedisCache struct {
	r redis.Cmdable
	// optional key prefix to namespace entries
	prefix string
}

// NewRedisCache creates a new Redis-backed cache.
func NewRedisCache(r redis.Cmdable, prefix string) *RedisCache {
	return &RedisCache{r: r, prefix: prefix}
}

func (c *RedisCache) namespaced(key string) string {
	if c.prefix == "" {
		return key
	}
	return c.prefix + ":" + key
}

// Get implements Cache.Get.
func (c *RedisCache) Get(ctx context.Context, key string) ([]byte, bool, error) {
	ns := c.namespaced(key)
	val, err := c.r.Get(ctx, ns).Bytes()
	if err == redis.Nil {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, err
	}
	return val, true, nil
}

// Set implements Cache.Set.
func (c *RedisCache) Set(ctx context.Context, key string, value []byte, ttl time.Duration) error {
	ns := c.namespaced(key)
	return c.r.Set(ctx, ns, value, ttl).Err()
}

// Delete implements Cache.Delete.
func (c *RedisCache) Delete(ctx context.Context, key string) error {
	ns := c.namespaced(key)
	return c.r.Del(ctx, ns).Err()
}
