//go:build !darwin

package thingsurl

import (
	"context"
	"errors"
)

var ErrUnsupportedPlatform = errors.New("things write/navigation commands require macOS")

type DefaultExecutor struct{}

func (e DefaultExecutor) Execute(_ context.Context, _ string) error {
	return ErrUnsupportedPlatform
}
