package utils

import (
	"errors"
	"regexp"
	"unicode"
)

var (
	ErrPasswordTooShort      = errors.New("password must be at least 12 characters long")
	ErrPasswordNoUppercase   = errors.New("password must contain at least one uppercase letter")
	ErrPasswordNoLowercase   = errors.New("password must contain at least one lowercase letter")
	ErrPasswordNoDigit       = errors.New("password must contain at least one digit")
	ErrPasswordNoSpecialChar = errors.New("password must contain at least one special character")
)

var specialCharRegex = regexp.MustCompile(`[!@#$%^&*(),.?":{}|<>\[\]\\/_\-+=~` + "`" + `';]`)

// ValidatePasswordStrength validates that a password meets security requirements
func ValidatePasswordStrength(password string) error {
	if len(password) < 12 {
		return ErrPasswordTooShort
	}

	var (
		hasUpper bool
		hasLower bool
		hasDigit bool
	)

	for _, char := range password {
		switch {
		case unicode.IsUpper(char):
			hasUpper = true
		case unicode.IsLower(char):
			hasLower = true
		case unicode.IsDigit(char):
			hasDigit = true
		}
	}

	if !hasUpper {
		return ErrPasswordNoUppercase
	}
	if !hasLower {
		return ErrPasswordNoLowercase
	}
	if !hasDigit {
		return ErrPasswordNoDigit
	}
	if !specialCharRegex.MatchString(password) {
		return ErrPasswordNoSpecialChar
	}

	return nil
}
