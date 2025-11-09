package services_test

import (
	"context"
	"errors"
	"testing"

	impl "github.com/avatarctic/clean-architecture-saas/go/internal/application/services"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	tmocks "github.com/avatarctic/clean-architecture-saas/go/test/mocks"
	"github.com/google/uuid"
	"github.com/sirupsen/logrus"
)

// user repo: use tmocks.UserRepositoryMock in tests

type emailTokenRepoMock struct {
	createFn   func(ctx context.Context, t *user.EmailToken) error
	getFn      func(ctx context.Context, token string) (*user.EmailToken, error)
	markUsedFn func(ctx context.Context, id uuid.UUID) error
}

func (m *emailTokenRepoMock) Create(ctx context.Context, t *user.EmailToken) error {
	if m.createFn != nil {
		return m.createFn(ctx, t)
	}
	return nil
}
func (m *emailTokenRepoMock) Get(ctx context.Context, token string) (*user.EmailToken, error) {
	if m.getFn != nil {
		return m.getFn(ctx, token)
	}
	return nil, errors.New("not found")
}
func (m *emailTokenRepoMock) MarkAsUsed(ctx context.Context, id uuid.UUID) error {
	if m.markUsedFn != nil {
		return m.markUsedFn(ctx, id)
	}
	return nil
}

type emailServiceMock struct {
	sendVerFn func(ctx context.Context, email, token, name string) error
}

func (m *emailServiceMock) SendVerificationEmail(ctx context.Context, email, token, name string) error {
	if m.sendVerFn != nil {
		return m.sendVerFn(ctx, email, token, name)
	}
	return nil
}
func (m *emailServiceMock) SendEmailUpdateConfirmation(ctx context.Context, email, token, name string) error {
	return nil
}

func TestCreateUser_DuplicateEmail(t *testing.T) {
	ur := &tmocks.UserRepositoryMock{GetByEmailFn: func(ctx context.Context, email string) (*user.User, error) { return &user.User{Email: email}, nil }}
	svc := impl.NewUserService(ur, &emailServiceMock{}, nil, nil, &emailTokenRepoMock{}, nil)
	_, err := svc.CreateUser(context.Background(), &user.CreateUserRequest{Email: "a@b.com", Password: "TestPass123!"}, uuid.New())
	if err == nil {
		t.Fatalf("expected duplicate email error")
	}
}

func TestCreateUser_Success(t *testing.T) {
	ur := &tmocks.UserRepositoryMock{CreateFn: func(ctx context.Context, u *user.User) error { return nil }}
	etr := &emailTokenRepoMock{createFn: func(ctx context.Context, t *user.EmailToken) error { return nil }}
	es := &emailServiceMock{}
	logger := logrus.New()
	svc := impl.NewUserService(ur, es, nil, nil, etr, logger)
	req := &user.CreateUserRequest{Email: "ok@x.com", Password: "TestPass123!", FirstName: "A", LastName: "B", Role: user.RoleMember}
	u, err := svc.CreateUser(context.Background(), req, uuid.New())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if u.Email != "ok@x.com" {
		t.Fatalf("unexpected email: %s", u.Email)
	}
}
