package httpserver

import (
	"net/http"

	"github.com/labstack/echo/v4"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	requestsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "The total number of HTTP requests",
		},
		[]string{"method", "endpoint", "status"},
	)

	requestDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name: "http_request_duration_seconds",
			Help: "The HTTP request latencies in seconds",
		},
		[]string{"method", "endpoint"},
	)
)

func init() {
	prometheus.MustRegister(requestsTotal)
	prometheus.MustRegister(requestDuration)
}

// GetRequestsTotal returns the requests total metric for middleware use
func GetRequestsTotal() *prometheus.CounterVec {
	return requestsTotal
}

// GetRequestDuration returns the request duration metric for middleware use
func GetRequestDuration() *prometheus.HistogramVec {
	return requestDuration
}

// LogMetricsInitialization logs that metrics have been initialized
func (s *Server) LogMetricsInitialization() {
	if s.logger != nil {
		s.logger.Info("Prometheus metrics initialized and registered")
		s.logger.WithFields(map[string]interface{}{
			"http_requests_total":   "Counter for HTTP requests by method, endpoint, status",
			"http_request_duration": "Histogram for HTTP request duration by method, endpoint",
			"metrics_endpoint":      "/metrics",
		}).Debug("Available Prometheus metrics")
	}
}

// Metrics handler
func (s *Server) metricsHandler() http.Handler {
	return promhttp.Handler()
}

// metricsEndpoint wraps the metrics handler with logging
func (s *Server) metricsEndpoint(c echo.Context) error {
	if s.logger != nil {
		s.logger.Debug("Serving Prometheus metrics")
	}
	handler := s.metricsHandler()
	handler.ServeHTTP(c.Response(), c.Request())
	return nil
}
