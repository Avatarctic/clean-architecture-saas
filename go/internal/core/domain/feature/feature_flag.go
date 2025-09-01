package feature

import (
	"slices"
	"strings"
	"time"

	"github.com/google/uuid"
)

type FeatureFlag struct {
	ID           uuid.UUID          `json:"id" db:"id"`
	Name         string             `json:"name" db:"name"`
	Key          string             `json:"key" db:"key"`
	Description  string             `json:"description" db:"description"`
	Type         FeatureFlagType    `json:"type" db:"type"`
	IsEnabled    bool               `json:"is_enabled" db:"is_enabled"`
	EnabledValue any                `json:"enabled_value" db:"enabled_value"` // Value for users in rollout
	DefaultValue any                `json:"default_value" db:"default_value"` // Value for users outside rollout
	Rules        []FeatureFlagRule  `json:"rules" db:"rules"`
	Rollout      FeatureFlagRollout `json:"rollout" db:"rollout"`
	CreatedAt    time.Time          `json:"created_at" db:"created_at"`
	UpdatedAt    time.Time          `json:"updated_at" db:"updated_at"`
}

type FeatureFlagType string

const (
	FlagTypeBoolean FeatureFlagType = "boolean"
	FlagTypeString  FeatureFlagType = "string"
	FlagTypeNumber  FeatureFlagType = "number"
	FlagTypeJSON    FeatureFlagType = "json"
)

func (flag *FeatureFlag) Evaluate(context *FeatureFlagContext) (any, bool) {
	if !flag.IsEnabled {
		return flag.DefaultValue, false
	}

	// First, check if any rule matches
	for _, rule := range flag.Rules {
		if rule.Evaluate(context) {
			return rule.Value, true
		}
	}

	// No rules matched, check flag-level rollout
	if isInRollout(context.UserID, flag.Rollout.Percentage) {
		return flag.EnabledValue, true
	}

	// Not in rollout, return default
	return flag.DefaultValue, false
}

type FeatureFlagRule struct {
	ID         uuid.UUID              `json:"id"`
	Conditions []FeatureFlagCondition `json:"conditions"`
	Value      any                    `json:"value"`
	Rollout    int                    `json:"rollout"` // percentage 0-100
}

func (rule *FeatureFlagRule) Evaluate(context *FeatureFlagContext) bool {
	// Check if ALL conditions match
	for _, condition := range rule.Conditions {
		if !condition.Evaluate(context) {
			return false // Rule doesn't apply
		}
	}

	// Check rollout percentage
	return isInRollout(context.UserID, rule.Rollout)
}

type FeatureFlagCondition struct {
	Attribute string `json:"attribute"` // e.g., "tenant_id", "user_role", "plan"
	Operator  string `json:"operator"`  // e.g., "equals", "in", "contains"
	Value     any    `json:"value"`
}

// isInRollout determines if a user is included in the rollout percentage based on their user ID.
func isInRollout(userID uuid.UUID, rollout int) bool {
	if rollout >= 100 {
		return true
	}
	if rollout <= 0 {
		return false
	}
	// Use the first 4 bytes of the UUID as a deterministic seed
	bytes := userID[:4]
	hash := int(bytes[0])<<24 | int(bytes[1])<<16 | int(bytes[2])<<8 | int(bytes[3])
	percent := hash % 100
	return percent < rollout
}

func (a *FeatureFlagCondition) Evaluate(context *FeatureFlagContext) bool {
	switch a.Operator {
	case "equals":
		return a.Value == context.Custom[a.Attribute]
	case "in":
		return contains(a.Value.([]any), context.Custom[a.Attribute])
	case "contains":
		return strings.Contains(context.Custom[a.Attribute].(string), a.Value.(string))
	default:
		return false
	}
}

// contains checks if val is present in the slice arr.
func contains(arr []any, val any) bool {
	return slices.Contains(arr, val)
}

type FeatureFlagRollout struct {
	Percentage int    `json:"percentage"` // 0-100
	Strategy   string `json:"strategy"`   // "random", "user_id", "tenant_id"
}

type FeatureFlagContext struct {
	UserID   uuid.UUID      `json:"user_id"`
	TenantID uuid.UUID      `json:"tenant_id"`
	Role     string         `json:"role"`
	Plan     string         `json:"plan"`
	Custom   map[string]any `json:"custom"`
}

// CreateFeatureFlagRequest represents the request to create a new feature flag
type CreateFeatureFlagRequest struct {
	Name         string             `json:"name" validate:"required"`
	Key          string             `json:"key" validate:"required"`
	Description  string             `json:"description"`
	Type         FeatureFlagType    `json:"type" validate:"required"`
	IsEnabled    bool               `json:"is_enabled"`
	EnabledValue any                `json:"enabled_value"`
	DefaultValue any                `json:"default_value"`
	Rules        []FeatureFlagRule  `json:"rules"`
	Rollout      FeatureFlagRollout `json:"rollout"`
}

// UpdateFeatureFlagRequest represents the request to update a feature flag
type UpdateFeatureFlagRequest struct {
	Name         *string             `json:"name,omitempty"`
	Key          *string             `json:"key,omitempty"`
	Description  *string             `json:"description,omitempty"`
	Type         *FeatureFlagType    `json:"type,omitempty"`
	IsEnabled    *bool               `json:"is_enabled,omitempty"`
	EnabledValue *any                `json:"enabled_value,omitempty"`
	DefaultValue *any                `json:"default_value,omitempty"`
	Rules        *[]FeatureFlagRule  `json:"rules,omitempty"`
	Rollout      *FeatureFlagRollout `json:"rollout,omitempty"`
}
