// Package cloud runs the bundled Things Cloud package without shell commands or
// a separately installed Python dependency. The Python package owns the protocol.
package cloud

import (
	"context"
	"embed"
	"fmt"
	"io"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
)

//go:embed all:runtime
var runtimeFiles embed.FS

// Client launches the shared CLI or its newline-delimited stdio MCP server.
type Client struct {
	Python  string
	DataDir string
	// TempDir is optional, primarily to isolate runtime extraction in tests.
	TempDir string
}

func (c Client) extract() (string, error) {
	directory, err := os.MkdirTemp(c.TempDir, "things-cloud-runtime-")
	if err != nil {
		return "", fmt.Errorf("create private cloud runtime: %w", err)
	}
	err = fs.WalkDir(runtimeFiles, "runtime", func(path string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		relative, err := filepath.Rel("runtime", path)
		if err != nil {
			return err
		}
		target := filepath.Join(directory, relative)
		if entry.IsDir() {
			return os.MkdirAll(target, 0700)
		}
		body, err := runtimeFiles.ReadFile(path)
		if err != nil {
			return err
		}
		return os.WriteFile(target, body, 0600)
	})
	if err != nil {
		_ = os.RemoveAll(directory)
		return "", fmt.Errorf("extract bundled cloud runtime: %w", err)
	}
	return directory, nil
}

// Run inherits the caller's streams directly. In serve mode, stdout contains
// only MCP messages; the Go parent never prints a banner or parses task data.
func (c Client) Run(ctx context.Context, args []string, stdin io.Reader, stdout, stderr io.Writer) error {
	python := c.Python
	if python == "" {
		python = "python3"
	}
	executable, err := exec.LookPath(python)
	if err != nil {
		return fmt.Errorf("Things Cloud requires Python 3.9+; install python3 or set --cloud-python")
	}
	directory, err := c.extract()
	if err != nil {
		return err
	}
	defer os.RemoveAll(directory)
	// -I excludes the current directory, PYTHONPATH, and user site packages.
	// The runtime path is an argument, never interpolated into executable code.
	bootstrap := "import runpy,sys; sys.path.insert(0,sys.argv.pop(1)); runpy.run_module('things_cloud',run_name='__main__')"
	arguments := []string{"-I", "-c", bootstrap, directory}
	if c.DataDir != "" {
		arguments = append(arguments, "--data-dir", c.DataDir)
	}
	arguments = append(arguments, args...)
	command := exec.CommandContext(ctx, executable, arguments...)
	command.Stdin, command.Stdout, command.Stderr = stdin, stdout, stderr
	if err := command.Run(); err != nil {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		// The Python CLI already reports a redacted error on stderr. Never echo
		// command arguments or arbitrary subprocess output into an error.
		return fmt.Errorf("Things Cloud command failed; see its diagnostic above")
	}
	return nil
}
