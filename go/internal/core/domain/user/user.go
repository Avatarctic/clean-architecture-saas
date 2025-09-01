package user

import (
	"time"

	"github.com/google/uuid"
)

type User struct {
	ID            uuid.UUID  `json:"id" db:"id"`
	Email         string     `json:"email" db:"email"`
	PasswordHash  string     `json:"-" db:"password_hash"`
	FirstName     string     `json:"first_name" db:"first_name"`
	LastName      string     `json:"last_name" db:"last_name"`
	Role          UserRole   `json:"role" db:"role"`
	TenantID      uuid.UUID  `json:"tenant_id" db:"tenant_id"`
	IsActive      bool       `json:"is_active" db:"is_active"`
	EmailVerified bool       `json:"email_verified" db:"email_verified"`
	AuditEnabled  bool       `json:"audit_enabled" db:"audit_enabled"`
	LastLoginAt   *time.Time `json:"last_login_at" db:"last_login_at"`
	CreatedAt     time.Time  `json:"created_at" db:"created_at"`
	UpdatedAt     time.Time  `json:"updated_at" db:"updated_at"`
}

type UserRole string

const (
	RoleSuperAdmin UserRole = "super_admin"
	RoleAdmin      UserRole = "admin"
	RoleMember     UserRole = "member"
	RoleGuest      UserRole = "guest"
)

func (r UserRole) String() string {
	return string(r)
}

func (r UserRole) IsValid() bool {
	switch r {
	case RoleSuperAdmin, RoleAdmin, RoleMember, RoleGuest:
		return true
	default:
		return false
	}
}

// CreateUserRequest represents the request to create a new user
type CreateUserRequest struct {
	Email        string   `json:"email" validate:"required,email"`
	Password     string   `json:"password" validate:"required,min=8"`
	FirstName    string   `json:"first_name" validate:"required"`
	LastName     string   `json:"last_name" validate:"required"`
	Role         UserRole `json:"role" validate:"required"`
	AuditEnabled *bool    `json:"audit_enabled,omitempty"`
}

// UpdateUserRequest represents the request to update a user
type UpdateUserRequest struct {
	FirstName    *string   `json:"first_name,omitempty"`
	LastName     *string   `json:"last_name,omitempty"`
	Role         *UserRole `json:"role,omitempty"`
	IsActive     *bool     `json:"is_active,omitempty"`
	AuditEnabled *bool     `json:"audit_enabled,omitempty"`
}

// UpdateEmailRequest represents the request to update user's email
type UpdateEmailRequest struct {
	NewEmail string `json:"new_email" validate:"required,email"`
	Password string `json:"password" validate:"required"` // Require password for security
}

// ConfirmEmailUpdateRequest represents the request to confirm email update
type ConfirmEmailUpdateRequest struct {
	Token string `json:"token" validate:"required"`
}

// EmailTokenType represents the type of email token
type EmailTokenType string

const (
	EmailTokenTypeVerification EmailTokenType = "verification"
	EmailTokenTypeEmailUpdate  EmailTokenType = "email_update"
)

// EmailToken represents a unified email token for verification and email updates
type EmailToken struct {
	ID        uuid.UUID      `json:"id" db:"id"`
	UserID    uuid.UUID      `json:"user_id" db:"user_id"`
	Token     string         `json:"token" db:"token"`
	Type      EmailTokenType `json:"type" db:"type"`
	NewEmail  *string        `json:"new_email,omitempty" db:"new_email"` // Only for email updates
	ExpiresAt time.Time      `json:"expires_at" db:"expires_at"`
	UsedAt    *time.Time     `json:"used_at" db:"used_at"`
	CreatedAt time.Time      `json:"created_at" db:"created_at"`
}

// IsExpired checks if the email token has expired
func (et *EmailToken) IsExpired() bool {
	return time.Now().After(et.ExpiresAt)
}

// IsUsed checks if the email token has been used
func (et *EmailToken) IsUsed() bool {
	return et.UsedAt != nil
}

// IsValid checks if the email token is still valid (not expired and not used)
func (et *EmailToken) IsValid() bool {
	return !et.IsExpired() && !et.IsUsed()
}

// IsVerificationToken checks if this is a verification token
func (et *EmailToken) IsVerificationToken() bool {
	return et.Type == EmailTokenTypeVerification
}

// IsEmailUpdateToken checks if this is an email update token
func (et *EmailToken) IsEmailUpdateToken() bool {
	return et.Type == EmailTokenTypeEmailUpdate
}

// VerifyEmailRequest represents the request to verify an email
type VerifyEmailRequest struct {
	Token string `json:"token" validate:"required"`
}

// ResendVerificationRequest represents the request to resend verification email
type ResendVerificationRequest struct {
	Email string `json:"email" validate:"required,email"`
}
