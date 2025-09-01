package services_test

import (
	"context"
	"fmt"
	"testing"
	"time"

	config "github.com/avatarctic/clean-architecture-saas/go/configs"
	impl "github.com/avatarctic/clean-architecture-saas/go/internal/application/services"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/auth"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/tenant"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/avatarctic/clean-architecture-saas/go/test/mocks"
	tmocks "github.com/avatarctic/clean-architecture-saas/go/test/mocks"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"github.com/stretchr/testify/require"
	"golang.org/x/crypto/bcrypt"
)

func TestStartSession_SessionTimeout(t *testing.T) {
	// Arrange
	tokenRepo := &mocks.TokenRepositoryMock{}
	now := time.Now()
	claims := &auth.Claims{UserID: uuid.New(), LastActivity: now.Add(-2 * time.Hour)}
	tokenHash := "thash"
	tokenRepo.GetTokenClaimsFn = func(ctx context.Context, th string) (*auth.Claims, error) {
		if th == tokenHash {
			return claims, nil
		}
		return nil, nil
	}
	tokenRepo.DeleteTokenClaimsFn = func(ctx context.Context, th string) error { return nil }
	tokenRepo.BlacklistTokenFn = func(ctx context.Context, userID uuid.UUID, token string, expiresAt time.Time) error { return nil }

	svc := impl.NewAuthService(nil, nil, tokenRepo, &config.JWTConfig{Secret: "s", AccessTokenTTL: time.Minute, SessionTimeout: time.Hour}, nil)

	// Act
	_, err := svc.StartSession(context.Background(), "token-string", "1.2.3.4", "ua")

	// Since ValidateToken will try to parse the token string with JWT using secret, we skip actual parsing by
	// directly calling the repo path: instead, ensure the path that times out is exercised by calling the internal logic
	// (simpler approach: call TerminateSession test below). Here we assert that when repo.GetTokenClaims returns a stale LastActivity,
	// the service returns an error indicating session timeout. Because ValidateToken will parse JWT first, we won't fully simulate here.
	if err == nil {
		t.Fatalf("expected error due to session timeout or invalid token")
	}
}

func TestTerminateSession_Behavior(t *testing.T) {
	userID := uuid.New()
	tokenHash := "tokenhash"
	tokenRepo := &mocks.TokenRepositoryMock{}
	tokenRepo.GetTokenClaimsFn = func(ctx context.Context, th string) (*auth.Claims, error) {
		if th == tokenHash {
			return &auth.Claims{UserID: userID}, nil
		}
		return nil, nil
	}
	deleted := false
	tokenRepo.DeleteTokenClaimsFn = func(ctx context.Context, th string) error {
		if th == tokenHash {
			deleted = true
			return nil
		}
		return nil
	}

	svc := impl.NewAuthService(nil, nil, tokenRepo, &config.JWTConfig{Secret: "s", AccessTokenTTL: time.Minute, SessionTimeout: time.Hour}, nil)
	err := svc.TerminateSession(context.Background(), userID, tokenHash)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !deleted {
		t.Fatalf("expected session to be deleted")
	}
}

