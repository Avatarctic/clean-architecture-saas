package httpserver_test

import (
	"bytes"
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/auth"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/permission"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	saas_http "github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/httpserver"
	"github.com/avatarctic/clean-architecture-saas/go/test/mocks"
	"github.com/google/uuid"
	"github.com/labstack/echo/v4"
	"github.com/sirupsen/logrus"
	"github.com/stretchr/testify/require"
)

var errInvalid = echo.NewHTTPError(http.StatusUnauthorized, "invalid token")

func TestTerminateSessionHandler(t *testing.T) {
	tokenHash := "thash"
	userID := uuid.New()
	authMock := &mocks.AuthServiceMock{}
	authMock.StartSessionFn = func(ctx context.Context, token string, ip, ua string) (*auth.Claims, error) {
		if token != "sometoken" {
			return nil, errInvalid
		}
		return &auth.Claims{UserID: userID, Role: user.UserRole("admin"), Email: "u@e.com", TenantID: uuid.Nil}, nil
	}
	authMock.TerminateSessionFn = func(ctx context.Context, uid uuid.UUID, th string) error {
		if uid != userID || th != tokenHash {
			return echo.NewHTTPError(http.StatusBadRequest)
		}
		return nil
	}
	userMock := &mocks.UserServiceMock{}
	userMock.GetUserFn = func(ctx context.Context, id uuid.UUID) (*user.User, error) {
		return &user.User{ID: id, TenantID: uuid.Nil, AuditEnabled: true}, nil
	}
	permMock := &mocks.PermissionServiceMock{}
	permMock.GetRolePermissionsFn = func(ctx context.Context, role user.UserRole) ([]permission.Permission, error) { return nil, nil }
	permMock.HasAnyPermissionFn = func(perms []permission.Permission, targetPermissions ...permission.Permission) bool { return true }
	deps := saas_http.ServerDeps{
		UserService:       userMock,
		AuthService:       authMock,
		PermissionService: permMock,
		HealthCheckers:    nil,
	}
	srv := saas_http.NewServer(&saas_http.ServerConfig{Host: "127.0.0.1", Port: "0", ReadTimeout: time.Second, WriteTimeout: time.Second, IdleTimeout: time.Second}, "s", logrus.New(), deps)
	srv.Echo().Validator = &testValidator{}
	ts := httptest.NewServer(srv.Echo())
	defer ts.Close()
	req, _ := http.NewRequest(http.MethodDelete, ts.URL+"/api/v1/users/"+userID.String()+"/sessions/"+tokenHash, nil)
	req.Header.Set("Authorization", "Bearer sometoken")
	resp, err := http.DefaultClient.Do(req)
	require.NoError(t, err)
	require.Equal(t, http.StatusOK, resp.StatusCode)
}

func TestTerminateAllSessionsHandler(t *testing.T) {
	userID := uuid.New()
	authMock := &mocks.AuthServiceMock{}
	authMock.StartSessionFn = func(ctx context.Context, token string, ip, ua string) (*auth.Claims, error) {
		if token != "sometoken" {
			return nil, errInvalid
		}
		return &auth.Claims{UserID: userID, Role: user.UserRole("admin"), Email: "u@e.com", TenantID: uuid.Nil}, nil
	}
	authMock.TerminateAllUserSessionsFn = func(ctx context.Context, uid uuid.UUID, exclude *string) (int, error) {
		if uid != userID {
			return 0, echo.NewHTTPError(http.StatusBadRequest)
		}
		return 2, nil
	}
	userMock := &mocks.UserServiceMock{}
	userMock.GetUserFn = func(ctx context.Context, id uuid.UUID) (*user.User, error) {
		return &user.User{ID: id, TenantID: uuid.Nil, AuditEnabled: true}, nil
	}
	permMock := &mocks.PermissionServiceMock{}
	permMock.GetRolePermissionsFn = func(ctx context.Context, role user.UserRole) ([]permission.Permission, error) { return nil, nil }
	permMock.HasAnyPermissionFn = func(perms []permission.Permission, targetPermissions ...permission.Permission) bool { return true }
	deps := saas_http.ServerDeps{
		UserService:       userMock,
		AuthService:       authMock,
		PermissionService: permMock,
		HealthCheckers:    nil,
	}
	srv := saas_http.NewServer(&saas_http.ServerConfig{Host: "127.0.0.1", Port: "0"}, "s", logrus.New(), deps)
	srv.Echo().Validator = &testValidator{}
	ts := httptest.NewServer(srv.Echo())
	defer ts.Close()
	req, _ := http.NewRequest(http.MethodDelete, ts.URL+"/api/v1/users/"+userID.String()+"/sessions", bytes.NewReader([]byte{}))
	req.Header.Set("Authorization", "Bearer sometoken")
	resp, err := http.DefaultClient.Do(req)
	require.NoError(t, err)
	require.Equal(t, http.StatusOK, resp.StatusCode)
}
