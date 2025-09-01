package auth

import (
	"time"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
)

// LoginRequest represents the login request
type LoginRequest struct {
	Email    string `json:"email" validate:"required,email"`
	Password string `json:"password" validate:"required"`
}

// AuthTokens represents the authentication tokens
type AuthTokens struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	ExpiresIn    int64  `json:"expires_in"`
}

// Claims represents JWT claims with embedded session metadata
type Claims struct {
	UserID       uuid.UUID     `json:"user_id"`
	Email        string        `json:"email"`
	Role         user.UserRole `json:"role"`
	TenantID     uuid.UUID     `json:"tenant_id"`
	IPAddress    string        `json:"ip_address,omitempty"`
	UserAgent    string        `json:"user_agent,omitempty"`
	LastActivity time.Time     `json:"last_activity"`
	CreatedAt    time.Time     `json:"created_at"`

	jwt.RegisteredClaims
}

// TokenType represents the type of token
type TokenType string

const (
	TokenTypeAccess  TokenType = "access"
	TokenTypeRefresh TokenType = "refresh"
)
