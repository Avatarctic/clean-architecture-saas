import prometheus_client
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# Guard against duplicated metric registration when the module is imported
# multiple times (for example, when running uvicorn with the reloader).
REQUEST_COUNT = getattr(prometheus_client, "app_REQUEST_COUNT", None)
REQUEST_LATENCY = getattr(prometheus_client, "app_REQUEST_LATENCY", None)
DB_QUERY_DURATION = getattr(prometheus_client, "app_DB_QUERY_DURATION", None)
DB_QUERY_ERRORS = getattr(prometheus_client, "app_DB_QUERY_ERRORS", None)
DB_POOL_SIZE = getattr(prometheus_client, "app_DB_POOL_SIZE", None)
DB_POOL_CHECKED_OUT = getattr(prometheus_client, "app_DB_POOL_CHECKED_OUT", None)
CACHE_OPERATIONS = getattr(prometheus_client, "app_CACHE_OPERATIONS", None)
CACHE_HITS = getattr(prometheus_client, "app_CACHE_HITS", None)
CACHE_MISSES = getattr(prometheus_client, "app_CACHE_MISSES", None)
CACHE_OPERATION_DURATION = getattr(prometheus_client, "app_CACHE_OPERATION_DURATION", None)
TENANT_REQUESTS = getattr(prometheus_client, "app_TENANT_REQUESTS", None)
ACTIVE_TENANTS = getattr(prometheus_client, "app_ACTIVE_TENANTS", None)
AUTH_ATTEMPTS = getattr(prometheus_client, "app_AUTH_ATTEMPTS", None)
ACTIVE_SESSIONS = getattr(prometheus_client, "app_ACTIVE_SESSIONS", None)
TOKEN_OPERATIONS = getattr(prometheus_client, "app_TOKEN_OPERATIONS", None)
PERMISSION_CHECKS = getattr(prometheus_client, "app_PERMISSION_CHECKS", None)
AUDIT_EVENTS = getattr(prometheus_client, "app_AUDIT_EVENTS", None)
FEATURE_FLAG_EVALUATIONS = getattr(prometheus_client, "app_FEATURE_FLAG_EVALUATIONS", None)
RATE_LIMIT_HITS = getattr(prometheus_client, "app_RATE_LIMIT_HITS", None)

