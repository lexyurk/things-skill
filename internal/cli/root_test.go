package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"os"
	"strings"
	"testing"
)

func captureStdout(t *testing.T, fn func() error) (string, error) {
	t.Helper()

	originalStdout := os.Stdout
	readPipe, writePipe, err := os.Pipe()
	if err != nil {
		t.Fatalf("create stdout pipe: %v", err)
	}

	os.Stdout = writePipe
	var output bytes.Buffer
	copyDone := make(chan error, 1)
	go func() {
		_, copyErr := io.Copy(&output, readPipe)
		copyDone <- copyErr
	}()

	runErr := fn()
	_ = writePipe.Close()
	os.Stdout = originalStdout

	copyErr := <-copyDone
	_ = readPipe.Close()
	if copyErr != nil {
		t.Fatalf("capture stdout: %v", copyErr)
	}

	return output.String(), runErr
}

func TestExecuteURLDryRunJSONDoesNotPrintRawURL(t *testing.T) {
	a := &app{dryRun: true, output: "json"}

	output, err := captureStdout(t, func() error {
		return a.executeURL(context.Background(), "things:///show?id=today")
	})
	if err != nil {
		t.Fatalf("executeURL dry-run json failed: %v", err)
	}
	if strings.TrimSpace(output) != "" {
		t.Fatalf("expected no raw URL output in json mode, got %q", output)
	}
}

func TestTodoAddDryRunJSONOutputsValidJSON(t *testing.T) {
	a := &app{}
	root := newRootCommand(a)
	root.SetArgs([]string{"--dry-run", "--format", "json", "todo", "add", "--title", "Test Todo"})

	output, err := captureStdout(t, root.Execute)
	if err != nil {
		t.Fatalf("execute command: %v", err)
	}

	var payload map[string]string
	if err := json.Unmarshal([]byte(strings.TrimSpace(output)), &payload); err != nil {
		t.Fatalf("expected valid json output, got %q: %v", output, err)
	}
	if payload["url"] == "" {
		t.Fatalf("expected url in payload, got %#v", payload)
	}
}
