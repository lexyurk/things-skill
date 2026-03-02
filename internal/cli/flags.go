package cli

import (
	"fmt"
	"strings"
)

func requireFlag(name string, value string) error {
	if strings.TrimSpace(value) == "" {
		return fmt.Errorf("--%s is required", name)
	}
	return nil
}
