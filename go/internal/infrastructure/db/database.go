package db

import (
	"context"
	"fmt"
	"time"

	"github.com/golang-migrate/migrate/v4"
	"github.com/golang-migrate/migrate/v4/database/postgres"
	_ "github.com/golang-migrate/migrate/v4/source/file"
	"github.com/jmoiron/sqlx"
	_ "github.com/lib/pq"

	"github.com/avatarctic/clean-architecture-saas/go/configs"
)

type Database struct {
	DB *sqlx.DB
}

// NewDatabase opens a DB using just the DSN and sensible defaults for pool settings.
func NewDatabase(dsn string) (*Database, error) {
	// Build a default config so callers using the old signature keep the same behavior
	cfg := &configs.DatabaseConfig{
		DSN:             dsn,
		MaxOpenConns:    25,
		MaxIdleConns:    25,
		ConnMaxLifetime: 30 * time.Minute,
		ConnMaxIdleTime: 5 * time.Minute,
	}
	return NewDatabaseWithConfig(cfg)
}

// NewDatabaseWithConfig opens a DB using the provided DatabaseConfig and applies pool settings.
func NewDatabaseWithConfig(cfg *configs.DatabaseConfig) (*Database, error) {
	dbx, err := sqlx.Open("postgres", cfg.DSN)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Apply pool settings from config
	if cfg.MaxOpenConns > 0 {
		dbx.SetMaxOpenConns(cfg.MaxOpenConns)
	}
	if cfg.MaxIdleConns > 0 {
		dbx.SetMaxIdleConns(cfg.MaxIdleConns)
	}
	if cfg.ConnMaxLifetime > 0 {
		dbx.SetConnMaxLifetime(cfg.ConnMaxLifetime)
	}
	if cfg.ConnMaxIdleTime > 0 {
		dbx.SetConnMaxIdleTime(cfg.ConnMaxIdleTime)
	}

	// Use PingContext with timeout to avoid hanging at startup
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := dbx.PingContext(ctx); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	return &Database{DB: dbx}, nil
}

func (d *Database) Close() error {
	return d.DB.Close()
}

func (d *Database) Migrate(migrationsPath string) error {
	driver, err := postgres.WithInstance(d.DB.DB, &postgres.Config{})
	if err != nil {
		return fmt.Errorf("failed to create migrate driver: %w", err)
	}

	m, err := migrate.NewWithDatabaseInstance(
		fmt.Sprintf("file://%s", migrationsPath),
		"postgres", driver,
	)
	if err != nil {
		return fmt.Errorf("failed to create migrate instance: %w", err)
	}

	if err := m.Up(); err != nil && err != migrate.ErrNoChange {
		return fmt.Errorf("failed to run migrations: %w", err)
	}

	return nil
}
