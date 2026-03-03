package thingsdb

import "testing"

func TestBuildTaskQueryStartFilterNormalizesCase(t *testing.T) {
	tests := []struct {
		name      string
		start     string
		wantValue int
	}{
		{
			name:      "lowercase inbox",
			start:     "inbox",
			wantValue: 0,
		},
		{
			name:      "uppercase anytime",
			start:     "ANYTIME",
			wantValue: 1,
		},
		{
			name:      "mixed case someday",
			start:     "SoMeDaY",
			wantValue: 2,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, args, err := buildTaskQuery(TaskFilter{Start: tt.start})
			if err != nil {
				t.Fatalf("buildTaskQuery() error = %v", err)
			}
			if len(args) != 1 {
				t.Fatalf("expected one query arg, got %d", len(args))
			}
			gotValue, ok := args[0].(int)
			if !ok {
				t.Fatalf("expected start arg to be int, got %T", args[0])
			}
			if gotValue != tt.wantValue {
				t.Fatalf("expected start arg %d, got %d", tt.wantValue, gotValue)
			}
		})
	}
}

func TestBuildTaskQueryStartFilterRejectsInvalidValue(t *testing.T) {
	_, _, err := buildTaskQuery(TaskFilter{Start: "later"})
	if err == nil {
		t.Fatal("expected invalid start value error")
	}
}
