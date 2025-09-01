package repositories

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/auth"
	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
	"github.com/sirupsen/logrus"
)

const (
	tokenPrefix = "saas_tokens"
)

// TokenRedisRepository provides Redis-based storage for token claims and session management
type TokenRedisRepository struct {
	client redis.Cmdable
	logger *logrus.Logger
}

// NewTokenRedisRepository creates a new Redis token repository
func NewTokenRedisRepository(client redis.Cmdable, logger *logrus.Logger) *TokenRedisRepository {
	return &TokenRedisRepository{client: client, logger: logger}
}

// StoreTokenClaims stores token claims in Redis with TTL
func (r *TokenRedisRepository) storeTokenClaims(ctx context.Context, tokenHash string, claims *auth.Claims, expiresAt time.Time) error {
	key := fmt.Sprintf("%s:token:%s", tokenPrefix, tokenHash)
	ttl := time.Until(expiresAt)
	if ttl <= 0 {
		return fmt.Errorf("token already expired")
	}
	data, err := json.Marshal(claims)
	if err != nil {
		return fmt.Errorf("failed to marshal claims: %w", err)
	}
	if err = r.client.Set(ctx, key, data, ttl).Err(); err != nil {
		return fmt.Errorf("failed to store token claims in Redis: %w", err)
	}
	userKey := fmt.Sprintf("%s:user:%s:tokens", tokenPrefix, claims.UserID)
	if err = r.client.SAdd(ctx, userKey, tokenHash).Err(); err != nil {
		return fmt.Errorf("failed to add token to user mapping: %w", err)
	}
	_ = r.client.Expire(ctx, userKey, ttl+time.Hour)
	return nil
}

// GetTokenClaims retrieves token claims from Redis
func (r *TokenRedisRepository) getTokenClaims(ctx context.Context, tokenHash string) (*auth.Claims, error) {
	key := fmt.Sprintf("%s:token:%s", tokenPrefix, tokenHash)
	data, err := r.client.Get(ctx, key).Result()
	if err != nil {
		if err == redis.Nil {
			return nil, fmt.Errorf("token not found or expired")
		}
		return nil, fmt.Errorf("failed to get token claims from Redis: %w", err)
	}
	var claims auth.Claims
	if err = json.Unmarshal([]byte(data), &claims); err != nil {
		return nil, fmt.Errorf("failed to unmarshal token claims: %w", err)
	}
	return &claims, nil
}

// UpdateTokenActivity updates the last activity timestamp and metadata for a token
func (r *TokenRedisRepository) updateTokenActivity(ctx context.Context, tokenHash, ipAddress, userAgent string) error {
	key := fmt.Sprintf("%s:token:%s", tokenPrefix, tokenHash)
	claims, err := r.getTokenClaims(ctx, tokenHash)
	if err != nil {
		return err
	}
	claims.LastActivity = time.Now()
	if ipAddress != "" {
		claims.IPAddress = ipAddress
	}
	if userAgent != "" {
		claims.UserAgent = userAgent
	}
	ttl, err := r.client.TTL(ctx, key).Result()
	if err != nil {
		return fmt.Errorf("failed to get token TTL: %w", err)
	}
	data, err := json.Marshal(claims)
	if err != nil {
		return fmt.Errorf("failed to marshal updated claims: %w", err)
	}
	if err = r.client.Set(ctx, key, data, ttl).Err(); err != nil {
		return fmt.Errorf("failed to update token claims: %w", err)
	}
	return nil
}

// DeleteTokenClaims removes token claims from Redis
func (r *TokenRedisRepository) deleteTokenClaims(ctx context.Context, tokenHash string) error {
	key := fmt.Sprintf("%s:token:%s", tokenPrefix, tokenHash)
	claims, err := r.getTokenClaims(ctx, tokenHash)
	if err != nil {
		if err.Error() == "token not found or expired" {
			return nil
		}
		return err
	}
	if err = r.client.Del(ctx, key).Err(); err != nil {
		return fmt.Errorf("failed to delete token claims: %w", err)
	}
	userKey := fmt.Sprintf("%s:user:%s:tokens", tokenPrefix, claims.UserID)
	if err = r.client.SRem(ctx, userKey, tokenHash).Err(); err != nil {
		r.logger.WithFields(logrus.Fields{"user_key": userKey, "token_hash": tokenHash}).WithError(err).Warn("failed to remove token from user mapping")
	}
	return nil
}

