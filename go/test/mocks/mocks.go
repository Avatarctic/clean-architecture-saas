package mocks

import (
	"context"
	"fmt"
	"time"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/audit"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/auth"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/feature"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/permission"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/tenant"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/google/uuid"
)

// TokenRepositoryMock is a lightweight mock for TokenRepository
type TokenRepositoryMock struct {
	StoreRefreshTokenFn     func(ctx context.Context, userID uuid.UUID, token string, expiresAt time.Time) error
	GetRefreshTokenFn       func(ctx context.Context, token string) (*ports.RefreshToken, error)
	DeleteRefreshTokenFn    func(ctx context.Context, token string) error
	BlacklistTokenFn        func(ctx context.Context, userID uuid.UUID, token string, expiresAt time.Time) error
	IsTokenBlacklistedFn    func(ctx context.Context, token string) (bool, error)
	StoreTokenClaimsFn      func(ctx context.Context, tokenHash string, claims *auth.Claims, expiresAt time.Time) error
	GetTokenClaimsFn        func(ctx context.Context, tokenHash string) (*auth.Claims, error)
	DeleteTokenClaimsFn     func(ctx context.Context, tokenHash string) error
	UpdateTokenActivityFn   func(ctx context.Context, tokenHash string, ipAddress, userAgent string) error
	DeleteUserTokensFn      func(ctx context.Context, userID uuid.UUID) error
	GetUserTokenClaimsFn    func(ctx context.Context, userID uuid.UUID) ([]*auth.Claims, error)
	DeleteUserTokenClaimsFn func(ctx context.Context, userID uuid.UUID, keepTokenHash *string) (int, error)
}

func (m *TokenRepositoryMock) StoreRefreshToken(ctx context.Context, userID uuid.UUID, token string, expiresAt time.Time) error {
	if m.StoreRefreshTokenFn != nil {
		return m.StoreRefreshTokenFn(ctx, userID, token, expiresAt)
	}
	return nil
}
func (m *TokenRepositoryMock) GetRefreshToken(ctx context.Context, token string) (*ports.RefreshToken, error) {
	if m.GetRefreshTokenFn != nil {
		return m.GetRefreshTokenFn(ctx, token)
	}
	return nil, fmt.Errorf("not found")
}
func (m *TokenRepositoryMock) DeleteRefreshToken(ctx context.Context, token string) error {
	if m.DeleteRefreshTokenFn != nil {
		return m.DeleteRefreshTokenFn(ctx, token)
	}
	return nil
}
func (m *TokenRepositoryMock) IsTokenBlacklisted(ctx context.Context, token string) (bool, error) {
	if m.IsTokenBlacklistedFn != nil {
		return m.IsTokenBlacklistedFn(ctx, token)
	}
	return false, nil
}
func (m *TokenRepositoryMock) BlacklistToken(ctx context.Context, userID uuid.UUID, token string, expiresAt time.Time) error {
	if m.BlacklistTokenFn != nil {
		return m.BlacklistTokenFn(ctx, userID, token, expiresAt)
	}
	return nil
}
func (m *TokenRepositoryMock) StoreTokenClaims(ctx context.Context, tokenHash string, claims *auth.Claims, expiresAt time.Time) error {
	if m.StoreTokenClaimsFn != nil {
		return m.StoreTokenClaimsFn(ctx, tokenHash, claims, expiresAt)
	}
	return nil
}
func (m *TokenRepositoryMock) GetTokenClaims(ctx context.Context, tokenHash string) (*auth.Claims, error) {
	if m.GetTokenClaimsFn != nil {
		return m.GetTokenClaimsFn(ctx, tokenHash)
	}
	return nil, fmt.Errorf("not found")
}
func (m *TokenRepositoryMock) UpdateTokenActivity(ctx context.Context, tokenHash string, ipAddress, userAgent string) error {
	if m.UpdateTokenActivityFn != nil {
		return m.UpdateTokenActivityFn(ctx, tokenHash, ipAddress, userAgent)
	}
	return nil
}
func (m *TokenRepositoryMock) DeleteTokenClaims(ctx context.Context, tokenHash string) error {
	if m.DeleteTokenClaimsFn != nil {
		return m.DeleteTokenClaimsFn(ctx, tokenHash)
	}
	return nil
}
func (m *TokenRepositoryMock) GetUserTokenClaims(ctx context.Context, userID uuid.UUID) ([]*auth.Claims, error) {
	if m.GetUserTokenClaimsFn != nil {
		return m.GetUserTokenClaimsFn(ctx, userID)
	}
	return nil, nil
}
func (m *TokenRepositoryMock) DeleteUserTokenClaims(ctx context.Context, userID uuid.UUID, keepTokenHash *string) (int, error) {
	if m.DeleteUserTokenClaimsFn != nil {
		return m.DeleteUserTokenClaimsFn(ctx, userID, keepTokenHash)
	}
	return 0, nil
}
func (m *TokenRepositoryMock) DeleteExpiredRefreshTokens(ctx context.Context) error     { return nil }
func (m *TokenRepositoryMock) DeleteExpiredBlacklistedTokens(ctx context.Context) error { return nil }
func (m *TokenRepositoryMock) DeleteExpiredTokenClaims(ctx context.Context) error       { return nil }
func (m *TokenRepositoryMock) DeleteUserTokens(ctx context.Context, userID uuid.UUID) error {
	if m.DeleteUserTokensFn != nil {
		return m.DeleteUserTokensFn(ctx, userID)
	}
	return nil
}

