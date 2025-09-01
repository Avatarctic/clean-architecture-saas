package services_test

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"testing"
	"time"

	config "github.com/avatarctic/clean-architecture-saas/go/configs"
	impl "github.com/avatarctic/clean-architecture-saas/go/internal/application/services"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/auth"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/tenant"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	tmocks "github.com/avatarctic/clean-architecture-saas/go/test/mocks"
	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"github.com/stretchr/testify/require"
	"golang.org/x/crypto/bcrypt"
)

// Use centralized lightweight mocks from tmocks

// Test: Login success stores token claims and refresh token
func TestLogin_Success_StoresClaimsAndRefreshToken(t *testing.T) {
	// prepare
	passHash, _ := bcrypt.GenerateFromPassword([]byte("pass"), bcrypt.DefaultCost)
	uid := uuid.New()
	tid := uuid.New()
	usr := &user.User{ID: uid, Email: "a@b.com", PasswordHash: string(passHash), IsActive: true, TenantID: tid}

	var storedTokenHash string
	var storedClaims *auth.Claims
	var storedRefreshUser uuid.UUID
	var storedRefreshToken string

	ur := &tmocks.UserRepositoryMock{GetByEmailFn: func(ctx context.Context, email string) (*user.User, error) { return usr, nil }, UpdateFn: func(ctx context.Context, u *user.User) error { return nil }}
	tr := &tmocks.TokenRepositoryMock{
		StoreTokenClaimsFn: func(ctx context.Context, tokenHash string, claims *auth.Claims, expiresAt time.Time) error {
			storedTokenHash = tokenHash
			storedClaims = claims
			return nil
		},
		StoreRefreshTokenFn: func(ctx context.Context, userID uuid.UUID, token string, expiresAt time.Time) error {
			storedRefreshUser = userID
			storedRefreshToken = token
			return nil
		},
	}
	tenantR := &tmocks.TenantRepositoryMock{GetByIDFn: func(ctx context.Context, id uuid.UUID) (*tenant.Tenant, error) {
		return &tenant.Tenant{ID: id, Status: tenant.TenantStatusActive}, nil
	}}

	jwtCfg := &config.JWTConfig{Secret: "s", AccessTokenTTL: time.Minute, RefreshTokenTTL: time.Hour, SessionTimeout: time.Hour}
	svc := impl.NewAuthService(ur, tenantR, tr, jwtCfg, nil)

	tokens, err := svc.Login(context.Background(), &auth.LoginRequest{Email: "a@b.com", Password: "pass"})
	require.NoError(t, err)
	require.NotNil(t, tokens)
	require.NotEmpty(t, tokens.AccessToken)
	require.NotEmpty(t, tokens.RefreshToken)

	// validate that StoreTokenClaims was called with hash matching access token
	sum := sha256.Sum256([]byte(tokens.AccessToken))
	expectHash := hex.EncodeToString(sum[:])
	require.Equal(t, expectHash, storedTokenHash)
	require.Equal(t, uid, storedClaims.UserID)
	require.Equal(t, uid, storedRefreshUser)
	require.NotEmpty(t, storedRefreshToken)
}

