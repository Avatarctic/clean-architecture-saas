package httpserver_test

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/auth"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/permission"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/tenant"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	saas_http "github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/httpserver"
	"github.com/avatarctic/clean-architecture-saas/go/test/mocks"
	"github.com/google/uuid"
	"github.com/labstack/echo/v4"
	"github.com/sirupsen/logrus"
	"github.com/stretchr/testify/require"
)

// testValidator is a no-op validator used in tests to satisfy echo.Validator
type testValidator struct{}

func (v *testValidator) Validate(i interface{}) error { return nil }

func TestAuthEndpoints_ServerIntegration_MockServices(t *testing.T) {
	// Arrange: create mocks
	authMock := &mocks.AuthServiceMock{}
	authMock.LoginFn = func(ctx context.Context, req *auth.LoginRequest) (*auth.AuthTokens, error) {
		return &auth.AuthTokens{AccessToken: "access-x", RefreshToken: "refresh-x", ExpiresIn: 3600}, nil
	}
	authMock.RefreshFn = func(ctx context.Context, refreshToken string) (*auth.AuthTokens, error) {
		if refreshToken != "refresh-x" {
			return nil, ctx.Err()
		}
		return &auth.AuthTokens{AccessToken: "access-y", RefreshToken: "refresh-y", ExpiresIn: 3600}, nil
	}
	logoutCalled := false
	authMock.LogoutFn = func(ctx context.Context, userID uuid.UUID, token string) error {
		logoutCalled = true
		return nil
	}
	authMock.GetTokenHashFn = func(token string) string { return "hash-" + token }

	userMock := &mocks.UserServiceMock{}
	userMock.GetUserFn = func(ctx context.Context, id uuid.UUID) (*user.User, error) {
		return &user.User{ID: id, Email: "u@e.com", AuditEnabled: true}, nil
	}

	permMock := &mocks.PermissionServiceMock{}
	permMock.GetRolePermissionsFn = func(ctx context.Context, role user.UserRole) ([]permission.Permission, error) { return nil, nil }

	tenantMock := &mocks.TenantRepositoryMock{}
	featureMock := &mocks.TenantRepositoryMock{}
	auditMock := &mocks.TenantRepositoryMock{}
	accessControlMock := &mocks.TenantRepositoryMock{}
	rateLimiterMock := &mocks.TenantRepositoryMock{}

	deps := saas_http.ServerDeps{
		UserService:          userMock,
		AuthService:          authMock,
		TenantService:        tenantMock,
		FeatureFlagService:   featureMock,
		AuditService:         auditMock,
		PermissionService:    permMock,
		AccessControlService: accessControlMock,
		RateLimiterService:   rateLimiterMock,
		HealthCheckers:       nil,
	}
	srv := saas_http.NewServer(&saas_http.ServerConfig{Host: "127.0.0.1", Port: "0", ReadTimeout: time.Second, WriteTimeout: time.Second, IdleTimeout: time.Second}, "jwt-secret", logrus.New(), deps)

	srv.Echo().Validator = &testValidator{}

	ts := httptest.NewServer(srv.Echo())
	defer ts.Close()

	doJSON := func(method, path string, body any, token string) (*http.Response, []byte, error) {
		var b []byte
		if body != nil {
			var err error
			b, err = json.Marshal(body)
			if err != nil {
				return nil, nil, err
			}
		}
		req, _ := http.NewRequest(method, ts.URL+path, bytes.NewReader(b))
		if body != nil {
			req.Header.Set(echo.HeaderContentType, echo.MIMEApplicationJSON)
		}
		if token != "" {
			req.Header.Set("Authorization", "Bearer "+token)
		}
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			return nil, nil, err
		}
		defer resp.Body.Close()
		respBody := make([]byte, 0)
		if resp.ContentLength > 0 {
			buf := make([]byte, resp.ContentLength)
			_, _ = resp.Body.Read(buf)
			respBody = buf
		}
		return resp, respBody, nil
	}

	loginReq := map[string]string{"email": "x@x.com", "password": "pass"}
	resp, body, err := doJSON(http.MethodPost, "/api/v1/auth/login", loginReq, "")
	require.NoError(t, err)
	require.Equal(t, http.StatusOK, resp.StatusCode)
	var tokens auth.AuthTokens
	_ = json.Unmarshal(body, &tokens)
	require.Equal(t, "access-x", tokens.AccessToken)

	refreshReq := map[string]string{"refresh_token": "refresh-x"}
	resp, body, err = doJSON(http.MethodPost, "/api/v1/auth/refresh", refreshReq, "")
	require.NoError(t, err)
	require.Equal(t, http.StatusOK, resp.StatusCode)
	_ = json.Unmarshal(body, &tokens)
	require.Equal(t, "access-y", tokens.AccessToken)

	authMock.StartSessionFn = func(ctx context.Context, token string, ip, ua string) (*auth.Claims, error) {
		return &auth.Claims{UserID: uuid.New(), Role: user.UserRole("user"), Email: "u@e.com", TenantID: uuid.New()}, nil
	}
	resp, _, err = doJSON(http.MethodPost, "/api/v1/auth/logout", nil, "some-jwt")
	require.NoError(t, err)
	require.Equal(t, http.StatusOK, resp.StatusCode)
	require.True(t, logoutCalled)
}

