package repositories

import (
	"context"
	"database/sql"
	"encoding/json"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/sirupsen/logrus"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/audit"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/avatarctic/clean-architecture-saas/go/internal/infrastructure/db"
)

type auditRepository struct {
	db     *db.Database
	logger *logrus.Logger
}

// NewAuditRepository creates a new instance of AuditRepository
func NewAuditRepository(database *db.Database, logger *logrus.Logger) ports.AuditRepository {
	return &auditRepository{
		db:     database,
		logger: logger,
	}
}

// Create inserts a new audit log entry into the database
func (r *auditRepository) Create(ctx context.Context, log *audit.AuditLog) error {
	// Generate ID if not provided
	if log.ID == uuid.Nil {
		log.ID = uuid.New()
	}

	// Set timestamp if not provided
	if log.Timestamp.IsZero() {
		log.Timestamp = time.Now()
	}

	// Convert details to JSON if not nil
	var detailsJSON []byte
	var err error
	if log.Details != nil {
		detailsJSON, err = json.Marshal(log.Details)
		if err != nil {
			return err
		}
	}

	query := `
		INSERT INTO audit_logs (
			id, tenant_id, user_id, action, resource, resource_id, 
			details, ip_address, user_agent, timestamp
		) VALUES (
			$1, $2, $3, $4, $5, $6, $7, $8, $9, $10
		)`

	_, err = r.db.DB.ExecContext(ctx, query,
		log.ID,
		log.TenantID,
		log.UserID,
		log.Action,
		log.Resource,
		log.ResourceID,
		detailsJSON,
		log.IPAddress,
		log.UserAgent,
		log.Timestamp,
	)
	if err != nil {
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"tenant_id": log.TenantID, "user_id": log.UserID, "action": log.Action}).WithError(err).Error("db: failed to insert audit log")
		}
		return err
	}
	if r.logger != nil {
		r.logger.WithFields(logrus.Fields{"tenant_id": log.TenantID, "user_id": log.UserID, "action": log.Action, "resource_id": log.ResourceID}).Debug("db: audit log inserted")
	}
	return nil
}

// List retrieves audit logs based on the provided filter
func (r *auditRepository) List(ctx context.Context, filter *audit.AuditLogFilter) ([]*audit.AuditLog, error) {
	query, args := r.buildListQuery(filter, false)
	if r.logger != nil {
		r.logger.WithFields(logrus.Fields{"query": query, "args": args}).Debug("db: executing audit list query")
	}
	rows, err := r.db.DB.QueryContext(ctx, query, args...)
	if err != nil {
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"query": query}).WithError(err).Error("db: failed to execute audit list query")
		}
		return nil, err
	}
	defer rows.Close()

	var logs []*audit.AuditLog
	for rows.Next() {
		log := &audit.AuditLog{}
		var detailsJSON sql.NullString

		err := rows.Scan(
			&log.ID,
			&log.TenantID,
			&log.UserID,
			&log.Action,
			&log.Resource,
			&log.ResourceID,
			&detailsJSON,
			&log.IPAddress,
			&log.UserAgent,
			&log.Timestamp,
		)
		if err != nil {
			return nil, err
		}

		// Parse details JSON if present
		if detailsJSON.Valid && detailsJSON.String != "" {
			var details interface{}
			if err := json.Unmarshal([]byte(detailsJSON.String), &details); err == nil {
				log.Details = details
			}
		}

		logs = append(logs, log)
	}

	if err := rows.Err(); err != nil {
		if r.logger != nil {
			r.logger.WithError(err).Error("db: error iterating audit list rows")
		}
		return nil, err
	}

	return logs, nil
}

// Count returns the total number of audit logs matching the filter
func (r *auditRepository) Count(ctx context.Context, filter *audit.AuditLogFilter) (int, error) {
	query, args := r.buildListQuery(filter, true)

	var count int
	if r.logger != nil {
		r.logger.WithFields(logrus.Fields{"query": query, "args": args}).Debug("db: executing audit count query")
	}
	err := r.db.DB.GetContext(ctx, &count, query, args...)
	if err != nil {
		if r.logger != nil {
			r.logger.WithFields(logrus.Fields{"query": query}).WithError(err).Error("db: failed to execute audit count query")
		}
		return 0, err
	}
	return count, nil
}

// buildListQuery constructs the SQL query and arguments for listing/counting audit logs
func (r *auditRepository) buildListQuery(filter *audit.AuditLogFilter, isCount bool) (string, []interface{}) {
	var selectClause string
	if isCount {
		selectClause = "SELECT COUNT(*)"
	} else {
		selectClause = `SELECT 
			id, tenant_id, user_id, action, resource, resource_id, 
			details, ip_address, user_agent, timestamp`
	}

	query := selectClause + " FROM audit_logs"
	var conditions []string
	var args []interface{}
	argIndex := 1

	// Add WHERE conditions based on filter
	if filter != nil {
		if filter.TenantID != nil {
			conditions = append(conditions, "tenant_id = $"+strconv.Itoa(argIndex))
			args = append(args, *filter.TenantID)
			argIndex++
		}

		if filter.UserID != nil {
			conditions = append(conditions, "user_id = $"+strconv.Itoa(argIndex))
			args = append(args, *filter.UserID)
			argIndex++
		}

		if filter.Action != nil {
			conditions = append(conditions, "action = $"+strconv.Itoa(argIndex))
			args = append(args, string(*filter.Action))
			argIndex++
		}

		if filter.Resource != nil {
			conditions = append(conditions, "resource = $"+strconv.Itoa(argIndex))
			args = append(args, string(*filter.Resource))
			argIndex++
		}

		if filter.ResourceID != nil {
			conditions = append(conditions, "resource_id = $"+strconv.Itoa(argIndex))
			args = append(args, *filter.ResourceID)
			argIndex++
		}

		if filter.StartTime != nil {
			conditions = append(conditions, "timestamp >= $"+strconv.Itoa(argIndex))
			args = append(args, *filter.StartTime)
			argIndex++
		}

		if filter.EndTime != nil {
			conditions = append(conditions, "timestamp <= $"+strconv.Itoa(argIndex))
			args = append(args, *filter.EndTime)
			argIndex++
		}
	}

	// Add WHERE clause if conditions exist
	if len(conditions) > 0 {
		query += " WHERE " + strings.Join(conditions, " AND ")
	}

	// Add ORDER BY and LIMIT/OFFSET for non-count queries
	if !isCount {
		query += " ORDER BY timestamp DESC"

		if filter != nil {
			if filter.Limit > 0 {
				query += " LIMIT $" + strconv.Itoa(argIndex)
				args = append(args, filter.Limit)
				argIndex++
			}

			if filter.Offset > 0 {
				query += " OFFSET $" + strconv.Itoa(argIndex)
				args = append(args, filter.Offset)
				argIndex++
			}
		}
	}

	return query, args
}
