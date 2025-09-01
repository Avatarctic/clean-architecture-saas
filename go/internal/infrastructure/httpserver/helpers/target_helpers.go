package helpers

import (
	"net/http"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/labstack/echo/v4"
)

// GetTargetUserFromContext returns the preloaded target user set by access control middleware
func GetTargetUserFromContext(c echo.Context) (*user.User, error) {
	tu, ok := GetTargetUserRaw(c)
	if !ok || tu == nil {
		return nil, echo.NewHTTPError(http.StatusInternalServerError, "target user not available in context")
	}
	return tu, nil
}