func TestAuthEndpoints_RefreshExpiredAndInvalidBodies_TenantMismatch(t *testing.T) {
	authMock := &mocks.AuthServiceMock{}
	authMock.RefreshFn = func(ctx context.Context, refreshToken string) (*auth.AuthTokens, error) {
		return nil, fmt.Errorf("expired")
	}
	jwtUserID := uuid.New()
	authMock.StartSessionFn = func(ctx context.Context, token string, ip, ua string) (*auth.Claims, error) {
		return &auth.Claims{UserID: jwtUserID, Role: user.UserRole("user"), Email: "u@e.com", TenantID: uuid.New()}, nil
	}
	tenantID := uuid.New()
	tenantMock := &mocks.TenantRepositoryMock{GetBySlugFn: func(ctx context.Context, slug string) (*tenant.Tenant, error) {
		return &tenant.Tenant{ID: tenantID, Slug: slug, Status: "active"}, nil
	}}
	userMock := &mocks.UserServiceMock{}
	permMock := &mocks.PermissionServiceMock{}
	featureMock := &mocks.TenantRepositoryMock{}
	auditMock := &mocks.TenantRepositoryMock{}
	accessControlMock := &mocks.TenantRepositoryMock{}
	rateLimiterMock := &mocks.TenantRepositoryMock{}
	deps := saas_http.ServerDeps{
		UserService:          userMock,
		AuthService:          authMock,
		TenantService:        tenantMock,
		FeatureFlagService:   featureMock,
		AuditService:         auditMock,
		PermissionService:    permMock,
		AccessControlService: accessControlMock,
		RateLimiterService:   rateLimiterMock,
		HealthCheckers:       nil,
	}
	srv := saas_http.NewServer(&saas_http.ServerConfig{Host: "127.0.0.1", Port: "0"}, "jwt-secret", logrus.New(), deps)
	ts := httptest.NewServer(srv.Echo())
	defer ts.Close()
	doRaw := func(method, path, body, token, host string) (*http.Response, []byte, error) {
		req, _ := http.NewRequest(method, ts.URL+path, bytes.NewReader([]byte(body)))
		if body != "" {
			req.Header.Set(echo.HeaderContentType, echo.MIMEApplicationJSON)
		}
		if token != "" {
			req.Header.Set("Authorization", "Bearer "+token)
		}
		if host != "" {
			req.Host = host
		}
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			return nil, nil, err
		}
		defer resp.Body.Close()
		b := make([]byte, 0)
		if resp.ContentLength > 0 {
			buf := make([]byte, resp.ContentLength)
			_, _ = resp.Body.Read(buf)
			b = buf
		}
		return resp, b, nil
	}
	refreshReq := map[string]string{"refresh_token": "expired-token"}
	rb, _ := json.Marshal(refreshReq)
	resp, _, err := doRaw(http.MethodPost, "/api/v1/auth/refresh", string(rb), "", "")
	require.NoError(t, err)
	require.Equal(t, http.StatusUnauthorized, resp.StatusCode)
	resp, _, err = doRaw(http.MethodPost, "/api/v1/auth/login", "not-json", "", "")
	require.NoError(t, err)
	require.Equal(t, http.StatusBadRequest, resp.StatusCode)
	resp, _, err = doRaw(http.MethodGet, "/api/v1/users/me", "", "some-jwt", "otherslug.example.com")
	require.NoError(t, err)
	require.Equal(t, http.StatusForbidden, resp.StatusCode)
}
