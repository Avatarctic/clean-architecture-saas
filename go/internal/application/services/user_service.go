package services

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"time"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/tenant"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/google/uuid"
	"github.com/sirupsen/logrus"
	"golang.org/x/crypto/bcrypt"
)

type UserService struct {
	repo           ports.UserRepository
	emailService   ports.EmailService
	tenantRepo     ports.TenantRepository
	tokenRepo      ports.TokenRepository
	emailTokenRepo ports.EmailTokenRepository
	logger         *logrus.Logger
}

func NewUserService(repo ports.UserRepository, emailService ports.EmailService, tenantRepo ports.TenantRepository, tokenRepo ports.TokenRepository, emailTokenRepo ports.EmailTokenRepository, logger *logrus.Logger) ports.UserService {
	return &UserService{
		repo:           repo,
		emailService:   emailService,
		tenantRepo:     tenantRepo,
		tokenRepo:      tokenRepo,
		emailTokenRepo: emailTokenRepo,
		logger:         logger,
	}
}

func (s *UserService) CreateUser(ctx context.Context, req *user.CreateUserRequest, tenantID uuid.UUID) (*user.User, error) {
	// Enforce tenant user limit if configured
	if s.tenantRepo != nil {
		if t, err := s.tenantRepo.GetByID(ctx, tenantID); err == nil && t != nil {
			if t.Settings.Limits.MaxUsers > 0 { // limit enabled
				currentCount, err := s.repo.Count(ctx, tenantID)
				if err == nil && currentCount >= t.Settings.Limits.MaxUsers {
					return nil, fmt.Errorf("tenant user limit (%d) reached", t.Settings.Limits.MaxUsers)
				}
			}
		}
	}
	// Validate email uniqueness
	if existingUser, err := s.repo.GetByEmail(ctx, req.Email); err == nil && existingUser != nil {
		return nil, fmt.Errorf("email '%s' is already taken", req.Email)
	}

	// Hash password
	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
	if err != nil {
		return nil, fmt.Errorf("failed to hash password: %w", err)
	}

	// Create user entity
	newUser := &user.User{
		ID:            uuid.New(),
		Email:         req.Email,
		PasswordHash:  string(hashedPassword),
		FirstName:     req.FirstName,
		LastName:      req.LastName,
		Role:          req.Role,
		TenantID:      tenantID,
		IsActive:      true,
		EmailVerified: false,
		CreatedAt:     time.Now(),
		UpdatedAt:     time.Now(),
	}

	// Save to repository
	if err := s.repo.Create(ctx, newUser); err != nil {
		return nil, fmt.Errorf("failed to create user: %w", err)
	}

	// Send verification email
	if err := s.SendVerificationEmail(ctx, newUser.ID); err != nil {
		// Log error but don't fail user creation
		s.logger.WithFields(logrus.Fields{
			"user_id": newUser.ID,
			"email":   newUser.Email,
		}).WithError(err).Warn("failed to send verification email")
	}

	return newUser, nil
}

