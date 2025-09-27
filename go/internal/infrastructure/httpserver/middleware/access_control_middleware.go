package middleware

import (
	"errors"
	"net/http"

	"github.com/google/uuid"
	"github.com/labstack/echo/v4"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/permission"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/httpserver/helpers"
)

type AccessControlMiddleware struct {
	accessControl ports.AccessControlService
	userService   ports.UserService
}

func NewAccessControlMiddleware(accessControl ports.AccessControlService, userService ports.UserService) *AccessControlMiddleware {
	return &AccessControlMiddleware{accessControl: accessControl, userService: userService}
}

func (m *AccessControlMiddleware) RequireUserAction(action ports.AccessAction) echo.MiddlewareFunc {
	return echo.MiddlewareFunc(func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			targetID, actorID, actorTenantID, perms, err := m.prepareRequestContextForAction(c)
			if err != nil {
				return err
			}

			targetUser, err := m.userService.GetUser(c.Request().Context(), targetID)
			if err != nil {
				return echo.NewHTTPError(http.StatusNotFound, "target user not found")
			}
			helpers.SetTargetUser(c, targetUser)

			if err := m.accessControl.CanPerformActionWithTarget(c.Request().Context(), actorID, actorTenantID, perms, targetUser, action); err != nil {
				return m.mapAccessControlError(err)
			}

			return next(c)
		}
	})
}

// prepareRequestContextForAction extracts common request values used by the middleware.
func (m *AccessControlMiddleware) prepareRequestContextForAction(c echo.Context) (uuid.UUID, uuid.UUID, uuid.UUID, []permission.Permission, error) {
	idStr := c.Param("id")
	if idStr == "" {
		return uuid.Nil, uuid.Nil, uuid.Nil, nil, echo.NewHTTPError(http.StatusBadRequest, "missing target user id")
	}
	targetID, err := uuid.Parse(idStr)
	if err != nil {
		return uuid.Nil, uuid.Nil, uuid.Nil, nil, echo.NewHTTPError(http.StatusBadRequest, "invalid target user id")
	}

	actorID, err := helpers.GetUserIDFromContext(c)
	if err != nil {
		return uuid.Nil, uuid.Nil, uuid.Nil, nil, err
	}
	actorTenantID, err := helpers.GetTenantIDFromContext(c)
	if err != nil {
		actorTenantID = uuid.Nil
	}
	perms, err := helpers.GetUserPermissionsFromContext(c)
	if err != nil {
		return uuid.Nil, uuid.Nil, uuid.Nil, nil, err
	}
	return targetID, actorID, actorTenantID, perms, nil
}

// mapAccessControlError converts AccessControlError into appropriate HTTP errors.
func (m *AccessControlMiddleware) mapAccessControlError(err error) error {
	var ace ports.AccessControlError
	if errors.As(err, &ace) {
		switch ace.Code() {
		case ports.ACCodeNotFound:
			return echo.NewHTTPError(http.StatusNotFound, ace.Message())
		case ports.ACCodeForbidden:
			return echo.NewHTTPError(http.StatusForbidden, ace.Message())
		default:
			return echo.NewHTTPError(http.StatusForbidden, ace.Message())
		}
	}
	return echo.NewHTTPError(http.StatusForbidden, err.Error())
}

func (m *AccessControlMiddleware) PreloadTargetUser() echo.MiddlewareFunc {
	return echo.MiddlewareFunc(func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			idStr := c.Param("id")
			if idStr == "" {
				return echo.NewHTTPError(http.StatusBadRequest, "missing target user id")
			}
			targetID, err := uuid.Parse(idStr)
			if err != nil {
				return echo.NewHTTPError(http.StatusBadRequest, "invalid target user id")
			}

			targetUser, err := m.userService.GetUser(c.Request().Context(), targetID)
			if err != nil {
				return echo.NewHTTPError(http.StatusNotFound, "target user not found")
			}

			helpers.SetTargetUser(c, targetUser)
			return next(c)
		}
	})
}
