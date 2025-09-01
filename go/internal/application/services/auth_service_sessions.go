package services

import (
	"context"
	"fmt"
	"time"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/auth"

	"github.com/google/uuid"
	"github.com/sirupsen/logrus"
)

func (s *AuthService) StartSession(ctx context.Context, token string, ipAddress, userAgent string) (*auth.Claims, error) {
	claims, err := s.ValidateToken(ctx, token)
	if err != nil {
		return nil, err
	}

	tokenHash := s.GetTokenHash(token)
	storedClaims, err := s.tokenRepo.GetTokenClaims(ctx, tokenHash)
	if err != nil {
		return nil, fmt.Errorf("session not found - token may be invalid or expired")
	}

	if storedClaims.UserID != claims.UserID {
		return nil, fmt.Errorf("session validation failed - token/user mismatch")
	}

	if time.Since(storedClaims.LastActivity) > s.jwtConfig.SessionTimeout {
		if err := s.tokenRepo.DeleteTokenClaims(ctx, tokenHash); err != nil {
			if s.logger != nil {
				s.logger.WithFields(logrus.Fields{"token_hash": tokenHash, "user_id": claims.UserID}).WithError(err).Warn("failed to delete token claims for timed-out session")
			}
		}
		expiresAt := time.Now().Add(s.jwtConfig.AccessTokenTTL)
		if err := s.tokenRepo.BlacklistToken(ctx, claims.UserID, token, expiresAt); err != nil {
			if s.logger != nil {
				s.logger.WithFields(logrus.Fields{"user_id": claims.UserID}).WithError(err).Warn("failed to blacklist token for timed-out session")
			}
		}
		return nil, fmt.Errorf("session timed out due to inactivity")
	}

	if err := s.tokenRepo.UpdateTokenActivity(ctx, tokenHash, ipAddress, userAgent); err != nil {
		if s.logger != nil {
			s.logger.WithFields(logrus.Fields{"token_hash": tokenHash, "user_id": claims.UserID}).WithError(err).Warn("failed to update token activity")
		}
	}

	storedClaims.LastActivity = time.Now()
	storedClaims.IPAddress = ipAddress
	storedClaims.UserAgent = userAgent

	return storedClaims, nil
}

func (s *AuthService) GetUserSessions(ctx context.Context, userID uuid.UUID) ([]*auth.Claims, error) {
	return s.tokenRepo.GetUserTokenClaims(ctx, userID)
}

func (s *AuthService) TerminateSession(ctx context.Context, userID uuid.UUID, tokenHash string) error {
	claims, err := s.tokenRepo.GetTokenClaims(ctx, tokenHash)
	if err != nil {
		return fmt.Errorf("session not found")
	}

	if claims.UserID != userID {
		return fmt.Errorf("session does not belong to user")
	}

	if err := s.tokenRepo.DeleteTokenClaims(ctx, tokenHash); err != nil {
		return fmt.Errorf("failed to terminate session: %w", err)
	}

	return nil
}

func (s *AuthService) TerminateAllUserSessions(ctx context.Context, userID uuid.UUID, excludeTokenHash *string) (int, error) {
	deleted, err := s.tokenRepo.DeleteUserTokenClaims(ctx, userID, excludeTokenHash)
	if err != nil {
		return 0, fmt.Errorf("failed to terminate sessions: %w", err)
	}
	return deleted, nil
}