// CreateUserInTenant creates a user in a specific tenant with tenant validation (for super admin operations)
func (s *UserService) CreateUserInTenant(ctx context.Context, req *user.CreateUserRequest, tenantID uuid.UUID) (*user.User, error) {
	// Validate tenant exists and is active
	tenantRecord, err := s.tenantRepo.GetByID(ctx, tenantID)
	if err != nil {
		return nil, fmt.Errorf("tenant not found: %w", err)
	}
	if tenantRecord.Status != tenant.TenantStatusActive {
		return nil, fmt.Errorf("tenant is not active")
	}

	// Enforce tenant user limit if configured
	if tenantRecord.Settings.Limits.MaxUsers > 0 {
		currentCount, err := s.repo.Count(ctx, tenantRecord.ID)
		if err == nil && currentCount >= tenantRecord.Settings.Limits.MaxUsers {
			return nil, fmt.Errorf("tenant user limit (%d) reached", tenantRecord.Settings.Limits.MaxUsers)
		}
	}

	// Validate email uniqueness
	if existingUser, err := s.repo.GetByEmail(ctx, req.Email); err == nil && existingUser != nil {
		return nil, fmt.Errorf("email '%s' is already taken", req.Email)
	}

	// Hash password
	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
	if err != nil {
		return nil, fmt.Errorf("failed to hash password: %w", err)
	}

	// Create user entity
	newUser := &user.User{
		ID:            uuid.New(),
		Email:         req.Email,
		PasswordHash:  string(hashedPassword),
		FirstName:     req.FirstName,
		LastName:      req.LastName,
		Role:          req.Role,
		TenantID:      tenantRecord.ID, // Use verified tenant ID
		IsActive:      true,
		EmailVerified: false,
		CreatedAt:     time.Now(),
		UpdatedAt:     time.Now(),
	}

	// Save to repository
	if err := s.repo.Create(ctx, newUser); err != nil {
		return nil, fmt.Errorf("failed to create user: %w", err)
	}

	// Send verification email
	if err := s.SendVerificationEmail(ctx, newUser.ID); err != nil {
		// Log error but don't fail user creation
		s.logger.WithFields(logrus.Fields{
			"user_id": newUser.ID,
			"email":   newUser.Email,
		}).WithError(err).Warn("failed to send verification email")
	}

	return newUser, nil
}

func (s *UserService) GetUser(ctx context.Context, id uuid.UUID) (*user.User, error) {
	return s.repo.GetByID(ctx, id)
}

func (s *UserService) GetUserByEmail(ctx context.Context, email string) (*user.User, error) {
	return s.repo.GetByEmail(ctx, email)
}

func (s *UserService) UpdateUser(ctx context.Context, id uuid.UUID, req *user.UpdateUserRequest) (*user.User, error) {
	existingUser, err := s.repo.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}

	// Track if user is being deactivated for token cleanup
	wasActive := existingUser.IsActive

	// Update fields if provided
	if req.FirstName != nil {
		existingUser.FirstName = *req.FirstName
	}
	if req.LastName != nil {
		existingUser.LastName = *req.LastName
	}
	if req.Role != nil {
		existingUser.Role = *req.Role
	}
	if req.IsActive != nil {
		existingUser.IsActive = *req.IsActive
	}
	existingUser.UpdatedAt = time.Now()

	if err := s.repo.Update(ctx, existingUser); err != nil {
		return nil, fmt.Errorf("failed to update user: %w", err)
	}

	// If user was deactivated, invalidate all their tokens for security
	if wasActive && req.IsActive != nil && !*req.IsActive && s.tokenRepo != nil {
		if err := s.tokenRepo.DeleteUserTokens(ctx, id); err != nil {
			// Log error but don't fail the user update
			s.logger.WithFields(logrus.Fields{"user_id": existingUser.ID}).WithError(err).Warn("failed to delete user tokens after account deactivation")
		}
	}

	return existingUser, nil
}

func (s *UserService) DeleteUser(ctx context.Context, id uuid.UUID) error {
	// Delete all authentication tokens for this user first (for security)
	if s.tokenRepo != nil {
		if err := s.tokenRepo.DeleteUserTokens(ctx, id); err != nil {
			// Log error but don't fail the deletion - we still want to delete the user
			s.logger.WithFields(logrus.Fields{"user_id": id}).WithError(err).Warn("failed to delete user tokens during user deletion")
		}
	}

	// Delete the user
	return s.repo.Delete(ctx, id)
}

func (s *UserService) ListUsers(ctx context.Context, tenantID uuid.UUID, limit, offset int) ([]*user.User, int, error) {
	users, err := s.repo.List(ctx, tenantID, limit, offset)
	if err != nil {
		return nil, 0, err
	}

	count, err := s.repo.Count(ctx, tenantID)
	if err != nil {
		return nil, 0, err
	}

	return users, count, nil
}

func (s *UserService) VerifyPassword(ctx context.Context, userID uuid.UUID, password string) error {
	user, err := s.repo.GetByID(ctx, userID)
	if err != nil {
		return err
	}

	return bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(password))
}