// UserRepository mock
type UserRepositoryMock struct {
	CreateFn     func(ctx context.Context, u *user.User) error
	GetByEmailFn func(ctx context.Context, email string) (*user.User, error)
	GetByIDFn    func(ctx context.Context, id uuid.UUID) (*user.User, error)
	UpdateFn     func(ctx context.Context, u *user.User) error
}

func (m *UserRepositoryMock) Create(ctx context.Context, u *user.User) error {
	if m.CreateFn != nil {
		return m.CreateFn(ctx, u)
	}
	return nil
}
func (m *UserRepositoryMock) GetByID(ctx context.Context, id uuid.UUID) (*user.User, error) {
	if m.GetByIDFn != nil {
		return m.GetByIDFn(ctx, id)
	}
	return nil, fmt.Errorf("not found")
}
func (m *UserRepositoryMock) GetByEmail(ctx context.Context, email string) (*user.User, error) {
	if m.GetByEmailFn != nil {
		return m.GetByEmailFn(ctx, email)
	}
	return nil, fmt.Errorf("not found")
}
func (m *UserRepositoryMock) Update(ctx context.Context, u *user.User) error {
	if m.UpdateFn != nil {
		return m.UpdateFn(ctx, u)
	}
	return nil
}
func (m *UserRepositoryMock) Delete(ctx context.Context, id uuid.UUID) error { return nil }
func (m *UserRepositoryMock) List(ctx context.Context, tenantID uuid.UUID, limit, offset int) ([]*user.User, error) {
	return nil, nil
}
func (m *UserRepositoryMock) Count(ctx context.Context, tenantID uuid.UUID) (int, error) {
	return 0, nil
}

