package httpserver_test

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/labstack/echo/v4"
	"github.com/sirupsen/logrus"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/auth"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/permission"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/httpserver/middleware"
	tmocks "github.com/avatarctic/clean-architecture-saas/go/test/mocks"
	"github.com/stretchr/testify/require"
)

func TestJWTMiddleware_MissingTokenReturns401(t *testing.T) {
	e := echo.New()
	m := middleware.NewJWTMiddleware(&tmocks.AuthServiceMock{}, &tmocks.UserServiceMock{}, &tmocks.PermissionServiceMock{}, logrus.New())
	handler := m.RequireJWT()(func(c echo.Context) error { return c.NoContent(http.StatusOK) })
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	rec := httptest.NewRecorder()
	c := e.NewContext(req, rec)
	err := handler(c)
	require.Error(t, err)
	htErr, ok := err.(*echo.HTTPError)
	require.True(t, ok)
	require.Equal(t, http.StatusUnauthorized, htErr.Code)
}

func TestJWTMiddleware_InvalidTokenReturns401(t *testing.T) {
	e := echo.New()
	authMock := &tmocks.AuthServiceMock{StartSessionFn: func(ctx context.Context, token string, ip, ua string) (*auth.Claims, error) {
		return nil, fmt.Errorf("bad")
	}}
	m := middleware.NewJWTMiddleware(authMock, &tmocks.UserServiceMock{}, &tmocks.PermissionServiceMock{}, logrus.New())
	handler := m.RequireJWT()(func(c echo.Context) error { return c.NoContent(http.StatusOK) })
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.Header.Set("Authorization", "Bearer invalid")
	rec := httptest.NewRecorder()
	c := e.NewContext(req, rec)
	err := handler(c)
	require.Error(t, err)
	htErr, ok := err.(*echo.HTTPError)
	require.True(t, ok)
	require.Equal(t, http.StatusUnauthorized, htErr.Code)
}

func TestPermMiddleware_Returns403WhenMissingPermission(t *testing.T) {
	e := echo.New()
	permMock := &tmocks.PermissionServiceMock{HasPermissionFn: func(perms []permission.Permission, p permission.Permission) bool { return false }}
	m := middleware.NewPermMiddleware(permMock, &tmocks.UserServiceMock{}, "s")
	h := m.RequirePermission(permission.Permission("can_edit"))(func(c echo.Context) error { return c.NoContent(http.StatusOK) })
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	rec := httptest.NewRecorder()
	c := e.NewContext(req, rec)
	err := h(c)
	require.Error(t, err)
	htErr, ok := err.(*echo.HTTPError)
	require.True(t, ok)
	require.Equal(t, http.StatusUnauthorized, htErr.Code)
	c.Set("user_permissions", []permission.Permission{permission.Permission("other")})
	err = h(c)
	require.Error(t, err)
	htErr, ok = err.(*echo.HTTPError)
	require.True(t, ok)
	require.Equal(t, http.StatusForbidden, htErr.Code)
}

func TestPermMiddleware_AllowsWhenPermissionPresent(t *testing.T) {
	e := echo.New()
	permMock := &tmocks.PermissionServiceMock{HasPermissionFn: func(perms []permission.Permission, p permission.Permission) bool { return true }}
	m := middleware.NewPermMiddleware(permMock, &tmocks.UserServiceMock{}, "s")
	h := m.RequirePermission(permission.Permission("can_edit"))(func(c echo.Context) error { return c.NoContent(http.StatusOK) })
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	rec := httptest.NewRecorder()
	c := e.NewContext(req, rec)
	c.Set("user_permissions", []permission.Permission{permission.Permission("can_edit")})
	err := h(c)
	require.NoError(t, err)
}
