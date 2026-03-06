package thingsdb

import (
	"strings"
	"testing"
)

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

func TestBuildTaskQueryLastRejectsZeroPeriod(t *testing.T) {
	_, _, err := buildTaskQuery(TaskFilter{Last: "0d"})
	if err == nil {
		t.Fatal("expected invalid offset error")
	}
	if err != ErrInvalidOffset {
		t.Fatalf("expected %v, got %v", ErrInvalidOffset, err)
	}
}

func TestBuildTaskQueryLastFiltersUseLocaltimeOnBothSides(t *testing.T) {
	query, args, err := buildTaskQuery(TaskFilter{
		Last:         "1d",
		LastStopDate: "1d",
	})
	if err != nil {
		t.Fatalf("buildTaskQuery() error = %v", err)
	}

	lastCreationClause := "datetime(TASK.creationDate, 'unixepoch', 'localtime') > datetime('now', ?, 'localtime')"
	if !strings.Contains(query, lastCreationClause) {
		t.Fatalf("expected query to contain %q", lastCreationClause)
	}

	lastStopClause := "datetime(TASK.stopDate, 'unixepoch', 'localtime') > datetime('now', ?, 'localtime')"
	if !strings.Contains(query, lastStopClause) {
		t.Fatalf("expected query to contain %q", lastStopClause)
	}

	if len(args) != 2 {
		t.Fatalf("expected two args, got %d", len(args))
	}
	if args[0] != "-1 days" {
		t.Fatalf("expected first arg %q, got %#v", "-1 days", args[0])
	}
	if args[1] != "-1 days" {
		t.Fatalf("expected second arg %q, got %#v", "-1 days", args[1])
	}
}

func TestBuildTaskQueryProjectFilterIncludesHeadingProjectTodos(t *testing.T) {
	query, args, err := buildTaskQuery(TaskFilter{Project: "project-1"})
	if err != nil {
		t.Fatalf("buildTaskQuery() error = %v", err)
	}

	projectClause := "(TASK.project = ? OR PROJECT_OF_HEADING.uuid = ?)"
	if !strings.Contains(query, projectClause) {
		t.Fatalf("expected query to contain %q", projectClause)
	}

	if len(args) != 2 {
		t.Fatalf("expected two args, got %d", len(args))
	}
	if args[0] != "project-1" || args[1] != "project-1" {
		t.Fatalf("expected args [project-1 project-1], got %#v", args)
	}
}

func TestBuildTaskQueryProjectFilterDirectItemsOnly(t *testing.T) {
	query, args, err := buildTaskQuery(TaskFilter{
		Project:            "project-1",
		DirectProjectItems: true,
	})
	if err != nil {
		t.Fatalf("buildTaskQuery() error = %v", err)
	}

	projectClause := "TASK.project = ?"
	if !strings.Contains(query, projectClause) {
		t.Fatalf("expected query to contain %q", projectClause)
	}
	if strings.Contains(query, "PROJECT_OF_HEADING.uuid = ?") {
		t.Fatalf("expected direct project query to exclude heading-project clause")
	}

	if len(args) != 1 {
		t.Fatalf("expected one arg, got %d", len(args))
	}
	if args[0] != "project-1" {
		t.Fatalf("expected arg project-1, got %#v", args[0])
	}
}
