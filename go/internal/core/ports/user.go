package ports

import (
	"context"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/google/uuid"
)

// UserRepository defines the interface for user data operations
type UserRepository interface {
	Create(ctx context.Context, user *user.User) error
	GetByID(ctx context.Context, id uuid.UUID) (*user.User, error)
	GetByEmail(ctx context.Context, email string) (*user.User, error)
	Update(ctx context.Context, user *user.User) error
	Delete(ctx context.Context, id uuid.UUID) error
	List(ctx context.Context, tenantID uuid.UUID, limit, offset int) ([]*user.User, error)
	Count(ctx context.Context, tenantID uuid.UUID) (int, error)
}

// UserService defines the interface for user business logic
type UserService interface {
	CreateUser(ctx context.Context, req *user.CreateUserRequest, tenantID uuid.UUID) (*user.User, error)
	CreateUserInTenant(ctx context.Context, req *user.CreateUserRequest, tenantID uuid.UUID) (*user.User, error)
	GetUser(ctx context.Context, id uuid.UUID) (*user.User, error)
	GetUserByEmail(ctx context.Context, email string) (*user.User, error)
	UpdateUser(ctx context.Context, id uuid.UUID, req *user.UpdateUserRequest) (*user.User, error)
	DeleteUser(ctx context.Context, id uuid.UUID) error
	ListUsers(ctx context.Context, tenantID uuid.UUID, limit, offset int) ([]*user.User, int, error)
	VerifyPassword(ctx context.Context, userID uuid.UUID, password string) error
	ChangePassword(ctx context.Context, userID uuid.UUID, oldPassword, newPassword string) error

	// Email verification methods
	SendVerificationEmail(ctx context.Context, userID uuid.UUID) error
	VerifyEmail(ctx context.Context, token string) (*user.User, error)
	ResendVerificationEmail(ctx context.Context, email string) error

	// Email update methods
	RequestEmailUpdate(ctx context.Context, userID uuid.UUID, req *user.UpdateEmailRequest) error
	ConfirmEmailUpdate(ctx context.Context, token string) (*user.User, error)
}
