package ports

import (
	"context"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/permission"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/google/uuid"
)

// AccessAction represents an action to be authorized
type AccessAction string

const (
	AccessActionReadUser       AccessAction = "read_user"
	AccessActionUpdateUser     AccessAction = "update_user"
	AccessActionDeleteUser     AccessAction = "delete_user"
	AccessActionChangePassword AccessAction = "change_password"
	AccessActionUpdateEmail    AccessAction = "update_email"
)

// AccessControlService defines the interface for access control / policy checks
type AccessControlService interface {
	// CanPerformAction returns nil if allowed, or an error describing why the action is not allowed.
	// actorTenantID is the tenant ID of the acting user (from JWT or tenant resolution).
	CanPerformAction(ctx context.Context, actorID uuid.UUID, actorTenantID uuid.UUID, actorPermissions []permission.Permission, targetUserID uuid.UUID, action AccessAction) error
	// CanPerformActionWithTarget performs the same authorization decision but accepts a preloaded target user
	CanPerformActionWithTarget(ctx context.Context, actorID uuid.UUID, actorTenantID uuid.UUID, actorPermissions []permission.Permission, target *user.User, action AccessAction) error
}

// AccessControlError represents a typed error returned by access control checks.
// It is defined here so infrastructure can depend on the error contract without
// importing application-level implementations.
type AccessControlError interface {
	error
	Code() int
	Message() string
}

// Concrete implementation returned by NewAccessControlError.
type accessControlError struct {
	code    int
	message string
}

func (e *accessControlError) Error() string   { return e.message }
func (e *accessControlError) Code() int       { return e.code }
func (e *accessControlError) Message() string { return e.message }

const (
	ACCodeUnknown   = 0
	ACCodeNotFound  = 1
	ACCodeForbidden = 2
)

// NewAccessControlError constructs a typed AccessControlError that implementations
// in the application layer can return and infrastructure can inspect.
func NewAccessControlError(code int, message string) AccessControlError {
	return &accessControlError{code: code, message: message}
}
