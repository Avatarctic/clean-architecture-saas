package email

import (
	"bytes"
	"context"
	"fmt"
	"html/template"
	"path/filepath"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/sendgrid/sendgrid-go"
	"github.com/sendgrid/sendgrid-go/helpers/mail"
	"github.com/sirupsen/logrus"
)

// EmailConfig holds email service configuration
type EmailConfig struct {
	SendGridAPIKey string
	FromEmail      string
	FromName       string
	CompanyName    string
	BaseURL        string
}

// EmailService implements the EmailService interface
type EmailService struct {
	config    *EmailConfig
	logger    *logrus.Logger
	client    *sendgrid.Client
	templates map[string]*template.Template
}

// NewEmailService creates a new email service instance
func NewEmailService(config *EmailConfig, logger *logrus.Logger) (ports.EmailService, error) {
	client := sendgrid.NewSendClient(config.SendGridAPIKey)

	// Load email templates
	templates, err := loadTemplates()
	if err != nil {
		return nil, fmt.Errorf("failed to load email templates: %w", err)
	}

	return &EmailService{
		config:    config,
		logger:    logger,
		client:    client,
		templates: templates,
	}, nil
}

// loadTemplates loads all email templates from the embedded filesystem
func loadTemplates() (map[string]*template.Template, error) {
	templates := make(map[string]*template.Template)

	templateDir := "templates/email"

	templateFiles := []string{
		"verification.html",
		"email_update.html",
	}

	for _, file := range templateFiles {
		name := filepath.Base(file)
		name = name[:len(name)-len(filepath.Ext(name))] // Remove .html extension

		tmpl, err := template.ParseFiles(filepath.Join(templateDir, file))
		if err != nil {
			return nil, fmt.Errorf("failed to parse template %s: %w", file, err)
		}

		templates[name] = tmpl
	}

	return templates, nil
}

// sendEmail sends an email using SendGrid
func (e *EmailService) sendEmail(to, subject, htmlContent string) error {
	from := mail.NewEmail(e.config.FromName, e.config.FromEmail)
	recipient := mail.NewEmail("", to)

	message := mail.NewSingleEmail(from, subject, recipient, "", htmlContent)

	response, err := e.client.Send(message)
	if err != nil {
		e.logger.WithFields(logrus.Fields{
			"to":      to,
			"subject": subject,
			"error":   err,
		}).Error("Failed to send email")
		return fmt.Errorf("failed to send email: %w", err)
	}

	e.logger.WithFields(logrus.Fields{
		"to":          to,
		"subject":     subject,
		"status_code": response.StatusCode,
	}).Info("Email sent successfully")

	return nil
}

// renderTemplate renders an email template with the provided data
func (e *EmailService) renderTemplate(templateName string, data interface{}) (string, error) {
	tmpl, exists := e.templates[templateName]
	if !exists {
		return "", fmt.Errorf("template %s not found", templateName)
	}

	var buf bytes.Buffer
	if err := tmpl.Execute(&buf, data); err != nil {
		return "", fmt.Errorf("failed to execute template %s: %w", templateName, err)
	}

	return buf.String(), nil
}

// VerificationEmailData holds data for email verification template
type VerificationEmailData struct {
	CompanyName     string
	UserName        string
	VerificationURL string
}

// EmailUpdateData holds data for email update confirmation template
type EmailUpdateData struct {
	CompanyName     string
	UserName        string
	NewEmail        string
	ConfirmationURL string
}

// SendVerificationEmail sends an email verification email
func (e *EmailService) SendVerificationEmail(ctx context.Context, email, token, userName string) error {
	data := VerificationEmailData{
		CompanyName:     e.config.CompanyName,
		UserName:        userName,
		VerificationURL: fmt.Sprintf("%s/api/v1/auth/verify-email?token=%s", e.config.BaseURL, token),
	}

	htmlContent, err := e.renderTemplate("verification", data)
	if err != nil {
		return fmt.Errorf("failed to render verification email template: %w", err)
	}

	subject := fmt.Sprintf("Verify Your Email Address - %s", e.config.CompanyName)

	return e.sendEmail(email, subject, htmlContent)
}

// SendEmailUpdateConfirmation sends an email to confirm email address update
func (e *EmailService) SendEmailUpdateConfirmation(ctx context.Context, newEmail, token, userName string) error {
	data := EmailUpdateData{
		CompanyName:     e.config.CompanyName,
		UserName:        userName,
		NewEmail:        newEmail,
		ConfirmationURL: fmt.Sprintf("%s/api/v1/auth/confirm-email-update?token=%s", e.config.BaseURL, token),
	}

	htmlContent, err := e.renderTemplate("email_update", data)
	if err != nil {
		return fmt.Errorf("failed to render email update template: %w", err)
	}

	subject := fmt.Sprintf("Confirm Your New Email Address - %s", e.config.CompanyName)

	return e.sendEmail(newEmail, subject, htmlContent)
}
