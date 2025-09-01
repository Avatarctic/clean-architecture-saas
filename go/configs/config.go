package configs

import (
	"fmt"
	"os"
	"strconv"
	"time"

	"github.com/joho/godotenv"
)

type Config struct {
	Server    ServerConfig
	Database  DatabaseConfig
	JWT       JWTConfig
	Email     EmailConfig
	Redis     RedisConfig
	Log       LogConfig
	RateLimit RateLimitConfig
}

type ServerConfig struct {
	Host         string
	Port         string
	ReadTimeout  time.Duration
	WriteTimeout time.Duration
	IdleTimeout  time.Duration
	TLSCertFile  string
	TLSKeyFile   string
	BaseDomain   string
}

type DatabaseConfig struct {
	Host     string
	Port     string
	User     string
	Password string
	DBName   string
	SSLMode  string
	DSN      string
	// Connection pool settings
	MaxOpenConns    int
	MaxIdleConns    int
	ConnMaxLifetime time.Duration
	ConnMaxIdleTime time.Duration
}

type JWTConfig struct {
	Secret          string
	AccessTokenTTL  time.Duration
	RefreshTokenTTL time.Duration
	SessionTimeout  time.Duration // Max inactivity before forced logout
}

type EmailConfig struct {
	SendGridAPIKey string
	FromEmail      string
	FromName       string
	CompanyName    string
	BaseURL        string
}

type RedisConfig struct {
	Host     string
	Port     string
	Password string
	DB       int
	// Pool and timeout settings
	PoolSize     int
	MinIdleConns int
	DialTimeout  time.Duration
	ReadTimeout  time.Duration
	WriteTimeout time.Duration
	PoolTimeout  time.Duration
	IdleTimeout  time.Duration
}

type LogConfig struct {
	Level  string
	Format string // json or text
}

type RateLimitConfig struct {
	DefaultRequestsPerMinute int
	BurstMultiplier          float64
	Window                   time.Duration
	KeyPrefix                string
}

func Load() (*Config, error) {
	// Load .env file if it exists
	_ = godotenv.Load()

	cfg := &Config{
		Server: ServerConfig{
			Host:         getEnv("SERVER_HOST", "0.0.0.0"),
			Port:         getEnv("SERVER_PORT", "8080"),
			ReadTimeout:  getDurationEnv("SERVER_READ_TIMEOUT", 30*time.Second),
			WriteTimeout: getDurationEnv("SERVER_WRITE_TIMEOUT", 30*time.Second),
			IdleTimeout:  getDurationEnv("SERVER_IDLE_TIMEOUT", 120*time.Second),
			TLSCertFile:  getEnv("TLS_CERT_FILE", ""),
			TLSKeyFile:   getEnv("TLS_KEY_FILE", ""),
			BaseDomain:   getEnvRequired("BASE_DOMAIN"),
		},
		Database: DatabaseConfig{
			Host:            getEnv("DB_HOST", "localhost"),
			Port:            getEnv("DB_PORT", "5432"),
			User:            getEnv("DB_USER", "postgres"),
			Password:        getEnv("DB_PASSWORD", "postgres"),
			DBName:          getEnv("DB_NAME", "saas_db"),
			SSLMode:         getEnv("DB_SSL_MODE", "disable"),
			MaxOpenConns:    getIntEnv("DB_MAX_OPEN_CONNS", 25),
			MaxIdleConns:    getIntEnv("DB_MAX_IDLE_CONNS", 25),
			ConnMaxLifetime: getDurationEnv("DB_CONN_MAX_LIFETIME", 30*time.Minute),
			ConnMaxIdleTime: getDurationEnv("DB_CONN_MAX_IDLE_TIME", 5*time.Minute),
		},
		JWT: JWTConfig{
			Secret:          getEnvRequired("JWT_SECRET"),
			AccessTokenTTL:  getDurationEnv("JWT_ACCESS_TTL", 15*time.Minute),
			RefreshTokenTTL: getDurationEnv("JWT_REFRESH_TTL", 24*7*time.Hour),
			SessionTimeout:  getDurationEnv("SESSION_TIMEOUT", 2*time.Hour), // Force logout after 2 hours of inactivity
		},
		Email: EmailConfig{
			SendGridAPIKey: getEnvRequired("SENDGRID_API_KEY"),
			FromEmail:      getEnv("FROM_EMAIL", "noreply@example.com"),
			FromName:       getEnv("FROM_NAME", "SaaS App"),
			CompanyName:    getEnv("COMPANY_NAME", "SaaS Company"),
			BaseURL:        getEnvRequired("BASE_URL"),
		},
		Redis: RedisConfig{
			Host:         getEnv("REDIS_HOST", "localhost"),
			Port:         getEnv("REDIS_PORT", "6379"),
			Password:     getEnv("REDIS_PASSWORD", ""),
			DB:           getIntEnv("REDIS_DB", 0),
			PoolSize:     getIntEnv("REDIS_POOL_SIZE", 10),
			MinIdleConns: getIntEnv("REDIS_MIN_IDLE_CONNS", 2),
			DialTimeout:  getDurationEnv("REDIS_DIAL_TIMEOUT", 5*time.Second),
			ReadTimeout:  getDurationEnv("REDIS_READ_TIMEOUT", 3*time.Second),
			WriteTimeout: getDurationEnv("REDIS_WRITE_TIMEOUT", 3*time.Second),
			PoolTimeout:  getDurationEnv("REDIS_POOL_TIMEOUT", 4*time.Second),
			IdleTimeout:  getDurationEnv("REDIS_IDLE_TIMEOUT", 5*time.Minute),
		},
		Log: LogConfig{
			Level:  getEnv("LOG_LEVEL", "info"),
			Format: getEnv("LOG_FORMAT", "json"),
		},
		RateLimit: RateLimitConfig{
			DefaultRequestsPerMinute: getIntEnv("RATE_LIMIT_RPM", 120),
			BurstMultiplier:          getFloatEnv("RATE_LIMIT_BURST", 2.0),
			Window:                   getDurationEnv("RATE_LIMIT_WINDOW", time.Minute),
			KeyPrefix:                getEnv("RATE_LIMIT_KEY_PREFIX", "ratelimit:tenant"),
		},
	}

	// Build database DSN
	cfg.Database.DSN = fmt.Sprintf(
		"host=%s port=%s user=%s password=%s dbname=%s sslmode=%s",
		cfg.Database.Host,
		cfg.Database.Port,
		cfg.Database.User,
		cfg.Database.Password,
		cfg.Database.DBName,
		cfg.Database.SSLMode,
	)

	return cfg, nil
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvRequired(key string) string {
	value := os.Getenv(key)
	if value == "" {
		panic(fmt.Sprintf("Required environment variable %s is not set", key))
	}
	return value
}

func getIntEnv(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

func getDurationEnv(key string, defaultValue time.Duration) time.Duration {
	if value := os.Getenv(key); value != "" {
		if duration, err := time.ParseDuration(value); err == nil {
			return duration
		}
	}
	return defaultValue
}

func getFloatEnv(key string, defaultValue float64) float64 {
	if value := os.Getenv(key); value != "" {
		if f, err := strconv.ParseFloat(value, 64); err == nil {
			return f
		}
	}
	return defaultValue
}
