package cloud

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func requirePython(t *testing.T) string {
	t.Helper()
	python, err := exec.LookPath("python3")
	if err != nil {
		t.Skip("Python 3.9+ is required for cloud runtime tests")
	}
	return python
}

func TestEmbeddedCLIWorksWithoutInstalledPythonPackage(t *testing.T) {
	client := Client{Python: requirePython(t), DataDir: filepath.Join(t.TempDir(), "data"), TempDir: t.TempDir()}
	var stdout, stderr bytes.Buffer
	if err := client.Run(context.Background(), []string{"--version"}, nil, &stdout, &stderr); err != nil {
		t.Fatalf("%v; diagnostics: %s", err, stderr.String())
	}
	if strings.TrimSpace(stdout.String()) != "0.1.0" {
		t.Fatalf("unexpected runtime version: %q", stdout.String())
	}
	entries, err := os.ReadDir(client.TempDir)
	if err != nil || len(entries) != 0 {
		t.Fatal("extracted runtime was not cleaned up")
	}
}

func TestServePassesCleanMCPMessagesAndDiscoversCloudTools(t *testing.T) {
	client := Client{Python: requirePython(t), DataDir: t.TempDir(), TempDir: t.TempDir()}
	requests := strings.NewReader(`{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"go-test","version":"1"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"things_status","arguments":{}}}
`)
	var stdout, stderr bytes.Buffer
	if err := client.Run(context.Background(), []string{"serve"}, requests, &stdout, &stderr); err != nil {
		t.Fatalf("%v; diagnostics: %s", err, stderr.String())
	}
	lines := strings.Split(strings.TrimSpace(stdout.String()), "\n")
	if len(lines) != 3 {
		t.Fatalf("expected three JSON-RPC replies, got %d", len(lines))
	}
	var discovered struct {
		Result struct {
			Tools []struct{ Name string }
		}
	}
	if err := json.Unmarshal([]byte(lines[1]), &discovered); err != nil {
		t.Fatalf("%v; diagnostics: %s", err, stderr.String())
	}
	if len(discovered.Result.Tools) != 13 {
		t.Fatalf("expected 13 cloud tools, got %d", len(discovered.Result.Tools))
	}
	if stderr.Len() != 0 {
		t.Fatal("MCP server produced unexpected diagnostics")
	}
}

func TestMissingPythonFailsClearly(t *testing.T) {
	err := (Client{Python: filepath.Join(t.TempDir(), "missing-python")}).Run(context.Background(), []string{"serve"}, nil, &bytes.Buffer{}, &bytes.Buffer{})
	if err == nil || !strings.Contains(err.Error(), "Python 3.9+") {
		t.Fatal("expected an actionable Python dependency error")
	}
}

func TestDisconnectedReadReturnsAnErrorWithoutFalseSuccess(t *testing.T) {
	client := Client{Python: requirePython(t), DataDir: t.TempDir(), TempDir: t.TempDir()}
	var stdout, stderr bytes.Buffer
	err := client.Run(context.Background(), []string{"list"}, nil, &stdout, &stderr)
	if err == nil || stdout.Len() != 0 || !strings.Contains(stderr.String(), "No account connected") {
		t.Fatal("expected a redacted disconnected error with no success output")
	}
}

func TestProcessDoesNotImportCodeFromCurrentDirectory(t *testing.T) {
	// PYTHONPATH must not override the bundled package when an agent invokes it.
	t.Setenv("PYTHONPATH", t.TempDir())
	client := Client{Python: requirePython(t), DataDir: t.TempDir(), TempDir: t.TempDir()}
	var stdout, stderr bytes.Buffer
	if err := client.Run(context.Background(), []string{"tools"}, nil, &stdout, &stderr); err != nil {
		t.Fatal(err)
	}
	var result map[string]json.RawMessage
	if err := json.Unmarshal(stdout.Bytes(), &result); err != nil || len(result["tools"]) == 0 {
		t.Fatal("bundled tools were not loaded")
	}
}
