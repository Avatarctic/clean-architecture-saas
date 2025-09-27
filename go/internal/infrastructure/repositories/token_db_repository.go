package repositories

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/db"
	"github.com/google/uuid"
	"github.com/sirupsen/logrus"
)

type TokenDBRepository struct {
	db     *db.Database
	logger *logrus.Logger
}

// NewTokenDBRepository creates a new token repository
func NewTokenDBRepository(database *db.Database, logger *logrus.Logger) *TokenDBRepository {
	return &TokenDBRepository{db: database, logger: logger}
}

// storeRefreshToken stores a refresh token in the database
func (r *TokenDBRepository) storeRefreshToken(ctx context.Context, userID uuid.UUID, tokenHash string, expiresAt time.Time) error {
	query := `
		INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at, created_at)
		VALUES ($1, $2, $3, $4, $5)`

	_, err := r.db.DB.ExecContext(ctx, query,
		uuid.New(), userID, tokenHash, expiresAt, time.Now())
	if err != nil {
		return fmt.Errorf("failed to store refresh token: %w", err)
	}

	return nil
}

// getRefreshToken retrieves a refresh token from the database
func (r *TokenDBRepository) getRefreshToken(ctx context.Context, tokenHash string) (*ports.RefreshToken, error) {
	var refreshToken ports.RefreshToken
	query := `
		SELECT id, user_id, token_hash, expires_at, created_at
		FROM refresh_tokens 
		WHERE token_hash = $1 AND expires_at > NOW()`

	err := r.db.DB.GetContext(ctx, &refreshToken, query, tokenHash)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("refresh token not found or expired")
		}
		return nil, fmt.Errorf("failed to get refresh token: %w", err)
	}

	return &refreshToken, nil
}

// deleteRefreshToken deletes a specific refresh token from the database
func (r *TokenDBRepository) deleteRefreshToken(ctx context.Context, tokenHash string) error {
	query := `DELETE FROM refresh_tokens WHERE token_hash = $1`

	_, err := r.db.DB.ExecContext(ctx, query, tokenHash)
	if err != nil {
		return fmt.Errorf("failed to delete refresh token: %w", err)
	}

	return nil
}

// deleteUserTokens deletes all tokens for a specific user (both refresh and blacklisted)
func (r *TokenDBRepository) deleteUserTokens(ctx context.Context, userID uuid.UUID) error {
	// Delete refresh tokens from database
	refreshQuery := `DELETE FROM refresh_tokens WHERE user_id = $1`
	if _, err := r.db.DB.ExecContext(ctx, refreshQuery, userID); err != nil {
		return fmt.Errorf("failed to delete user refresh tokens: %w", err)
	}

	// Delete blacklisted tokens for this user from database
	blacklistQuery := `DELETE FROM blacklisted_tokens WHERE user_id = $1`
	if _, err := r.db.DB.ExecContext(ctx, blacklistQuery, userID); err != nil {
		return fmt.Errorf("failed to delete user blacklisted tokens: %w", err)
	}

	return nil
}

// isTokenBlacklisted checks if a token is blacklisted in the database
func (r *TokenDBRepository) isTokenBlacklisted(ctx context.Context, tokenHash string) (bool, error) {
	var count int
	query := `
		SELECT COUNT(*)
		FROM blacklisted_tokens 
		WHERE token_hash = $1 AND expires_at > NOW()`

	err := r.db.DB.GetContext(ctx, &count, query, tokenHash)
	if err != nil {
		return false, fmt.Errorf("failed to check if token is blacklisted: %w", err)
	}

	return count > 0, nil
}

// blacklistToken adds a token to the blacklist in the database
func (r *TokenDBRepository) blacklistToken(ctx context.Context, userID uuid.UUID, tokenHash string, expiresAt time.Time) error {
	query := `
		INSERT INTO blacklisted_tokens (id, user_id, token_hash, expires_at, created_at, reason)
		VALUES ($1, $2, $3, $4, $5, $6)
		ON CONFLICT (token_hash) DO NOTHING`

	_, err := r.db.DB.ExecContext(ctx, query,
		uuid.New(), userID, tokenHash, expiresAt, time.Now(), "logout")
	if err != nil {
		return fmt.Errorf("failed to blacklist token: %w", err)
	}

	return nil
}

// deleteExpiredRefreshTokens removes expired refresh tokens from the database
func (r *TokenDBRepository) deleteExpiredRefreshTokens(ctx context.Context) error {
	query := `DELETE FROM refresh_tokens WHERE expires_at <= NOW()`

	result, err := r.db.DB.ExecContext(ctx, query)
	if err != nil {
		return fmt.Errorf("failed to delete expired refresh tokens: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	if rowsAffected > 0 {
		r.logger.WithFields(logrus.Fields{"rows": rowsAffected}).Info("cleaned up expired refresh tokens")
	}

	return nil
}

// deleteExpiredBlacklistedTokens removes expired blacklisted tokens from the database
func (r *TokenDBRepository) deleteExpiredBlacklistedTokens(ctx context.Context) error {
	query := `DELETE FROM blacklisted_tokens WHERE expires_at <= NOW()`

	result, err := r.db.DB.ExecContext(ctx, query)
	if err != nil {
		return fmt.Errorf("failed to delete expired blacklisted tokens: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	if rowsAffected > 0 {
		r.logger.WithFields(logrus.Fields{"rows": rowsAffected}).Info("cleaned up expired blacklisted tokens")
	}

	return nil
}
