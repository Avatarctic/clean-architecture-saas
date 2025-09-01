package ports

import (
	"context"
)

// EmailService defines the interface for email operations
type EmailService interface {
	SendVerificationEmail(ctx context.Context, email, token, userName string) error
	SendEmailUpdateConfirmation(ctx context.Context, newEmail, token, userName string) error
}

// EmailTemplate represents email template data
type EmailTemplate struct {
	Subject string
	Body    string
	IsHTML  bool
}
