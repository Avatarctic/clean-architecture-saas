package services

import (
	"context"
	"crypto/sha256"
	"fmt"
	"time"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/auth"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/golang-jwt/jwt/v5"
)

func (s *AuthService) GetTokenHash(token string) string {
	hasher := sha256.New()
	hasher.Write([]byte(token))
	return fmt.Sprintf("%x", hasher.Sum(nil))
}

func (s *AuthService) GenerateTokens(ctx context.Context, u *user.User) (*auth.AuthTokens, error) {
	now := time.Now()

	claims := &auth.Claims{
		UserID:       u.ID,
		Email:        u.Email,
		Role:         u.Role,
		TenantID:     u.TenantID,
		IPAddress:    "",
		UserAgent:    "",
		LastActivity: now,
		CreatedAt:    now,
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   u.ID.String(),
			ExpiresAt: jwt.NewNumericDate(now.Add(s.jwtConfig.AccessTokenTTL)),
			IssuedAt:  jwt.NewNumericDate(now),
		},
	}

	accessToken := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	accessTokenString, err := accessToken.SignedString([]byte(s.jwtConfig.Secret))
	if err != nil {
		return nil, fmt.Errorf("failed to generate access token: %w", err)
	}

	tokenHash := s.GetTokenHash(accessTokenString)
	tokenExpiry := now.Add(s.jwtConfig.SessionTimeout)
	if err := s.tokenRepo.StoreTokenClaims(ctx, tokenHash, claims, tokenExpiry); err != nil {
		return nil, fmt.Errorf("failed to store token claims: %w", err)
	}

	refreshToken := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.RegisteredClaims{
		Subject:   u.ID.String(),
		ExpiresAt: jwt.NewNumericDate(now.Add(s.jwtConfig.RefreshTokenTTL)),
		IssuedAt:  jwt.NewNumericDate(now),
	})

	refreshTokenString, err := refreshToken.SignedString([]byte(s.jwtConfig.Secret))
	if err != nil {
		return nil, fmt.Errorf("failed to generate refresh token: %w", err)
	}

	err = s.tokenRepo.StoreRefreshToken(ctx, u.ID, refreshTokenString, now.Add(s.jwtConfig.RefreshTokenTTL))
	if err != nil {
		return nil, fmt.Errorf("failed to store refresh token: %w", err)
	}

	return &auth.AuthTokens{
		AccessToken:  accessTokenString,
		RefreshToken: refreshTokenString,
		ExpiresIn:    int64(s.jwtConfig.AccessTokenTTL.Seconds()),
	}, nil
}

func (s *AuthService) ValidateToken(ctx context.Context, tokenString string) (*auth.Claims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &auth.Claims{}, func(token *jwt.Token) (interface{}, error) {
		// Ensure the token's signing method is HMAC (prevent alg confusion)
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return []byte(s.jwtConfig.Secret), nil
	})

	if err != nil {
		return nil, err
	}

	if !token.Valid {
		return nil, fmt.Errorf("invalid token")
	}

	claims, ok := token.Claims.(*auth.Claims)
	if !ok {
		return nil, fmt.Errorf("invalid token claims")
	}

	isBlacklisted, err := s.tokenRepo.IsTokenBlacklisted(ctx, tokenString)
	if err != nil {
		return nil, err
	}

	if isBlacklisted {
		return nil, fmt.Errorf("token is blacklisted")
	}

	return claims, nil
}
