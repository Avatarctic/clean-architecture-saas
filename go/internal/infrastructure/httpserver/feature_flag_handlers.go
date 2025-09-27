package httpserver

import (
	"net/http"
	"strconv"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/feature"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/httpserver/helpers"
	"github.com/google/uuid"
	"github.com/labstack/echo/v4"
)

func (s *Server) createFeatureFlag(c echo.Context) error {
	var req feature.CreateFeatureFlagRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid request body")
	}
	if err := c.Validate(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}
	flag, err := s.featureSvc.CreateFeatureFlag(c.Request().Context(), &req)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, err.Error())
	}
	return c.JSON(http.StatusCreated, flag)
}

func (s *Server) updateFeatureFlag(c echo.Context) error {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid feature flag ID")
	}
	var req feature.UpdateFeatureFlagRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid request body")
	}
	if err := c.Validate(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}
	flag, err := s.featureSvc.UpdateFeatureFlag(c.Request().Context(), id, &req)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, err.Error())
	}
	return c.JSON(http.StatusOK, flag)
}

func (s *Server) deleteFeatureFlag(c echo.Context) error {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid feature flag ID")
	}
	if err := s.featureSvc.DeleteFeatureFlag(c.Request().Context(), id); err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, err.Error())
	}
	return c.NoContent(http.StatusNoContent)
}

func (s *Server) listFeatureFlags(c echo.Context) error {
	limit := 20
	offset := 0
	if l := c.QueryParam("limit"); l != "" {
		if v, err := strconv.Atoi(l); err == nil {
			limit = v
		}
	}
	if o := c.QueryParam("offset"); o != "" {
		if v, err := strconv.Atoi(o); err == nil {
			offset = v
		}
	}
	flags, total, err := s.featureSvc.ListFeatureFlags(c.Request().Context(), limit, offset)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, err.Error())
	}
	return c.JSON(http.StatusOK, map[string]interface{}{"feature_flags": flags, "total": total, "limit": limit, "offset": offset})
}

func (s *Server) evaluateFeatureFlag(c echo.Context) error {
	var req struct {
		Key         string         `json:"key" validate:"required"`
		Custom      map[string]any `json:"custom,omitempty"`
		ReturnValue bool           `json:"return_value"`
	}
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "invalid request body")
	}
	if err := c.Validate(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}
	userID, err := helpers.GetUserIDFromContext(c)
	if err != nil {
		return err
	}
	tenantID, err := helpers.GetTenantIDFromContext(c)
	if err != nil {
		return err
	}
	userRole, err := helpers.GetUserRoleFromContext(c)
	if err != nil {
		return err
	}
	tenant, err := helpers.GetTenantFromContext(c)
	if err != nil {
		return err
	}
	context := &feature.FeatureFlagContext{
		UserID:   userID,
		TenantID: tenantID,
		Role:     string(userRole),
		Plan:     string(tenant.Plan),
		Custom:   req.Custom,
	}
	if req.ReturnValue {
		val, err := s.featureSvc.GetFeatureValue(c.Request().Context(), req.Key, context)
		if err != nil {
			return echo.NewHTTPError(http.StatusInternalServerError, err.Error())
		}
		return c.JSON(http.StatusOK, map[string]interface{}{"value": val})
	} else {
		enabled, err := s.featureSvc.IsFeatureEnabled(c.Request().Context(), req.Key, context)
		if err != nil {
			return echo.NewHTTPError(http.StatusInternalServerError, err.Error())
		}
		return c.JSON(http.StatusOK, map[string]interface{}{"enabled": enabled})
	}
}