// UserServiceMock is a lightweight mock implementing ports.UserService
type UserServiceMock struct {
	CreateUserFn              func(ctx context.Context, req *user.CreateUserRequest, tenantID uuid.UUID) (*user.User, error)
	CreateUserInTenantFn      func(ctx context.Context, req *user.CreateUserRequest, tenantID uuid.UUID) (*user.User, error)
	GetUserFn                 func(ctx context.Context, id uuid.UUID) (*user.User, error)
	GetUserByEmailFn          func(ctx context.Context, email string) (*user.User, error)
	UpdateUserFn              func(ctx context.Context, id uuid.UUID, req *user.UpdateUserRequest) (*user.User, error)
	DeleteUserFn              func(ctx context.Context, id uuid.UUID) error
	ListUsersFn               func(ctx context.Context, tenantID uuid.UUID, limit, offset int) ([]*user.User, int, error)
	VerifyPasswordFn          func(ctx context.Context, userID uuid.UUID, password string) error
	ChangePasswordFn          func(ctx context.Context, userID uuid.UUID, oldPassword, newPassword string) error
	SendVerificationEmailFn   func(ctx context.Context, userID uuid.UUID) error
	VerifyEmailFn             func(ctx context.Context, token string) (*user.User, error)
	ResendVerificationEmailFn func(ctx context.Context, email string) error
	RequestEmailUpdateFn      func(ctx context.Context, userID uuid.UUID, req *user.UpdateEmailRequest) error
	ConfirmEmailUpdateFn      func(ctx context.Context, token string) (*user.User, error)
}

func (m *UserServiceMock) CreateUser(ctx context.Context, req *user.CreateUserRequest, tenantID uuid.UUID) (*user.User, error) {
	if m.CreateUserFn != nil {
		return m.CreateUserFn(ctx, req, tenantID)
	}
	return nil, nil
}
func (m *UserServiceMock) CreateUserInTenant(ctx context.Context, req *user.CreateUserRequest, tenantID uuid.UUID) (*user.User, error) {
	if m.CreateUserInTenantFn != nil {
		return m.CreateUserInTenantFn(ctx, req, tenantID)
	}
	return nil, nil
}
func (m *UserServiceMock) GetUser(ctx context.Context, id uuid.UUID) (*user.User, error) {
	if m.GetUserFn != nil {
		return m.GetUserFn(ctx, id)
	}
	return nil, nil
}
func (m *UserServiceMock) GetUserByEmail(ctx context.Context, email string) (*user.User, error) {
	if m.GetUserByEmailFn != nil {
		return m.GetUserByEmailFn(ctx, email)
	}
	return nil, nil
}
func (m *UserServiceMock) UpdateUser(ctx context.Context, id uuid.UUID, req *user.UpdateUserRequest) (*user.User, error) {
	if m.UpdateUserFn != nil {
		return m.UpdateUserFn(ctx, id, req)
	}
	return nil, nil
}
func (m *UserServiceMock) DeleteUser(ctx context.Context, id uuid.UUID) error {
	if m.DeleteUserFn != nil {
		return m.DeleteUserFn(ctx, id)
	}
	return nil
}
func (m *UserServiceMock) ListUsers(ctx context.Context, tenantID uuid.UUID, limit, offset int) ([]*user.User, int, error) {
	if m.ListUsersFn != nil {
		return m.ListUsersFn(ctx, tenantID, limit, offset)
	}
	return nil, 0, nil
}
func (m *UserServiceMock) VerifyPassword(ctx context.Context, userID uuid.UUID, password string) error {
	if m.VerifyPasswordFn != nil {
		return m.VerifyPasswordFn(ctx, userID, password)
	}
	return nil
}
func (m *UserServiceMock) ChangePassword(ctx context.Context, userID uuid.UUID, oldPassword, newPassword string) error {
	if m.ChangePasswordFn != nil {
		return m.ChangePasswordFn(ctx, userID, oldPassword, newPassword)
	}
	return nil
}
func (m *UserServiceMock) SendVerificationEmail(ctx context.Context, userID uuid.UUID) error {
	if m.SendVerificationEmailFn != nil {
		return m.SendVerificationEmailFn(ctx, userID)
	}
	return nil
}
func (m *UserServiceMock) VerifyEmail(ctx context.Context, token string) (*user.User, error) {
	if m.VerifyEmailFn != nil {
		return m.VerifyEmailFn(ctx, token)
	}
	return nil, nil
}
func (m *UserServiceMock) ResendVerificationEmail(ctx context.Context, email string) error {
	if m.ResendVerificationEmailFn != nil {
		return m.ResendVerificationEmailFn(ctx, email)
	}
	return nil
}
func (m *UserServiceMock) RequestEmailUpdate(ctx context.Context, userID uuid.UUID, req *user.UpdateEmailRequest) error {
	if m.RequestEmailUpdateFn != nil {
		return m.RequestEmailUpdateFn(ctx, userID, req)
	}
	return nil
}
func (m *UserServiceMock) ConfirmEmailUpdate(ctx context.Context, token string) (*user.User, error) {
	if m.ConfirmEmailUpdateFn != nil {
		return m.ConfirmEmailUpdateFn(ctx, token)
	}
	return nil, nil
}

