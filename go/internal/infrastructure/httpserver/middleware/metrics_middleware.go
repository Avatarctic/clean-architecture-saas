package middleware

import (
	"strconv"
	"time"

	"github.com/labstack/echo/v4"
	"github.com/prometheus/client_golang/prometheus"
)

// MetricsMiddleware holds the Prometheus metrics
type MetricsMiddleware struct {
	requestsTotal   *prometheus.CounterVec
	requestDuration *prometheus.HistogramVec
}

// NewMetricsMiddleware creates a new metrics middleware instance
func NewMetricsMiddleware(requestsTotal *prometheus.CounterVec, requestDuration *prometheus.HistogramVec) *MetricsMiddleware {
	return &MetricsMiddleware{
		requestsTotal:   requestsTotal,
		requestDuration: requestDuration,
	}
}

// CollectHTTPMetrics creates middleware that collects HTTP request metrics
func (m *MetricsMiddleware) CollectHTTPMetrics() echo.MiddlewareFunc {
	return echo.MiddlewareFunc(func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			start := time.Now()

			err := next(c)

			duration := time.Since(start).Seconds()
			method := c.Request().Method
			path := c.Path()
			if path == "" {
				path = c.Request().URL.Path
			}
			status := strconv.Itoa(c.Response().Status)

			m.requestsTotal.WithLabelValues(method, path, status).Inc()
			m.requestDuration.WithLabelValues(method, path).Observe(duration)

			return err
		}
	})
}
