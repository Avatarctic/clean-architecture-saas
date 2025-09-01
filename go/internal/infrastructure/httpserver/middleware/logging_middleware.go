package middleware

import (
	"github.com/labstack/echo/v4"
	"github.com/sirupsen/logrus"
)

type LoggingMiddleware struct {
	logger *logrus.Logger
}

func NewLoggingMiddleware(logger *logrus.Logger) *LoggingMiddleware {
	return &LoggingMiddleware{logger: logger}
}

func (m *LoggingMiddleware) RequestLogging() echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			if m.logger != nil {
				m.logger.WithFields(logrus.Fields{"method": c.Request().Method, "path": c.Path()}).Debug("incoming request")
			}
			return next(c)
		}
	}
}