// TenantRepository mock
type TenantRepositoryMock struct {
	GetByIDFn   func(ctx context.Context, id uuid.UUID) (*tenant.Tenant, error)
	GetBySlugFn func(ctx context.Context, slug string) (*tenant.Tenant, error)
}

// Allow implements ports.RateLimiterService.
func (m *TenantRepositoryMock) Allow(ctx context.Context, tenantID uuid.UUID) (allowed bool, remaining int, limit int, reset time.Time, err error) {
	// Default to allowing requests in tests unless the test overrides AllowFn on a more specific mock.
	return true, 100, 1000, time.Now().Add(time.Minute), nil
}

// CanPerformAction implements ports.AccessControlService.
func (m *TenantRepositoryMock) CanPerformAction(ctx context.Context, actorID uuid.UUID, actorTenantID uuid.UUID, actorPermissions []permission.Permission, targetUserID uuid.UUID, action ports.AccessAction) error {
	// By default, allow the action in tests.
	return nil
}

// CanPerformActionWithTarget implements ports.AccessControlService.
func (m *TenantRepositoryMock) CanPerformActionWithTarget(ctx context.Context, actorID uuid.UUID, actorTenantID uuid.UUID, actorPermissions []permission.Permission, target *user.User, action ports.AccessAction) error {
	// By default, allow the action in tests.
	return nil
}

// GetAuditLogs implements ports.AuditService.
func (m *TenantRepositoryMock) GetAuditLogs(ctx context.Context, filter *audit.AuditLogFilter) ([]*audit.AuditLog, int, error) {
	// No audit logs by default.
	return nil, 0, nil
}

// LogAction implements ports.AuditService.
func (m *TenantRepositoryMock) LogAction(ctx context.Context, req *audit.CreateAuditLogRequest) error {
	// No-op logging in tests.
	return nil
}

// CreateFeatureFlag implements ports.FeatureFlagService.
func (m *TenantRepositoryMock) CreateFeatureFlag(ctx context.Context, req *feature.CreateFeatureFlagRequest) (*feature.FeatureFlag, error) {
	return nil, nil
}

// DeleteFeatureFlag implements ports.FeatureFlagService.
func (m *TenantRepositoryMock) DeleteFeatureFlag(ctx context.Context, id uuid.UUID) error {
	return nil
}

// GetFeatureValue implements ports.FeatureFlagService.
func (m *TenantRepositoryMock) GetFeatureValue(ctx context.Context, key string, context *feature.FeatureFlagContext) (any, error) {
	return nil, nil
}

// IsFeatureEnabled implements ports.FeatureFlagService.
func (m *TenantRepositoryMock) IsFeatureEnabled(ctx context.Context, key string, context *feature.FeatureFlagContext) (bool, error) {
	return false, nil
}

// ListFeatureFlags implements ports.FeatureFlagService.
func (m *TenantRepositoryMock) ListFeatureFlags(ctx context.Context, limit int, offset int) ([]*feature.FeatureFlag, int, error) {
	return nil, 0, nil
}

// UpdateFeatureFlag implements ports.FeatureFlagService.
func (m *TenantRepositoryMock) UpdateFeatureFlag(ctx context.Context, id uuid.UUID, req *feature.UpdateFeatureFlagRequest) (*feature.FeatureFlag, error) {
	return nil, nil
}

