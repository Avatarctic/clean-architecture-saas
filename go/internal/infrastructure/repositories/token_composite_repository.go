package repositories

import (
	"context"
	"crypto/sha256"
	"fmt"
	"time"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/auth"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/google/uuid"
	"github.com/sirupsen/logrus"
)

// TokenRepository combines database storage for refresh tokens
// and blacklisted tokens with Redis storage for token claims and
// session management
type TokenRepository struct {
	dbRepo    *TokenDBRepository    // Database repository
	redisRepo *TokenRedisRepository // Redis repository
}

func NewTokenRepository(dbRepo *TokenDBRepository, redisRepo *TokenRedisRepository, logger *logrus.Logger) ports.TokenRepository {
	// propagate logger to child repos if needed (they already have their own logger fields)
	return &TokenRepository{dbRepo: dbRepo, redisRepo: redisRepo}
}

// Refresh token and blacklisting methods - delegate to database repository
func (r *TokenRepository) StoreRefreshToken(ctx context.Context, userID uuid.UUID, token string, expiresAt time.Time) error {
	// compute token hash (sha256) and store hash in DB
	h := sha256.Sum256([]byte(token))
	tokenHash := fmt.Sprintf("%x", h[:])
	return r.dbRepo.storeRefreshToken(ctx, userID, tokenHash, expiresAt)
}

func (r *TokenRepository) GetRefreshToken(ctx context.Context, token string) (*ports.RefreshToken, error) {
	h := sha256.Sum256([]byte(token))
	tokenHash := fmt.Sprintf("%x", h[:])
	return r.dbRepo.getRefreshToken(ctx, tokenHash)
}

func (r *TokenRepository) DeleteRefreshToken(ctx context.Context, token string) error {
	h := sha256.Sum256([]byte(token))
	tokenHash := fmt.Sprintf("%x", h[:])
	return r.dbRepo.deleteRefreshToken(ctx, tokenHash)
}

func (r *TokenRepository) DeleteUserTokens(ctx context.Context, userID uuid.UUID) error {
	return r.dbRepo.deleteUserTokens(ctx, userID)
}

func (r *TokenRepository) IsTokenBlacklisted(ctx context.Context, token string) (bool, error) {
	h := sha256.Sum256([]byte(token))
	tokenHash := fmt.Sprintf("%x", h[:])
	return r.dbRepo.isTokenBlacklisted(ctx, tokenHash)
}

func (r *TokenRepository) BlacklistToken(ctx context.Context, userID uuid.UUID, token string, expiresAt time.Time) error {
	h := sha256.Sum256([]byte(token))
	tokenHash := fmt.Sprintf("%x", h[:])
	return r.dbRepo.blacklistToken(ctx, userID, tokenHash, expiresAt)
}

// Token claims methods - delegate to Redis repository
func (r *TokenRepository) StoreTokenClaims(ctx context.Context, tokenHash string, claims *auth.Claims, expiresAt time.Time) error {
	return r.redisRepo.storeTokenClaims(ctx, tokenHash, claims, expiresAt)
}

func (r *TokenRepository) GetTokenClaims(ctx context.Context, tokenHash string) (*auth.Claims, error) {
	return r.redisRepo.getTokenClaims(ctx, tokenHash)
}

func (r *TokenRepository) UpdateTokenActivity(ctx context.Context, tokenHash string, ipAddress, userAgent string) error {
	return r.redisRepo.updateTokenActivity(ctx, tokenHash, ipAddress, userAgent)
}

func (r *TokenRepository) DeleteTokenClaims(ctx context.Context, tokenHash string) error {
	return r.redisRepo.deleteTokenClaims(ctx, tokenHash)
}

func (r *TokenRepository) GetUserTokenClaims(ctx context.Context, userID uuid.UUID) ([]*auth.Claims, error) {
	return r.redisRepo.getUserTokenClaims(ctx, userID)
}

func (r *TokenRepository) DeleteUserTokenClaims(ctx context.Context, userID uuid.UUID, keepTokenHash *string) (int, error) {
	return r.redisRepo.deleteUserTokenClaims(ctx, userID, keepTokenHash)
}

// Cleanup methods - combine both database and redis cleanup
func (r *TokenRepository) DeleteExpiredRefreshTokens(ctx context.Context) error {
	return r.dbRepo.deleteExpiredRefreshTokens(ctx)
}

func (r *TokenRepository) DeleteExpiredBlacklistedTokens(ctx context.Context) error {
	return r.dbRepo.deleteExpiredBlacklistedTokens(ctx)
}

func (r *TokenRepository) DeleteExpiredTokenClaims(ctx context.Context) error {
	return r.redisRepo.deleteExpiredTokenClaims(ctx)
}