// Test: RefreshToken exchanges stored refresh token for new tokens
func TestRefreshToken_Success_ReplacesOldToken(t *testing.T) {
	uid := uuid.New()

	// prepare stored refresh token
	oldRefresh := "oldrefresh"
	now := time.Now()
	stored := &ports.RefreshToken{ID: uuid.New(), UserID: uid, Token: oldRefresh, ExpiresAt: now.Add(time.Hour), CreatedAt: now}

	var deletedRefresh string
	var storedTokenClaimsCalled int

	tr := &tmocks.TokenRepositoryMock{
		GetRefreshTokenFn: func(ctx context.Context, token string) (*ports.RefreshToken, error) {
			if token == oldRefresh {
				return stored, nil
			}
			return nil, fmt.Errorf("not found")
		},
		DeleteRefreshTokenFn: func(ctx context.Context, token string) error { deletedRefresh = token; return nil },
		StoreTokenClaimsFn: func(ctx context.Context, tokenHash string, claims *auth.Claims, expiresAt time.Time) error {
			storedTokenClaimsCalled++
			return nil
		},
	}
	tenantR := &tmocks.TenantRepositoryMock{GetByIDFn: func(ctx context.Context, id uuid.UUID) (*tenant.Tenant, error) {
		return &tenant.Tenant{ID: id, Status: tenant.TenantStatusActive}, nil
	}}

	jwtCfg := &config.JWTConfig{Secret: "s", AccessTokenTTL: time.Minute, RefreshTokenTTL: time.Hour, SessionTimeout: time.Hour}
	// provide a user repo that can return the user by ID
	ur2 := &tmocks.UserRepositoryMock{GetByIDFn: func(ctx context.Context, id uuid.UUID) (*user.User, error) {
		return &user.User{ID: uid, TenantID: uuid.New(), Email: "x@x.com", PasswordHash: "", IsActive: true}, nil
	}}
	svc := impl.NewAuthService(ur2, tenantR, tr, jwtCfg, nil)

	tokens, err := svc.RefreshToken(context.Background(), oldRefresh)
	require.NoError(t, err)
	require.NotNil(t, tokens)
	require.NotEmpty(t, tokens.AccessToken)
	require.NotEmpty(t, tokens.RefreshToken)
	require.Equal(t, oldRefresh, deletedRefresh)
	require.Greater(t, storedTokenClaimsCalled, 0)
}

// Test: Logout blacklists token and deletes token claims
func TestLogout_BlacklistsTokenAndDeletesClaims(t *testing.T) {
	uid := uuid.New()
	tokenStr := "sometoken"

	var blacklisted bool
	var deletedHash string

	tr := &tmocks.TokenRepositoryMock{
		BlacklistTokenFn: func(ctx context.Context, userID uuid.UUID, token string, expiresAt time.Time) error {
			blacklisted = true
			return nil
		},
		DeleteTokenClaimsFn: func(ctx context.Context, tokenHash string) error { deletedHash = tokenHash; return nil },
	}
	jwtCfg := &config.JWTConfig{Secret: "s", AccessTokenTTL: time.Minute, RefreshTokenTTL: time.Hour, SessionTimeout: time.Hour}
	svc := impl.NewAuthService(&tmocks.UserRepositoryMock{}, &tmocks.TenantRepositoryMock{}, tr, jwtCfg, nil)

	err := svc.Logout(context.Background(), uid, tokenStr)
	require.NoError(t, err)
	require.True(t, blacklisted)
	// expected deletedHash to be hash of tokenStr
	sum := sha256.Sum256([]byte(tokenStr))
	expectHash := hex.EncodeToString(sum[:])
	require.Equal(t, expectHash, deletedHash)
}

// Test: ValidateToken returns error when token is blacklisted
func TestValidateToken_BlacklistedFails(t *testing.T) {
	uid := uuid.New()
	// create a simple token signed with same secret
	jwtCfg := &config.JWTConfig{Secret: "s", AccessTokenTTL: time.Minute, RefreshTokenTTL: time.Hour, SessionTimeout: time.Hour}
	svc := impl.NewAuthService(&tmocks.UserRepositoryMock{}, &tmocks.TenantRepositoryMock{}, &tmocks.TokenRepositoryMock{IsTokenBlacklistedFn: func(ctx context.Context, token string) (bool, error) { return true, nil }}, jwtCfg, nil)

	// manually craft a token with minimal claims
	claims := &auth.Claims{UserID: uid, RegisteredClaims: jwt.RegisteredClaims{Subject: uid.String(), ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Minute)), IssuedAt: jwt.NewNumericDate(time.Now())}}
	tkn := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenStr, err := tkn.SignedString([]byte(jwtCfg.Secret))
	require.NoError(t, err)

	_, err = svc.ValidateToken(context.Background(), tokenStr)
	require.Error(t, err)
}
