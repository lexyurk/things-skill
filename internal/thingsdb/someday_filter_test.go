package thingsdb

import "testing"

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
