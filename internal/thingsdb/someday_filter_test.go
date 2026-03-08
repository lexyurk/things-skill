package thingsdb

import "testing"

func TestIsInSomedayProject(t *testing.T) {
	projectIDs := map[string]struct{}{
		"project-someday": {},
	}
	headingToProject := map[string]string{
		"heading-someday": "project-someday",
	}

	tests := []struct {
		name string
		task Task
		want bool
	}{
		{
			name: "matches project directly",
			task: Task{ProjectUUID: "project-someday"},
			want: true,
		},
		{
			name: "matches heading mapped to someday project",
			task: Task{HeadingUUID: "heading-someday"},
			want: true,
		},
		{
			name: "project not in someday set",
			task: Task{ProjectUUID: "project-active"},
			want: false,
		},
		{
			name: "heading not mapped to someday project",
			task: Task{HeadingUUID: "heading-active"},
			want: false,
		},
		{
			name: "task without project or heading",
			task: Task{},
			want: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := isInSomedayProject(tt.task, projectIDs, headingToProject)
			if got != tt.want {
				t.Fatalf("isInSomedayProject() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestFilterSomedayProjectTasks(t *testing.T) {
	repo := openFixtureRepo(t)

	input := []Task{
		{UUID: "todo-anytime-someday-project", ProjectUUID: "project-someday"},
		{UUID: "todo-heading-someday", HeadingUUID: "heading-someday"},
		{UUID: "todo-anytime-active", ProjectUUID: "project-active"},
		{UUID: "todo-inbox"},
	}
	filtered, err := repo.FilterSomedayProjectTasks(input)
	if err != nil {
		t.Fatal(err)
	}
	if len(filtered) != 2 {
		t.Fatalf("expected 2 tasks after filtering, got %d", len(filtered))
	}
	if filtered[0].UUID != "todo-anytime-active" || filtered[1].UUID != "todo-inbox" {
		t.Fatalf("unexpected filtered tasks: %#v", filtered)
	}
}