// GetUserTokenClaims returns all active token claims for a user
func (r *TokenRedisRepository) getUserTokenClaims(ctx context.Context, userID uuid.UUID) ([]*auth.Claims, error) {
	userKey := fmt.Sprintf("%s:user:%s:tokens", tokenPrefix, userID)
	tokenHashes, err := r.client.SMembers(ctx, userKey).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get user token hashes: %w", err)
	}
	claimsList := make([]*auth.Claims, 0, len(tokenHashes))
	for _, tokenHash := range tokenHashes {
		claims, err := r.getTokenClaims(ctx, tokenHash)
		if err != nil {
			r.client.SRem(ctx, userKey, tokenHash)
			continue
		}
		claimsList = append(claimsList, claims)
	}
	return claimsList, nil
}

// deleteUserTokenClaims removes all user sessions except the provided token hash
func (r *TokenRedisRepository) deleteUserTokenClaims(ctx context.Context, userID uuid.UUID, keepTokenHash *string) (int, error) {
	userKey := fmt.Sprintf("%s:user:%s:tokens", tokenPrefix, userID)
	tokenHashes, err := r.client.SMembers(ctx, userKey).Result()
	if err != nil {
		return 0, fmt.Errorf("failed to get user token hashes: %w", err)
	}
	deleted := 0
	for _, th := range tokenHashes {
		if keepTokenHash != nil && th == *keepTokenHash {
			continue
		}
		_ = r.client.Del(ctx, fmt.Sprintf("%s:token:%s", tokenPrefix, th))
		if err := r.client.SRem(ctx, userKey, th).Err(); err != nil {
			r.logger.WithFields(logrus.Fields{"user_key": userKey, "token_hash": th}).WithError(err).Warn("failed removing token hash from user mapping")
			continue
		}
		deleted++
	}
	if keepTokenHash != nil {
		if err = r.client.Del(ctx, userKey).Err(); err != nil {
			return deleted, fmt.Errorf("failed to delete user tokens set: %w", err)
		}
	}
	return deleted, nil
}

// DeleteExpiredTokenClaims cleans up expired tokens references
func (r *TokenRedisRepository) deleteExpiredTokenClaims(ctx context.Context) error {
	pattern := fmt.Sprintf("%s:user:*:tokens", tokenPrefix)
	var cursor uint64 = 0
	for {
		keys, next, err := r.client.Scan(ctx, cursor, pattern, 200).Result()
		if err != nil {
			return err
		}
		for _, userKey := range keys {
			r.cleanupUserTokens(ctx, userKey)
		}
		cursor = next
		if cursor == 0 { // done scanning all keys
			break
		}
	}
	return nil
}

// cleanupUserTokens scans a user's token set and removes token hashes whose token
// entries no longer exist. This mirrors the original behavior: on SScan errors we
// skip the user set, and on Exists errors we attempt to remove the token hash.
func (r *TokenRedisRepository) cleanupUserTokens(ctx context.Context, userKey string) {
	var sc uint64 = 0
	for {
		members, nextSc, err := r.client.SScan(ctx, userKey, sc, "*", 200).Result()
		if err != nil {
			if r.logger != nil {
				r.logger.WithFields(logrus.Fields{"user_key": userKey}).WithError(err).Warn("skipping user set due to scan error")
			}
			return // skip this user set on error
		}
		r.processUserTokenPage(ctx, userKey, members)
		sc = nextSc
		if sc == 0 {
			break
		}
	}
}

// processUserTokenPage processes a batch of token hashes for a user and removes
// any tokens whose token key no longer exists in Redis.
func (r *TokenRedisRepository) processUserTokenPage(ctx context.Context, userKey string, members []string) {
	for _, tokenHash := range members {
		tokenKey := fmt.Sprintf("%s:token:%s", tokenPrefix, tokenHash)
		exists, err := r.client.Exists(ctx, tokenKey).Result()
		if err != nil {
			if r.logger != nil {
				r.logger.WithFields(logrus.Fields{"user_key": userKey, "token_hash": tokenHash}).WithError(err).Warn("exists check failed for token key")
			}
			continue
		}
		if exists == 0 {
			if err := r.client.SRem(ctx, userKey, tokenHash).Err(); err != nil {
				if r.logger != nil {
					r.logger.WithFields(logrus.Fields{"user_key": userKey, "token_hash": tokenHash}).WithError(err).Warn("failed to remove token hash from user mapping")
				}
			}
		}
	}
}
