package thingsdb

import (
	"errors"
	"os"
	"path/filepath"
)

const (
	EnvDBPath = "THINGSDB"
)

var (
	ErrDBPathNotFound = errors.New("could not locate Things database; set THINGSDB or use --db-path")
)

func ResolveDBPath(override string) (string, error) {
	if override != "" {
		return filepath.Abs(override)
	}
	if env := os.Getenv(EnvDBPath); env != "" {
		return filepath.Abs(env)
	}

	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}

	modernPattern := filepath.Join(
		home,
		"Library",
		"Group Containers",
		"JLMPQHK86H.com.culturedcode.ThingsMac",
		"ThingsData-*",
		"Things Database.thingsdatabase",
		"main.sqlite",
	)
	matches, err := filepath.Glob(modernPattern)
	if err != nil {
		return "", err
	}
	if len(matches) > 0 {
		return matches[0], nil
	}

	legacy := filepath.Join(
		home,
		"Library",
		"Group Containers",
		"JLMPQHK86H.com.culturedcode.ThingsMac",
		"Things Database.thingsdatabase",
		"main.sqlite",
	)
	if _, err := os.Stat(legacy); err == nil {
		return legacy, nil
	}

	return "", ErrDBPathNotFound
}