func TestTerminateAllUserSessions_Behavior(t *testing.T) {
	userID := uuid.New()
	tokenRepo := &mocks.TokenRepositoryMock{}
	tokenRepo.DeleteUserTokenClaimsFn = func(ctx context.Context, uid uuid.UUID, keep *string) (int, error) {
		if uid == userID {
			return 3, nil
		}
		return 0, nil
	}

	svc := impl.NewAuthService(nil, nil, tokenRepo, &config.JWTConfig{}, nil)
	n, err := svc.TerminateAllUserSessions(context.Background(), userID, nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if n != 3 {
		t.Fatalf("expected 3 terminated, got %d", n)
	}
}

func TestLogin_InvalidPassword(t *testing.T) {
	passHash, _ := bcrypt.GenerateFromPassword([]byte("correct"), bcrypt.DefaultCost)
	userID := uuid.New()
	u := &user.User{ID: userID, Email: "a@b.com", PasswordHash: string(passHash), IsActive: true, TenantID: uuid.New()}
	ur := &tmocks.UserRepositoryMock{GetByEmailFn: func(ctx context.Context, email string) (*user.User, error) { return u, nil }}
	tr := &tmocks.TokenRepositoryMock{}
	tenantRepo := &tmocks.TenantRepositoryMock{GetByIDFn: func(ctx context.Context, id uuid.UUID) (*tenant.Tenant, error) {
		return &tenant.Tenant{ID: u.TenantID, Status: tenant.TenantStatusActive}, nil
	}}

	svc := impl.NewAuthService(ur, tenantRepo, tr, &config.JWTConfig{Secret: "s", AccessTokenTTL: time.Minute, RefreshTokenTTL: time.Hour, SessionTimeout: time.Hour}, nil)
	_, err := svc.Login(context.Background(), &auth.LoginRequest{Email: "a@b.com", Password: "wrong"})
	if err == nil {
		t.Fatalf("expected error for invalid credentials")
	}
}

func TestStartSession_SessionTimeout_Full(t *testing.T) {
	// Arrange: create service with token repo mock and JWT config
	tokenRepo := &mocks.TokenRepositoryMock{}
	jwtCfg := &config.JWTConfig{Secret: "s", AccessTokenTTL: time.Minute, SessionTimeout: time.Hour}
	svc := impl.NewAuthService(nil, nil, tokenRepo, jwtCfg, nil)

	// Create a token whose stored session last activity is older than SessionTimeout
	userID := uuid.New()
	now := time.Now()
	storedClaims := &auth.Claims{
		UserID:       userID,
		Email:        "a@b.com",
		Role:         user.UserRole("admin"),
		TenantID:     uuid.Nil,
		LastActivity: now.Add(-2 * time.Hour),
		CreatedAt:    now.Add(-3 * time.Hour),
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   userID.String(),
			ExpiresAt: jwt.NewNumericDate(now.Add(10 * time.Minute)),
			IssuedAt:  jwt.NewNumericDate(now),
		},
	}

	// Sign a JWT matching the stored claims
	tok := jwt.NewWithClaims(jwt.SigningMethodHS256, storedClaims)
	tokenString, err := tok.SignedString([]byte(jwtCfg.Secret))
	require.NoError(t, err)

	tokenHash := svc.GetTokenHash(tokenString)

	deleted := false
	blacklisted := false

	tokenRepo.GetTokenClaimsFn = func(ctx context.Context, th string) (*auth.Claims, error) {
		if th == tokenHash {
			return storedClaims, nil
		}
		return nil, fmt.Errorf("not found")
	}
	tokenRepo.DeleteTokenClaimsFn = func(ctx context.Context, th string) error {
		if th == tokenHash {
			deleted = true
			return nil
		}
		return nil
	}
	tokenRepo.BlacklistTokenFn = func(ctx context.Context, uid uuid.UUID, token string, expiresAt time.Time) error {
		if uid == userID {
			blacklisted = true
			return nil
		}
		return nil
	}

	// Act
	_, err = svc.StartSession(context.Background(), tokenString, "1.2.3.4", "ua")

	// Assert: session timed out and cleanup hooks were called
	require.Error(t, err)
	require.Contains(t, err.Error(), "session timed out")
	require.True(t, deleted, "expected DeleteTokenClaims to be called")
	require.True(t, blacklisted, "expected BlacklistToken to be called")
}

func TestStartSession_UpdateActivityError_DoesNotFail(t *testing.T) {
	tokenRepo := &mocks.TokenRepositoryMock{}
	jwtCfg := &config.JWTConfig{Secret: "s", AccessTokenTTL: time.Minute, SessionTimeout: time.Hour}
	svc := impl.NewAuthService(nil, nil, tokenRepo, jwtCfg, nil)

	userID := uuid.New()
	now := time.Now()
	storedClaims := &auth.Claims{
		UserID:       userID,
		Email:        "a@b.com",
		Role:         user.UserRole("admin"),
		TenantID:     uuid.Nil,
		LastActivity: now,
		CreatedAt:    now,
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   userID.String(),
			ExpiresAt: jwt.NewNumericDate(now.Add(10 * time.Minute)),
			IssuedAt:  jwt.NewNumericDate(now),
		},
	}

	tok := jwt.NewWithClaims(jwt.SigningMethodHS256, storedClaims)
	tokenString, err := tok.SignedString([]byte(jwtCfg.Secret))
	require.NoError(t, err)

	tokenHash := svc.GetTokenHash(tokenString)

	tokenRepo.GetTokenClaimsFn = func(ctx context.Context, th string) (*auth.Claims, error) {
		if th == tokenHash {
			return storedClaims, nil
		}
		return nil, fmt.Errorf("not found")
	}

	updateCalled := false
	tokenRepo.UpdateTokenActivityFn = func(ctx context.Context, th string, ipAddress, userAgent string) error {
		if th == tokenHash {
			updateCalled = true
			return fmt.Errorf("db error")
		}
		return nil
	}

	// Act
	ret, err := svc.StartSession(context.Background(), tokenString, "1.2.3.4", "ua")

	// Assert: update error should not fail validation
	require.NoError(t, err)
	require.Equal(t, userID, ret.UserID)
	require.Equal(t, "1.2.3.4", ret.IPAddress)
	require.Equal(t, "ua", ret.UserAgent)
	require.True(t, updateCalled)
}