func (s *UserService) ChangePassword(ctx context.Context, userID uuid.UUID, oldPassword, newPassword string) error {
	// Verify old password first
	if err := s.VerifyPassword(ctx, userID, oldPassword); err != nil {
		return fmt.Errorf("invalid old password: %w", err)
	}

	// Hash new password
	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(newPassword), bcrypt.DefaultCost)
	if err != nil {
		return fmt.Errorf("failed to hash password: %w", err)
	}

	// Update user
	user, err := s.repo.GetByID(ctx, userID)
	if err != nil {
		return err
	}

	user.PasswordHash = string(hashedPassword)
	if err := s.repo.Update(ctx, user); err != nil {
		return err
	}

	// Invalidate all existing authentication tokens for security
	// This forces the user to re-authenticate with their new password
	if s.tokenRepo != nil {
		if err := s.tokenRepo.DeleteUserTokens(ctx, userID); err != nil {
			// Log error but don't fail the password change
			s.logger.WithFields(logrus.Fields{"user_id": userID}).WithError(err).Warn("failed to delete user tokens after password change")
		}
	}

	return nil
}

// generateVerificationToken generates a secure random token for email verification
func (s *UserService) generateVerificationToken() (string, error) {
	bytes := make([]byte, 32)
	if _, err := rand.Read(bytes); err != nil {
		return "", err
	}
	return hex.EncodeToString(bytes), nil
}

// SendVerificationEmail creates a verification token and sends verification email
func (s *UserService) SendVerificationEmail(ctx context.Context, userID uuid.UUID) error {
	usr, err := s.repo.GetByID(ctx, userID)
	if err != nil {
		return fmt.Errorf("failed to get user: %w", err)
	}

	if usr.EmailVerified {
		return fmt.Errorf("email already verified")
	}

	// Generate verification token
	tokenStr, err := s.generateVerificationToken()
	if err != nil {
		return fmt.Errorf("failed to generate token: %w", err)
	}

	// Create verification token record
	token := &user.EmailToken{
		ID:        uuid.New(),
		UserID:    userID,
		Token:     tokenStr,
		Type:      user.EmailTokenTypeVerification,
		NewEmail:  nil,                            // Not needed for verification
		ExpiresAt: time.Now().Add(24 * time.Hour), // 24 hours expiry
		CreatedAt: time.Now(),
	}

	if err := s.emailTokenRepo.Create(ctx, token); err != nil {
		return fmt.Errorf("failed to save verification token: %w", err)
	}

	// Send verification email
	userName := fmt.Sprintf("%s %s", usr.FirstName, usr.LastName)
	if err := s.emailService.SendVerificationEmail(ctx, usr.Email, tokenStr, userName); err != nil {
		return fmt.Errorf("failed to send verification email: %w", err)
	}

	return nil
}

// VerifyEmail verifies the user's email using the provided token
func (s *UserService) VerifyEmail(ctx context.Context, tokenStr string) (*user.User, error) {
	// Get email token
	token, err := s.emailTokenRepo.Get(ctx, tokenStr)
	if err != nil {
		return nil, fmt.Errorf("invalid verification token")
	}

	// Check if token is valid and is a verification token
	if !token.IsValid() || !token.IsVerificationToken() {
		return nil, fmt.Errorf("verification token has expired, already been used, or is not a verification token")
	}

	// Get user
	user, err := s.repo.GetByID(ctx, token.UserID)
	if err != nil {
		return nil, fmt.Errorf("failed to get user: %w", err)
	}

	// Mark token as used
	if err := s.emailTokenRepo.MarkAsUsed(ctx, token.ID); err != nil {
		return nil, fmt.Errorf("failed to mark token as used: %w", err)
	}

	// Mark user email as verified
	user.EmailVerified = true
	user.UpdatedAt = time.Now()
	if err := s.repo.Update(ctx, user); err != nil {
		return nil, fmt.Errorf("failed to update user: %w", err)
	}

	return user, nil
}

