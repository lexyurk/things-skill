package cli

import (
	"bytes"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestCloudRoutingPreservesChangedFalseAndEmptyFlags(t *testing.T) {
	// A subprocess fixture captures the adapter request, without a network or
	// account. It also checks that stdout remains valid legacy CLI JSON.
	python, err := exec.LookPath("python3")
	if err != nil {
		t.Skip("requires Python")
	}
	directory := t.TempDir()
	recorder := filepath.Join(directory, "python-fixture")
	requestPath := filepath.Join(directory, "request.json")
	body := "#!" + python + "\nimport os,sys\nbody=sys.stdin.read()\nopen(os.environ['THINGS_TEST_REQUEST'],'w').write(body)\nprint('{\"kind\":\"result\",\"data\":{\"synced\":true},\"message\":\"Updated\"}')\n"
	if err := os.WriteFile(recorder, []byte(body), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("THINGS_TEST_REQUEST", requestPath)
	a := &app{}
	root := newRootCommand(a)
	root.SetArgs([]string{"--backend", "cloud", "--cloud-python", recorder, "--format", "json", "todo", "update", "--id", "A7h5eCi24RvAWKC3Hv3muf", "--notes=", "--completed=false", "--request-id", "same-request"})
	output, err := captureStdout(t, root.Execute)
	if err != nil {
		t.Fatal(err)
	}
	var result map[string]any
	if err := json.Unmarshal([]byte(output), &result); err != nil || result["synced"] != true {
		t.Fatalf("invalid command result: %q", output)
	}
	request, err := os.ReadFile(requestPath)
	if err != nil {
		t.Fatal(err)
	}
	var payload struct {
		Command []string
		Flags   map[string]any
		Changed []string
	}
	if err := json.Unmarshal(request, &payload); err != nil {
		t.Fatal(err)
	}
	if strings.Join(payload.Command, " ") != "todo update" || payload.Flags["notes"] != "" || payload.Flags["completed"] != false || payload.Flags["request-id"] != "same-request" {
		t.Fatalf("wrong adapter request: %s", request)
	}
	for _, expected := range []string{"notes", "completed", "request-id"} {
		found := false
		for _, name := range payload.Changed {
			found = found || name == expected
		}
		if !found {
			t.Fatalf("missing changed flag %s", expected)
		}
	}
}

func TestCloudBackendRejectsConflictingFlags(t *testing.T) {
	for _, a := range []*app{{backend: "unknown"}, {backend: "cloud", dryRun: true}, {backend: "cloud", dbPath: "/tmp/database"}} {
		if _, err := a.useCloud(); err == nil {
			t.Fatal("expected backend conflict error")
		}
	}
	use, err := (&app{backend: "auto", dryRun: true}).useCloud()
	if err != nil || use {
		t.Fatal("dry-run should retain local URL preview")
	}
}

func TestStatusAndLogoutReusePrivatePersistedAccount(t *testing.T) {
	python, err := exec.LookPath("python3")
	if err != nil {
		t.Skip("requires Python")
	}
	directory := t.TempDir()
	account := filepath.Join(directory, "account.json")
	if err := os.WriteFile(account, []byte(`{"email":"fixture@example.com","history_key":"fixture-capability","instance_id":"fixture"}`), 0600); err != nil {
		t.Fatal(err)
	}
	for _, command := range []string{"status", "logout", "status"} {
		root := newRootCommand(&app{})
		var stdout, stderr bytes.Buffer
		root.SetOut(&stdout)
		root.SetErr(&stderr)
		root.SetArgs([]string{"--cloud-python", python, "--cloud-data-dir", directory, command})
		if err := root.Execute(); err != nil {
			t.Fatalf("%s: %v", command, err)
		}
		var result map[string]any
		if err := json.Unmarshal(stdout.Bytes(), &result); err != nil {
			t.Fatal(err)
		}
		if strings.Contains(stdout.String(), "fixture-capability") {
			t.Fatal("status leaked credentials")
		}
	}
	if _, err := os.Stat(account); !os.IsNotExist(err) {
		t.Fatal("logout did not remove persisted access")
	}
}
