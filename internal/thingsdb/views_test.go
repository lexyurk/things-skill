package thingsdb

import "testing"

func TestUpcomingContainsFutureTask(t *testing.T) {
	repo := openFixtureRepo(t)
	tasks, err := repo.Upcoming()
	if err != nil {
		t.Fatal(err)
	}
	if !taskExists(tasks, "todo-upcoming") {
		t.Fatalf("expected upcoming task in upcoming view")
	}
}

func TestTaggedItems(t *testing.T) {
	repo := openFixtureRepo(t)
	tasks, err := repo.TaggedItems("work")
	if err != nil {
		t.Fatal(err)
	}
	if !taskExists(tasks, "todo-anytime-active") {
		t.Fatalf("expected task with 'work' tag")
	}
}

func TestSearchAdvancedTypeProject(t *testing.T) {
	repo := openFixtureRepo(t)
	tasks, err := repo.SearchAdvanced(SearchAdvancedFilter{
		Type: "project",
	})
	if err != nil {
		t.Fatal(err)
	}
	if !taskExists(tasks, "project-active") || !taskExists(tasks, "project-someday") {
		t.Fatalf("expected projects in advanced type filter")
	}
}
