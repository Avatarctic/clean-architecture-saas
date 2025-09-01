package services

import (
	"context"
	"fmt"
	"time"

	config "github.com/avatarctic/clean-architecture-saas/go/configs"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/auth"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/google/uuid"
	"github.com/sirupsen/logrus"
	"golang.org/x/crypto/bcrypt"
)

type AuthService struct {
	userRepo   ports.UserRepository
	tenantRepo ports.TenantRepository
	tokenRepo  ports.TokenRepository
	jwtConfig  *config.JWTConfig
	logger     *logrus.Logger
}

func NewAuthService(userRepo ports.UserRepository, tenantRepo ports.TenantRepository, tokenRepo ports.TokenRepository, jwtConfig *config.JWTConfig, logger *logrus.Logger) ports.AuthService {
	service := &AuthService{
		userRepo:   userRepo,
		tenantRepo: tenantRepo,
		tokenRepo:  tokenRepo,
		jwtConfig:  jwtConfig,
		logger:     logger,
	}

	if tokenRepo != nil {
		go service.startPeriodicTokenCleanup()
	}

	return service
}

func (s *AuthService) Login(ctx context.Context, req *auth.LoginRequest) (*auth.AuthTokens, error) {
	foundUser, err := s.userRepo.GetByEmail(ctx, req.Email)
	if err != nil {
		return nil, fmt.Errorf("user not found")
	}

	if err := bcrypt.CompareHashAndPassword([]byte(foundUser.PasswordHash), []byte(req.Password)); err != nil {
		return nil, fmt.Errorf("invalid credentials")
	}

	if !foundUser.IsActive {
		return nil, fmt.Errorf("user account is disabled")
	}

	tenant, err := s.tenantRepo.GetByID(ctx, foundUser.TenantID)
	if err != nil {
		return nil, fmt.Errorf("tenant not found")
	}

	if !tenant.CanAccess() {
		return nil, fmt.Errorf("tenant access is not available")
	}

	tokens, err := s.GenerateTokens(ctx, foundUser)
	if err != nil {
		return nil, err
	}

	now := time.Now()
	foundUser.LastLoginAt = &now
	if err := s.userRepo.Update(ctx, foundUser); err != nil {
		if s.logger != nil {
			s.logger.WithFields(logrus.Fields{"user_id": foundUser.ID}).WithError(err).Warn("failed to update user last login time")
		}
	}

	return tokens, nil
}

func (s *AuthService) RefreshToken(ctx context.Context, refreshToken string) (*auth.AuthTokens, error) {
	storedToken, err := s.tokenRepo.GetRefreshToken(ctx, refreshToken)
	if err != nil {
		return nil, fmt.Errorf("invalid refresh token")
	}

	if time.Now().After(storedToken.ExpiresAt) {
		if err := s.tokenRepo.DeleteRefreshToken(ctx, refreshToken); err != nil {
			if s.logger != nil {
				s.logger.WithFields(logrus.Fields{"refresh_token": refreshToken}).WithError(err).Warn("failed to delete expired refresh token")
			}
		}
		return nil, fmt.Errorf("refresh token expired")
	}

	foundUser, err := s.userRepo.GetByID(ctx, storedToken.UserID)
	if err != nil {
		return nil, fmt.Errorf("user not found")
	}

	tokens, err := s.GenerateTokens(ctx, foundUser)
	if err != nil {
		return nil, err
	}

	if err := s.tokenRepo.DeleteRefreshToken(ctx, refreshToken); err != nil {
		if s.logger != nil {
			s.logger.WithFields(logrus.Fields{"refresh_token": refreshToken}).WithError(err).Warn("failed to delete used refresh token")
		}
	}
	return tokens, nil
}

func (s *AuthService) Logout(ctx context.Context, userID uuid.UUID, token string) error {
	expiresAt := time.Now().Add(s.jwtConfig.AccessTokenTTL)
	if err := s.tokenRepo.BlacklistToken(ctx, userID, token, expiresAt); err != nil {
		return err
	}

	tokenHash := s.GetTokenHash(token)
	if err := s.tokenRepo.DeleteTokenClaims(ctx, tokenHash); err != nil {
		if s.logger != nil {
			s.logger.WithFields(logrus.Fields{"user_id": userID, "token_hash": tokenHash}).WithError(err).Warn("failed to delete token claims during logout")
		}
	}

	return nil
}

// startPeriodicTokenCleanup runs background cleanup loops; kept here to keep
// auth-related maintenance in the auth package.
func (s *AuthService) startPeriodicTokenCleanup() {
	ticker := time.NewTicker(6 * time.Hour)
	defer ticker.Stop()

	for range ticker.C {
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)

		if err := s.tokenRepo.DeleteExpiredRefreshTokens(ctx); err != nil {
			if s.logger != nil {
				s.logger.WithError(err).Error("failed to cleanup expired refresh tokens")
			}
		}

		if err := s.tokenRepo.DeleteExpiredBlacklistedTokens(ctx); err != nil {
			if s.logger != nil {
				s.logger.WithError(err).Error("failed to cleanup expired blacklisted tokens")
			}
		}

		if err := s.tokenRepo.DeleteExpiredTokenClaims(ctx); err != nil {
			if s.logger != nil {
				s.logger.WithError(err).Error("failed to cleanup expired token claims")
			}
		}

		cancel()
	}
}
