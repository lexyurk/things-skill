//go:build darwin

package thingsurl

import (
	"context"
	"os/exec"
)

type DefaultExecutor struct{}

func (e DefaultExecutor) Execute(ctx context.Context, thingsURL string) error {
	return exec.CommandContext(ctx, "open", "-g", thingsURL).Run()
}
