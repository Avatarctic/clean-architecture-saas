package services

import (
	"context"
	"fmt"
	"time"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/tenant"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/google/uuid"
	"github.com/sirupsen/logrus"
	"golang.org/x/crypto/bcrypt"
)

type TenantService struct {
	repo         ports.TenantRepository
	userRepo     ports.UserRepository
	userService  ports.UserService
	emailService ports.EmailService
	logger       *logrus.Logger
}

func NewTenantService(repo ports.TenantRepository, userRepo ports.UserRepository, userService ports.UserService, emailService ports.EmailService, logger *logrus.Logger) ports.TenantService {
	return &TenantService{
		repo:         repo,
		userRepo:     userRepo,
		userService:  userService,
		emailService: emailService,
		logger:       logger,
	}
}

func (s *TenantService) CreateTenant(ctx context.Context, req *tenant.CreateTenantRequest) (*tenant.Tenant, error) {
	// Validate slug uniqueness
	if existingTenant, err := s.repo.GetBySlug(ctx, req.Slug); err == nil && existingTenant != nil {
		return nil, fmt.Errorf("slug '%s' is already taken", req.Slug)
	}

	// Validate admin email uniqueness
	if existingUser, err := s.userRepo.GetByEmail(ctx, req.AdminUser.Email); err == nil && existingUser != nil {
		return nil, fmt.Errorf("admin email '%s' is already taken", req.AdminUser.Email)
	}

	// Create tenant entity
	newTenant := &tenant.Tenant{
		ID:        uuid.New(),
		Name:      req.Name,
		Slug:      req.Slug,
		Domain:    req.Domain,
		Plan:      req.Plan,
		Status:    tenant.TenantStatusActive,
		Settings:  req.Settings,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	// Hash admin password
	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(req.AdminUser.Password), bcrypt.DefaultCost)
	if err != nil {
		return nil, fmt.Errorf("failed to hash admin password: %w", err)
	}

	// Create initial admin user
	adminUser := &user.User{
		ID:            uuid.New(),
		Email:         req.AdminUser.Email,
		PasswordHash:  string(hashedPassword),
		FirstName:     req.AdminUser.FirstName,
		LastName:      req.AdminUser.LastName,
		Role:          user.RoleAdmin, // Initial user is always admin
		TenantID:      newTenant.ID,
		IsActive:      true,
		EmailVerified: false, // Will need verification
		CreatedAt:     time.Now(),
		UpdatedAt:     time.Now(),
	}

	// Save tenant first
	if err := s.repo.Create(ctx, newTenant); err != nil {
		return nil, fmt.Errorf("failed to create tenant: %w", err)
	}

	// Save admin user
	if err := s.userRepo.Create(ctx, adminUser); err != nil {
		// If user creation fails, attempt cleanup and log any cleanup error
		if derr := s.repo.Delete(ctx, newTenant.ID); derr != nil {
			if s.logger != nil {
				s.logger.WithFields(logrus.Fields{"tenant_id": newTenant.ID}).WithError(derr).Warn("failed to clean up tenant after user creation error")
			}
		}
		return nil, fmt.Errorf("failed to create admin user: %w", err)
	}

	// Send verification email to admin
	if err := s.userService.SendVerificationEmail(ctx, adminUser.ID); err != nil {
		// Log error but don't fail tenant creation
		s.logger.WithFields(logrus.Fields{"tenant_id": newTenant.ID, "admin_user_id": adminUser.ID}).WithError(err).Warn("failed to send admin verification email")
	}

	return newTenant, nil
}

func (s *TenantService) GetTenant(ctx context.Context, id uuid.UUID) (*tenant.Tenant, error) {
	return s.repo.GetByID(ctx, id)
}

func (s *TenantService) GetTenantBySlug(ctx context.Context, slug string) (*tenant.Tenant, error) {
	return s.repo.GetBySlug(ctx, slug)
}

// GetActiveTenant returns a tenant only if it's in active status
func (s *TenantService) GetActiveTenant(ctx context.Context, id uuid.UUID) (*tenant.Tenant, error) {
	t, err := s.repo.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}
	if t.Status != tenant.TenantStatusActive {
		return nil, fmt.Errorf("tenant is not active")
	}
	return t, nil
}

func (s *TenantService) UpdateTenant(ctx context.Context, id uuid.UUID, req *tenant.UpdateTenantRequest) (*tenant.Tenant, error) {
	existingTenant, err := s.repo.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}

	// Update fields if provided
	if req.Name != nil {
		existingTenant.Name = *req.Name
	}
	if req.Slug != nil {
		// Validate slug uniqueness if it's being changed
		if *req.Slug != existingTenant.Slug {
			if existing, err := s.repo.GetBySlug(ctx, *req.Slug); err == nil && existing != nil && existing.ID != id {
				return nil, fmt.Errorf("slug '%s' is already taken", *req.Slug)
			}
		}
		existingTenant.Slug = *req.Slug
	}
	if req.Domain != nil {
		existingTenant.Domain = *req.Domain
	}
	if req.Plan != nil {
		existingTenant.Plan = *req.Plan
	}
	if req.Settings != nil {
		existingTenant.Settings = *req.Settings
	}

	// Update timestamp
	existingTenant.UpdatedAt = time.Now()

	if err := s.repo.Update(ctx, existingTenant); err != nil {
		return nil, fmt.Errorf("failed to update tenant: %w", err)
	}

	return existingTenant, nil
}

func (s *TenantService) DeleteTenant(ctx context.Context, id uuid.UUID) error {
	return s.repo.Delete(ctx, id)
}

func (s *TenantService) ListTenants(ctx context.Context, limit, offset int) ([]*tenant.Tenant, int, error) {
	tenants, err := s.repo.List(ctx, limit, offset)
	if err != nil {
		return nil, 0, err
	}

	count, err := s.repo.Count(ctx)
	if err != nil {
		return nil, 0, err
	}

	return tenants, count, nil
}
