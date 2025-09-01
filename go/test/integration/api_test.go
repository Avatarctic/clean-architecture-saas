package integration_test

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/suite"
)

type IntegrationTestSuite struct {
	suite.Suite
	serverCmd    *exec.Cmd
	serverCancel func()
	client       *http.Client
	baseURL      string
}

//nolint:gocognit // test setup: reasonably complex integration test bootstrap
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
		required := []string{"BASE_DOMAIN", "JWT_SECRET", "SENDGRID_API_KEY", "BASE_URL"}
		if missing := checkRequiredEnv(required); len(missing) > 0 {
			s.T().Fatalf("START_TEST_SERVER=true but required env vars missing: %v; set TEST_SERVER_URL instead or provide these env vars", missing)
		}

		cmd, cancel, err := startServerProcess()
		if err != nil {
			s.T().Fatalf("failed to start server subprocess: %v", err)
		}
		s.serverCmd = cmd
		s.serverCancel = cancel

		s.baseURL = "http://localhost:8080"
		timeoutSecs := 60
		if v := os.Getenv("TEST_SERVER_STARTUP_SECONDS"); v != "" {
			if n, err := strconv.Atoi(v); err == nil && n > 0 {
				timeoutSecs = n
			}
		}
		if ok := waitForServerHealthy(s.client, s.baseURL, timeoutSecs); !ok {
			_ = cmd.Process.Kill()
			s.T().Fatal("server did not become healthy in time")
		}
	}

	// Default: assume server already running on localhost:8080
	s.baseURL = "http://localhost:8080"
}

// checkRequiredEnv returns a slice of missing environment variable names.
func checkRequiredEnv(keys []string) []string {
	var missing []string
	for _, k := range keys {
		if os.Getenv(k) == "" {
			missing = append(missing, k)
		}
	}
	return missing
}

// startServerProcess starts the server subprocess using an explicit path to
// cmd/server/main.go and returns the started *exec.Cmd.
func startServerProcess() (*exec.Cmd, func(), error) {
	wd, err := os.Getwd()
	if err != nil {
		return nil, nil, err
	}
	repoRoot := filepath.Join(wd, "..", "..")
	mainFile := filepath.Join(repoRoot, "cmd", "server", "main.go")
	ctx, cancel := context.WithCancel(context.Background())
	cmd := exec.CommandContext(ctx, "go", "run", mainFile)
	// Ensure the command runs from the repo go/ root.
	cmd.Dir = repoRoot
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		cancel()
		return nil, nil, err
	}
	return cmd, cancel, nil
}

// waitForServerHealthy polls the /health endpoint until it returns 200 or
// the timeout (in seconds) elapses.
func waitForServerHealthy(client *http.Client, baseURL string, timeoutSecs int) bool {
	fmt.Fprintf(os.Stdout, "Waiting up to %ds for test server to become healthy...\n", timeoutSecs)
	deadline := time.Now().Add(time.Duration(timeoutSecs) * time.Second)
	for time.Now().Before(deadline) {
		req, _ := http.NewRequest("GET", baseURL+"/health", nil)
		resp, err := client.Do(req)
		if err == nil && resp.StatusCode == http.StatusOK {
			if resp.Body != nil {
				resp.Body.Close()
			}
			return true
		}
		if resp != nil && resp.Body != nil {
			resp.Body.Close()
		}
		time.Sleep(500 * time.Millisecond)
	}
	return false
}

func (s *IntegrationTestSuite) TearDownSuite() {
	if s.serverCmd != nil && s.serverCmd.Process != nil {
		// Cancel the server context if available (will request graceful
		// shutdown), then wait for process to exit and kill if it doesn't.
		if s.serverCancel != nil {
			s.serverCancel()
		} else {
			_ = s.serverCmd.Process.Signal(os.Interrupt)
		}

		done := make(chan struct{})
		go func() {
			s.serverCmd.Wait()
			close(done)
		}()
		select {
		case <-done:
		case <-time.After(10 * time.Second):
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
