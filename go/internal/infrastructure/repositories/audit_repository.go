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

	// Build conditions and args from the filter using a helper so the function
	// body stays small and easier to reason about.
	conds, condArgs, nextIndex := r.buildConditions(filter, argIndex)
	if len(conds) > 0 {
		conditions = append(conditions, conds...)
		args = append(args, condArgs...)
		argIndex = nextIndex
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
			}
		}
	}

	return query, args
}

// buildConditions constructs WHERE conditions and their corresponding args from
// the provided filter. It starts numbering placeholders at startIndex and
// returns the next index after the last used one.
func (r *auditRepository) buildConditions(filter *audit.AuditLogFilter, startIndex int) ([]string, []interface{}, int) {
	var conditions []string
	var args []interface{}
	idx := startIndex
	if filter == nil {
		return conditions, args, idx
	}

	add := func(base string, v interface{}) {
		conditions = append(conditions, base+strconv.Itoa(idx))
		args = append(args, v)
		idx++
	}

	if filter.TenantID != nil {
		add("tenant_id = $", *filter.TenantID)
	}
	if filter.UserID != nil {
		add("user_id = $", *filter.UserID)
	}
	if filter.Action != nil {
		add("action = $", string(*filter.Action))
	}
	if filter.Resource != nil {
		add("resource = $", string(*filter.Resource))
	}
	if filter.ResourceID != nil {
		add("resource_id = $", *filter.ResourceID)
	}
	if filter.StartTime != nil {
		add("timestamp >= $", *filter.StartTime)
	}
	if filter.EndTime != nil {
		add("timestamp <= $", *filter.EndTime)
	}

	return conditions, args, idx
}
