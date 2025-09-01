package audit

import (
	"time"

	"github.com/google/uuid"
)

type AuditLog struct {
	ID         uuid.UUID  `json:"id" db:"id"`
	TenantID   uuid.UUID  `json:"tenant_id" db:"tenant_id"`
	UserID     *uuid.UUID `json:"user_id" db:"user_id"`
	Action     string     `json:"action" db:"action"`
	Resource   string     `json:"resource" db:"resource"`
	ResourceID *uuid.UUID `json:"resource_id" db:"resource_id"`
	Details    any        `json:"details" db:"details"`
	IPAddress  string     `json:"ip_address" db:"ip_address"`
	UserAgent  string     `json:"user_agent" db:"user_agent"`
	Timestamp  time.Time  `json:"timestamp" db:"timestamp"`
}

type AuditAction string

const (
	ActionCreate AuditAction = "create"
	ActionRead   AuditAction = "read"
	ActionUpdate AuditAction = "update"
	ActionDelete AuditAction = "delete"
	ActionLogin  AuditAction = "login"
	ActionLogout AuditAction = "logout"
)

type AuditResource string

const (
	ResourceUser         AuditResource = "user"
	ResourceTenant       AuditResource = "tenant"
	ResourcePermission   AuditResource = "permission"
	ResourceFeatureFlag  AuditResource = "feature_flag"
	ResourceBilling      AuditResource = "billing"
	ResourceSubscription AuditResource = "subscription"
)

// CreateAuditLogRequest represents the request to create an audit log entry
type CreateAuditLogRequest struct {
	TenantID   uuid.UUID     `json:"tenant_id"`
	UserID     *uuid.UUID    `json:"user_id,omitempty"`
	Action     AuditAction   `json:"action"`
	Resource   AuditResource `json:"resource"`
	ResourceID *uuid.UUID    `json:"resource_id,omitempty"`
	Details    any           `json:"details,omitempty"`
	IPAddress  string        `json:"ip_address"`
	UserAgent  string        `json:"user_agent"`
}

// AuditLogFilter represents filters for querying audit logs
type AuditLogFilter struct {
	TenantID   *uuid.UUID     `json:"tenant_id,omitempty"`
	UserID     *uuid.UUID     `json:"user_id,omitempty"`
	Action     *AuditAction   `json:"action,omitempty"`
	Resource   *AuditResource `json:"resource,omitempty"`
	ResourceID *uuid.UUID     `json:"resource_id,omitempty"`
	StartTime  *time.Time     `json:"start_time,omitempty"`
	EndTime    *time.Time     `json:"end_time,omitempty"`
	Limit      int            `json:"limit"`
	Offset     int            `json:"offset"`
}
