package thingsdb

import (
	"os"
	"path/filepath"
	"testing"
)

func TestResolveDBPathOverride(t *testing.T) {
	got, err := ResolveDBPath("/tmp/custom.sqlite")
	if err != nil {
		t.Fatal(err)
	}
	if got != "/tmp/custom.sqlite" {
		t.Fatalf("expected override path, got %q", got)
	}
}

func TestResolveDBPathFromEnv(t *testing.T) {
	t.Setenv(EnvDBPath, "/tmp/env.sqlite")
	got, err := ResolveDBPath("")
	if err != nil {
		t.Fatal(err)
	}
	if got != "/tmp/env.sqlite" {
		t.Fatalf("expected env path, got %q", got)
	}
}

func TestResolveDBPathLegacyFallback(t *testing.T) {
	t.Setenv(EnvDBPath, "")
	tmpHome := t.TempDir()
	t.Setenv("HOME", tmpHome)

	legacyPath := filepath.Join(
		tmpHome,
		"Library",
		"Group Containers",
		"JLMPQHK86H.com.culturedcode.ThingsMac",
		"Things Database.thingsdatabase",
		"main.sqlite",
	)
	if err := os.MkdirAll(filepath.Dir(legacyPath), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(legacyPath, []byte(""), 0o644); err != nil {
		t.Fatal(err)
	}

	got, err := ResolveDBPath("")
	if err != nil {
		t.Fatal(err)
	}
	if got != legacyPath {
		t.Fatalf("expected legacy path %q, got %q", legacyPath, got)
	}
}
