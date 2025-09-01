package ports

import (
	"context"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/google/uuid"
)

// EmailTokenRepository handles ephemeral email tokens (verification / update).
// Implementations may use Redis or another ephemeral store.
type EmailTokenRepository interface {
	Create(ctx context.Context, token *user.EmailToken) error
	Get(ctx context.Context, token string) (*user.EmailToken, error)
	MarkAsUsed(ctx context.Context, tokenID uuid.UUID) error
}
