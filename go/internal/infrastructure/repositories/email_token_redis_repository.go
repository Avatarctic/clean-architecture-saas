package repositories

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
	"github.com/sirupsen/logrus"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
)

const (
	// emailTokenPrefix prefixes Redis keys for email tokens.
	// It's a static prefix and not a credential; silence gosec G101 here.
	emailTokenPrefix = "app:email_token" //nolint:gosec
)

type EmailTokenRedisRepository struct {
	redisClient *redis.Client
	logger      *logrus.Logger
}

func NewEmailTokenRedisRepository(redisClient *redis.Client, logger *logrus.Logger) *EmailTokenRedisRepository {
	return &EmailTokenRedisRepository{redisClient: redisClient, logger: logger}
}

func (r *EmailTokenRedisRepository) keyByToken(token string) string {
	return fmt.Sprintf("%s:tok:%s", emailTokenPrefix, token)
}

func (r *EmailTokenRedisRepository) keyByID(id uuid.UUID) string {
	return fmt.Sprintf("%s:id:%s", emailTokenPrefix, id.String())
}

// Ensure EmailTokenRedisRepository implements ports.EmailTokenRepository
var _ ports.EmailTokenRepository = (*EmailTokenRedisRepository)(nil)

func (r *EmailTokenRedisRepository) Create(ctx context.Context, t *user.EmailToken) error {
	b, err := json.Marshal(t)
	if err != nil {
		return fmt.Errorf("failed to marshal email token: %w", err)
	}

	ttl := time.Until(t.ExpiresAt)
	if ttl <= 0 {
		return fmt.Errorf("email token already expired")
	}

	// store by token and by id for lookup/consume
	tokenKey := r.keyByToken(t.Token)
	idKey := r.keyByID(t.ID)

	// use pipeline to set both keys with same TTL
	pipe := r.redisClient.TxPipeline()
	pipe.Set(ctx, tokenKey, b, ttl)
	pipe.Set(ctx, idKey, b, ttl)
	_, err = pipe.Exec(ctx)
	if err != nil {
		return fmt.Errorf("failed to store email token in redis: %w", err)
	}

	return nil
}

func (r *EmailTokenRedisRepository) Get(ctx context.Context, token string) (*user.EmailToken, error) {
	tokenKey := r.keyByToken(token)

	b, err := r.redisClient.Get(ctx, tokenKey).Bytes()
	if err != nil {
		if err == redis.Nil {
			return nil, fmt.Errorf("email token not found or expired")
		}
		return nil, fmt.Errorf("failed to get email token from redis: %w", err)
	}

	var t user.EmailToken
	if err := json.Unmarshal(b, &t); err != nil {
		return nil, fmt.Errorf("failed to unmarshal email token: %w", err)
	}

	return &t, nil
}

func (r *EmailTokenRedisRepository) MarkAsUsed(ctx context.Context, id uuid.UUID) error {
	// consume by id: fetch and delete both keys (id and token)
	idKey := r.keyByID(id)

	// Get the value for id to find the token string
	b, err := r.redisClient.Get(ctx, idKey).Bytes()
	if err != nil {
		if err == redis.Nil {
			return fmt.Errorf("email token not found or already used")
		}
		return fmt.Errorf("failed to get email token by id: %w", err)
	}

	var t user.EmailToken
	if err := json.Unmarshal(b, &t); err != nil {
		return fmt.Errorf("failed to unmarshal email token: %w", err)
	}

	tokenKey := r.keyByToken(t.Token)

	// delete both keys atomically
	pipe := r.redisClient.TxPipeline()
	pipe.Del(ctx, idKey)
	pipe.Del(ctx, tokenKey)
	_, err = pipe.Exec(ctx)
	if err != nil {
		return fmt.Errorf("failed to delete email token keys: %w", err)
	}

	return nil
}