# Initialize all metrics if any are None
if REQUEST_COUNT is None:
    # HTTP Metrics
    REQUEST_COUNT = Counter(
        "http_requests_total", "Total HTTP requests", ["method", "endpoint", "http_status"]
    )
    REQUEST_LATENCY = Histogram(
        "http_request_latency_seconds", "HTTP request latency in seconds", ["method", "endpoint"]
    )

    # Database Metrics
    DB_QUERY_DURATION = Histogram(
        "db_query_duration_seconds", "Database query duration in seconds", ["operation"]
    )
    DB_QUERY_ERRORS = Counter(
        "db_query_errors_total", "Total database query errors", ["operation", "error_type"]
    )
    DB_POOL_SIZE = Gauge("db_pool_size", "Database connection pool size")
    DB_POOL_CHECKED_OUT = Gauge(
        "db_pool_checked_out_connections", "Number of checked out database connections"
    )

    # Cache Metrics
    CACHE_OPERATIONS = Counter(
        "cache_operations_total", "Total cache operations", ["operation", "cache_type"]
    )
    CACHE_HITS = Counter("cache_hits_total", "Total cache hits", ["cache_type", "key_pattern"])
    CACHE_MISSES = Counter(
        "cache_misses_total", "Total cache misses", ["cache_type", "key_pattern"]
    )
    CACHE_OPERATION_DURATION = Histogram(
        "cache_operation_duration_seconds",
        "Cache operation duration in seconds",
        ["operation", "cache_type"],
    )

    # Multi-Tenancy Metrics
    TENANT_REQUESTS = Counter(
        "tenant_requests_total", "Total requests per tenant", ["tenant_id", "tenant_slug"]
    )
    ACTIVE_TENANTS = Gauge("active_tenants", "Number of active tenants")

    # Authentication Metrics
    AUTH_ATTEMPTS = Counter(
        "auth_attempts_total",
        "Total authentication attempts",
        ["result", "method"],  # result: success/failure, method: login/token_refresh
    )
    ACTIVE_SESSIONS = Gauge("active_sessions", "Number of active user sessions")
    TOKEN_OPERATIONS = Counter(
        "token_operations_total",
        "Total token operations",
        ["operation"],  # operation: generate/verify/revoke/blacklist
    )

    # Authorization Metrics
    PERMISSION_CHECKS = Counter(
        "permission_checks_total",
        "Total permission checks",
        ["result", "permission"],  # result: granted/denied
    )

    # Business Metrics
    AUDIT_EVENTS = Counter(
        "audit_events_total", "Total audit events written", ["action", "resource"]
    )
    FEATURE_FLAG_EVALUATIONS = Counter(
        "feature_flag_evaluations_total",
        "Total feature flag evaluations",
        ["key", "result"],  # result: enabled/disabled
    )

    # Rate Limiting Metrics
    RATE_LIMIT_HITS = Counter(
        "rate_limit_hits_total",
        "Total rate limit hits (blocked requests)",
        ["tenant_id", "endpoint"],
    )

    # Register all metrics on the prometheus_client module
    prometheus_client.app_REQUEST_COUNT = REQUEST_COUNT  # type: ignore[attr-defined]
    prometheus_client.app_REQUEST_LATENCY = REQUEST_LATENCY  # type: ignore[attr-defined]
    prometheus_client.app_DB_QUERY_DURATION = DB_QUERY_DURATION  # type: ignore[attr-defined]
    prometheus_client.app_DB_QUERY_ERRORS = DB_QUERY_ERRORS  # type: ignore[attr-defined]
    prometheus_client.app_DB_POOL_SIZE = DB_POOL_SIZE  # type: ignore[attr-defined]
    prometheus_client.app_DB_POOL_CHECKED_OUT = DB_POOL_CHECKED_OUT  # type: ignore[attr-defined]
    prometheus_client.app_CACHE_OPERATIONS = CACHE_OPERATIONS  # type: ignore[attr-defined]
    prometheus_client.app_CACHE_HITS = CACHE_HITS  # type: ignore[attr-defined]
    prometheus_client.app_CACHE_MISSES = CACHE_MISSES  # type: ignore[attr-defined]
    prometheus_client.app_CACHE_OPERATION_DURATION = CACHE_OPERATION_DURATION  # type: ignore[attr-defined]
    prometheus_client.app_TENANT_REQUESTS = TENANT_REQUESTS  # type: ignore[attr-defined]
    prometheus_client.app_ACTIVE_TENANTS = ACTIVE_TENANTS  # type: ignore[attr-defined]
    prometheus_client.app_AUTH_ATTEMPTS = AUTH_ATTEMPTS  # type: ignore[attr-defined]
    prometheus_client.app_ACTIVE_SESSIONS = ACTIVE_SESSIONS  # type: ignore[attr-defined]
    prometheus_client.app_TOKEN_OPERATIONS = TOKEN_OPERATIONS  # type: ignore[attr-defined]
    prometheus_client.app_PERMISSION_CHECKS = PERMISSION_CHECKS  # type: ignore[attr-defined]
    prometheus_client.app_AUDIT_EVENTS = AUDIT_EVENTS  # type: ignore[attr-defined]
    prometheus_client.app_FEATURE_FLAG_EVALUATIONS = FEATURE_FLAG_EVALUATIONS  # type: ignore[attr-defined]
    prometheus_client.app_RATE_LIMIT_HITS = RATE_LIMIT_HITS  # type: ignore[attr-defined]


def metrics_response():
    data = generate_latest()
    return data, CONTENT_TYPE_LATEST
