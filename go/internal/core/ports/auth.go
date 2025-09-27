package ports

import (
	"context"
	"time"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/auth"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/google/uuid"
)

// AuthService defines the interface for authentication operations
type AuthService interface {
	Login(ctx context.Context, req *auth.LoginRequest) (*auth.AuthTokens, error)
	RefreshToken(ctx context.Context, refreshToken string) (*auth.AuthTokens, error)
	ValidateToken(ctx context.Context, token string) (*auth.Claims, error)
	Logout(ctx context.Context, userID uuid.UUID, token string) error
	GenerateTokens(ctx context.Context, user *user.User) (*auth.AuthTokens, error)

	// Enhanced session management through token claims
	StartSession(ctx context.Context, token string, ipAddress, userAgent string) (*auth.Claims, error)
	GetUserSessions(ctx context.Context, userID uuid.UUID) ([]*auth.Claims, error)
	TerminateSession(ctx context.Context, userID uuid.UUID, tokenHash string) error
	TerminateAllUserSessions(ctx context.Context, userID uuid.UUID, excludeTokenHash *string) (int, error)
	GetTokenHash(token string) string
}

// TokenRepository defines the interface for token storage operations
type TokenRepository interface {
	StoreRefreshToken(ctx context.Context, userID uuid.UUID, token string, expiresAt time.Time) error
	GetRefreshToken(ctx context.Context, token string) (*RefreshToken, error)
	DeleteRefreshToken(ctx context.Context, token string) error
	DeleteUserTokens(ctx context.Context, userID uuid.UUID) error
	IsTokenBlacklisted(ctx context.Context, token string) (bool, error)
	BlacklistToken(ctx context.Context, userID uuid.UUID, token string, expiresAt time.Time) error

	// Enhanced token operations with session metadata
	StoreTokenClaims(ctx context.Context, tokenHash string, claims *auth.Claims, expiresAt time.Time) error
	GetTokenClaims(ctx context.Context, tokenHash string) (*auth.Claims, error)
	UpdateTokenActivity(ctx context.Context, tokenHash string, ipAddress, userAgent string) error
	DeleteTokenClaims(ctx context.Context, tokenHash string) error
	GetUserTokenClaims(ctx context.Context, userID uuid.UUID) ([]*auth.Claims, error)
	DeleteUserTokenClaims(ctx context.Context, userID uuid.UUID, keepTokenHash *string) (int, error)

	// Cleanup methods for periodic maintenance
	DeleteExpiredRefreshTokens(ctx context.Context) error
	DeleteExpiredBlacklistedTokens(ctx context.Context) error
	DeleteExpiredTokenClaims(ctx context.Context) error
}

// RefreshToken represents a stored refresh token
type RefreshToken struct {
	ID        uuid.UUID `json:"id"`
	UserID    uuid.UUID `json:"user_id"`
	TokenHash string    `json:"token_hash"`
	ExpiresAt time.Time `json:"expires_at"`
	CreatedAt time.Time `json:"created_at"`
}