// ResendVerificationEmail resends verification email for the user
func (s *UserService) ResendVerificationEmail(ctx context.Context, email string) error {
	user, err := s.repo.GetByEmail(ctx, email)
	if err != nil {
		return fmt.Errorf("user not found")
	}

	if user.EmailVerified {
		return fmt.Errorf("email already verified")
	}

	return s.SendVerificationEmail(ctx, user.ID)
}

// RequestEmailUpdate initiates an email update process
func (s *UserService) RequestEmailUpdate(ctx context.Context, userID uuid.UUID, req *user.UpdateEmailRequest) error {
	// Get current user
	currentUser, err := s.repo.GetByID(ctx, userID)
	if err != nil {
		return fmt.Errorf("failed to get user: %w", err)
	}

	// Verify password for security
	if err := bcrypt.CompareHashAndPassword([]byte(currentUser.PasswordHash), []byte(req.Password)); err != nil {
		return fmt.Errorf("invalid password")
	}

	// Check if new email is already in use
	existingUser, err := s.repo.GetByEmail(ctx, req.NewEmail)
	if err == nil && existingUser.ID != userID {
		return fmt.Errorf("email already in use")
	}

	// Check if email is the same as current
	if currentUser.Email == req.NewEmail {
		return fmt.Errorf("new email is the same as current email")
	}

	// Generate verification token
	tokenStr, err := s.generateVerificationToken()
	if err != nil {
		return fmt.Errorf("failed to generate token: %w", err)
	}

	// Create email update token record
	token := &user.EmailToken{
		ID:        uuid.New(),
		UserID:    userID,
		Token:     tokenStr,
		Type:      user.EmailTokenTypeEmailUpdate,
		NewEmail:  &req.NewEmail,                  // Store the new email
		ExpiresAt: time.Now().Add(24 * time.Hour), // 24 hours expiry
		CreatedAt: time.Now(),
	}

	if err := s.emailTokenRepo.Create(ctx, token); err != nil {
		return fmt.Errorf("failed to save email update token: %w", err)
	}

	// Send confirmation email to the NEW email address
	userName := fmt.Sprintf("%s %s", currentUser.FirstName, currentUser.LastName)
	if err := s.emailService.SendEmailUpdateConfirmation(ctx, req.NewEmail, tokenStr, userName); err != nil {
		return fmt.Errorf("failed to send email update confirmation: %w", err)
	}

	return nil
}

// ConfirmEmailUpdate confirms the email update using the provided token
func (s *UserService) ConfirmEmailUpdate(ctx context.Context, tokenStr string) (*user.User, error) {
	// Get email token
	token, err := s.emailTokenRepo.Get(ctx, tokenStr)
	if err != nil {
		return nil, fmt.Errorf("invalid email update token")
	}

	// Check if token is valid and is an email update token
	if !token.IsValid() || !token.IsEmailUpdateToken() {
		return nil, fmt.Errorf("email update token has expired, already been used, or is not an email update token")
	}

	// Ensure NewEmail is set for email update tokens
	if token.NewEmail == nil {
		return nil, fmt.Errorf("invalid email update token: missing new email")
	}

	// Get user
	user, err := s.repo.GetByID(ctx, token.UserID)
	if err != nil {
		return nil, fmt.Errorf("failed to get user: %w", err)
	}

	// Check if new email is still available (double-check for race conditions)
	existingUser, err := s.repo.GetByEmail(ctx, *token.NewEmail)
	if err == nil && existingUser.ID != user.ID {
		return nil, fmt.Errorf("email address is no longer available")
	}

	// Mark token as used
	if err := s.emailTokenRepo.MarkAsUsed(ctx, token.ID); err != nil {
		return nil, fmt.Errorf("failed to mark token as used: %w", err)
	}

	// Update user email and mark as verified (since they confirmed ownership)
	user.Email = *token.NewEmail
	user.EmailVerified = true // Email is verified since they confirmed ownership
	user.UpdatedAt = time.Now()
	if err := s.repo.Update(ctx, user); err != nil {
		return nil, fmt.Errorf("failed to update user email: %w", err)
	}

	return user, nil
}
