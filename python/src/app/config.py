from pydantic import BaseSettings


class Settings(BaseSettings):
    server_host: str = "0.0.0.0"
    server_port: int = 8080
    # Optional full database URL override (useful for tests)
    database_url: str = ""
    db_host: str = "db"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_name: str = "saas_db"
    # Database connection pool settings
    # Increased from 5/10 to 20/30 for better concurrency under load
    db_pool_size: int = 20  # Number of connections to keep in pool
    db_max_overflow: int = 30  # Additional connections beyond pool_size (total max: 50)
    db_pool_recycle: int = 3600  # Recycle connections after 1 hour
    db_pool_pre_ping: bool = True  # Verify connections before use
    jwt_secret: str = "changeme"
    # Access token lifetime (seconds)
    access_token_ttl_seconds: int = 900  # 15 minutes
    # Refresh token lifetime (seconds). Default: 7 days
    refresh_token_ttl_seconds: int = 604800
    # Background cleanup interval for refresh tokens (seconds). Default daily.
    refresh_token_cleanup_interval_seconds: int = 86400
    # When purging revoked tokens, keep revoked tokens at least this many seconds (default 7 days).
    refresh_token_purge_keep_revoked_seconds: int = 604800
    # Tenant cache TTL (seconds) - increased from 300s to 3600s since tenants change rarely
    tenant_cache_ttl_seconds: int = 3600  # 1 hour
    # Email / SendGrid
    sendgrid_api_key: str = ""
    email_from: str = "no-reply@example.com"
    frontend_url: str = "http://localhost:3000"
    # Redis
    redis_url: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# module-level settings instance for convenience across the app
settings = Settings()
