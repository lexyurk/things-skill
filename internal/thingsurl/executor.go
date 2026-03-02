package thingsurl

import "context"

type Executor interface {
	Execute(ctx context.Context, thingsURL string) error
}
