package integration_test

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"os/exec"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/suite"
)

type IntegrationTestSuite struct {
	suite.Suite
	serverCmd *exec.Cmd
	client    *http.Client
	baseURL   string
}

func (s *IntegrationTestSuite) SetupSuite() {
	// Setup test server/client.
	// Behavior:
	// - If TEST_SERVER_URL is set, use it and do not attempt to start a server.
	// - If START_TEST_SERVER=true, attempt to start the server in a subprocess
	//   using `go run cmd/server/main.go` and wait until /health responds 200.
	// - Otherwise, default to http://localhost:8080 and assume a server is
	//   already running there.

	s.client = &http.Client{Timeout: 5 * time.Second}

	// Prefer explicit TEST_SERVER_URL
	if base := os.Getenv("TEST_SERVER_URL"); base != "" {
		s.baseURL = base
		return
	}

	// Optionally start server in subprocess (requires working environment)
	if os.Getenv("START_TEST_SERVER") == "true" {
		// Ensure required env vars for the real server are present. The
		// application's config.Load() panics if these are missing, so fail
		// early with a clear message instead of starting a process that will
		// immediately crash.
		required := []string{"BASE_DOMAIN", "JWT_SECRET", "SENDGRID_API_KEY", "BASE_URL"}
		var missing []string
		for _, k := range required {
			if os.Getenv(k) == "" {
				missing = append(missing, k)
			}
		}
		if len(missing) > 0 {
			s.T().Fatalf("START_TEST_SERVER=true but required env vars missing: %v; set TEST_SERVER_URL instead or provide these env vars", missing)
		}

		// Start server using `go run` so we reuse the project's main wiring.
		cmd := exec.CommandContext(context.Background(), "go", "run", "./cmd/server")
		// forward output to test process so logs are visible when running tests
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr

		if err := cmd.Start(); err != nil {
			s.T().Fatalf("failed to start server subprocess: %v", err)
		}
		s.serverCmd = cmd

		// Poll health endpoint until ready or timeout
		s.baseURL = "http://localhost:8080"
		deadline := time.Now().Add(15 * time.Second)
		for time.Now().Before(deadline) {
			req, _ := http.NewRequest("GET", s.baseURL+"/health", nil)
			resp, err := s.client.Do(req)
			if err == nil && resp.StatusCode == http.StatusOK {
				if resp.Body != nil {
					resp.Body.Close()
				}
				return
			}
			if resp != nil && resp.Body != nil {
				resp.Body.Close()
			}
			time.Sleep(500 * time.Millisecond)
		}

		// If we reach here, server didn't start in time
		// Kill the process and fail the setup.
		_ = cmd.Process.Kill()
		s.T().Fatal("server did not become healthy in time")
	}

	// Default: assume server already running on localhost:8080
	s.baseURL = "http://localhost:8080"
}

func (s *IntegrationTestSuite) TearDownSuite() {
	if s.serverCmd != nil && s.serverCmd.Process != nil {
		// Try graceful termination, then kill if needed
		_ = s.serverCmd.Process.Signal(os.Interrupt)
		done := make(chan struct{})
		go func() {
			s.serverCmd.Wait()
			close(done)
		}()
		select {
		case <-done:
		case <-time.After(3 * time.Second):
			_ = s.serverCmd.Process.Kill()
		}
	}
}

func (s *IntegrationTestSuite) TestHealthCheck() {
	req, err := http.NewRequest("GET", s.baseURL+"/health", nil)
	s.NoError(err)

	resp, err := s.client.Do(req)
	s.Require().NoError(err)
	defer resp.Body.Close()

	s.Equal(http.StatusOK, resp.StatusCode)

	var health map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&health); err == nil {
		// If the endpoint returns a JSON status, assert expected shape/value
		if v, ok := health["status"]; ok {
			assert.Equal(s.T(), "healthy", v)
		}
	} else {
		// If body wasn't JSON, at least ensure we got 200
		s.T().Logf("health endpoint did not return JSON: %v", err)
	}
}

func TestIntegrationSuite(t *testing.T) {
	suite.Run(t, new(IntegrationTestSuite))
}