// CreateTenant implements ports.TenantService.
func (m *TenantRepositoryMock) CreateTenant(ctx context.Context, req *tenant.CreateTenantRequest) (*tenant.Tenant, error) {
	return nil, nil
}

// DeleteTenant implements ports.TenantService.
func (m *TenantRepositoryMock) DeleteTenant(ctx context.Context, id uuid.UUID) error {
	return nil
}

// GetActiveTenant implements ports.TenantService.
func (m *TenantRepositoryMock) GetActiveTenant(ctx context.Context, id uuid.UUID) (*tenant.Tenant, error) {
	return nil, fmt.Errorf("not found")
}

// GetTenant implements ports.TenantService.
func (m *TenantRepositoryMock) GetTenant(ctx context.Context, id uuid.UUID) (*tenant.Tenant, error) {
	if m.GetByIDFn != nil {
		return m.GetByIDFn(ctx, id)
	}
	return nil, fmt.Errorf("not found")
}

// GetTenantBySlug implements ports.TenantService.
func (m *TenantRepositoryMock) GetTenantBySlug(ctx context.Context, slug string) (*tenant.Tenant, error) {
	if m.GetBySlugFn != nil {
		return m.GetBySlugFn(ctx, slug)
	}
	return nil, fmt.Errorf("not found")
}

// ListTenants implements ports.TenantService.
func (m *TenantRepositoryMock) ListTenants(ctx context.Context, limit int, offset int) ([]*tenant.Tenant, int, error) {
	return nil, 0, nil
}

// UpdateTenant implements ports.TenantService.
func (m *TenantRepositoryMock) UpdateTenant(ctx context.Context, id uuid.UUID, req *tenant.UpdateTenantRequest) (*tenant.Tenant, error) {
	return nil, nil
}

func (m *TenantRepositoryMock) Create(ctx context.Context, t *tenant.Tenant) error { return nil }
func (m *TenantRepositoryMock) GetByID(ctx context.Context, id uuid.UUID) (*tenant.Tenant, error) {
	if m.GetByIDFn != nil {
		return m.GetByIDFn(ctx, id)
	}
	return nil, fmt.Errorf("not found")
}
func (m *TenantRepositoryMock) GetBySlug(ctx context.Context, slug string) (*tenant.Tenant, error) {
	if m.GetBySlugFn != nil {
		return m.GetBySlugFn(ctx, slug)
	}
	return nil, fmt.Errorf("not found")
}
func (m *TenantRepositoryMock) Update(ctx context.Context, t *tenant.Tenant) error { return nil }
func (m *TenantRepositoryMock) Delete(ctx context.Context, id uuid.UUID) error     { return nil }
func (m *TenantRepositoryMock) List(ctx context.Context, limit, offset int) ([]*tenant.Tenant, error) {
	return nil, nil
}
func (m *TenantRepositoryMock) Count(ctx context.Context) (int, error) { return 0, nil }

// AuthService mock (minimal)
type AuthServiceMock struct {
	LoginFn                    func(ctx context.Context, req *auth.LoginRequest) (*auth.AuthTokens, error)
	RefreshFn                  func(ctx context.Context, refreshToken string) (*auth.AuthTokens, error)
	LogoutFn                   func(ctx context.Context, userID uuid.UUID, token string) error
	StartSessionFn             func(ctx context.Context, token string, ipAddress, userAgent string) (*auth.Claims, error)
	GetTokenHashFn             func(token string) string
	TerminateSessionFn         func(ctx context.Context, userID uuid.UUID, tokenHash string) error
	TerminateAllUserSessionsFn func(ctx context.Context, userID uuid.UUID, excludeTokenHash *string) (int, error)
}

