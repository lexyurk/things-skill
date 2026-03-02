package thingsdb

import "errors"

var (
	ErrInvalidOffset = errors.New("invalid offset format, expected Xd|Xw|Xm|Xy")
)