func (m *AuthServiceMock) Login(ctx context.Context, req *auth.LoginRequest) (*auth.AuthTokens, error) {
	if m.LoginFn != nil {
		return m.LoginFn(ctx, req)
	}
	return nil, fmt.Errorf("not implemented")
}
func (m *AuthServiceMock) RefreshToken(ctx context.Context, refreshToken string) (*auth.AuthTokens, error) {
	if m.RefreshFn != nil {
		return m.RefreshFn(ctx, refreshToken)
	}
	return nil, fmt.Errorf("not implemented")
}
func (m *AuthServiceMock) ValidateToken(ctx context.Context, token string) (*auth.Claims, error) {
	return nil, fmt.Errorf("not implemented")
}
func (m *AuthServiceMock) Logout(ctx context.Context, userID uuid.UUID, token string) error {
	if m.LogoutFn != nil {
		return m.LogoutFn(ctx, userID, token)
	}
	return nil
}
func (m *AuthServiceMock) GenerateTokens(ctx context.Context, user *user.User) (*auth.AuthTokens, error) {
	return nil, fmt.Errorf("not implemented")
}
func (m *AuthServiceMock) StartSession(ctx context.Context, token string, ipAddress, userAgent string) (*auth.Claims, error) {
	if m.StartSessionFn != nil {
		return m.StartSessionFn(ctx, token, ipAddress, userAgent)
	}
	return nil, fmt.Errorf("not implemented")
}
func (m *AuthServiceMock) GetUserSessions(ctx context.Context, userID uuid.UUID) ([]*auth.Claims, error) {
	return nil, nil
}
func (m *AuthServiceMock) TerminateSession(ctx context.Context, userID uuid.UUID, tokenHash string) error {
	if m.TerminateSessionFn != nil {
		return m.TerminateSessionFn(ctx, userID, tokenHash)
	}
	return nil
}
func (m *AuthServiceMock) TerminateAllUserSessions(ctx context.Context, userID uuid.UUID, excludeTokenHash *string) (int, error) {
	if m.TerminateAllUserSessionsFn != nil {
		return m.TerminateAllUserSessionsFn(ctx, userID, excludeTokenHash)
	}
	return 0, nil
}
func (m *AuthServiceMock) GetTokenHash(token string) string {
	if m.GetTokenHashFn != nil {
		return m.GetTokenHashFn(token)
	}
	return ""
}

// PermissionService mock (minimal)
type PermissionServiceMock struct {
	GetRolePermissionsFn func(ctx context.Context, role user.UserRole) ([]permission.Permission, error)
	HasPermissionFn      func(perms []permission.Permission, p permission.Permission) bool
	HasAnyPermissionFn   func(perms []permission.Permission, targetPermissions ...permission.Permission) bool
}

func (m *PermissionServiceMock) GetRolePermissions(ctx context.Context, role user.UserRole) ([]permission.Permission, error) {
	if m.GetRolePermissionsFn != nil {
		return m.GetRolePermissionsFn(ctx, role)
	}
	return nil, nil
}
func (m *PermissionServiceMock) AddPermissionToRole(ctx context.Context, role user.UserRole, perm permission.Permission) error {
	return nil
}
func (m *PermissionServiceMock) RemovePermissionFromRole(ctx context.Context, role user.UserRole, perm permission.Permission) error {
	return nil
}
func (m *PermissionServiceMock) SetRolePermissions(ctx context.Context, role user.UserRole, permissions []permission.Permission) error {
	return nil
}
func (m *PermissionServiceMock) HasPermission(perms []permission.Permission, targetPermission permission.Permission) bool {
	if m.HasPermissionFn != nil {
		return m.HasPermissionFn(perms, targetPermission)
	}
	return false
}
func (m *PermissionServiceMock) HasAnyPermission(perms []permission.Permission, targetPermissions ...permission.Permission) bool {
	if m.HasAnyPermissionFn != nil {
		return m.HasAnyPermissionFn(perms, targetPermissions...)
	}
	return false
}
func (m *PermissionServiceMock) HasAllPermissions(perms []permission.Permission, targetPermissions ...permission.Permission) bool {
	return false
}
func (m *PermissionServiceMock) ValidatePermission(perm permission.Permission) bool { return true }
func (m *PermissionServiceMock) GetAvailablePermissions() []permission.Permission   { return nil }

// end of mocks
