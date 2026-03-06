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

func TestSearchAdvancedInvalidTypeReturnsError(t *testing.T) {
	repo := openFixtureRepo(t)
	_, err := repo.SearchAdvanced(SearchAdvancedFilter{
		Type: "invalid-type",
	})
	if err == nil {
		t.Fatal("expected invalid type error")
	}
}

func TestListViewLogbookPeriodIncludesCanceled(t *testing.T) {
	repo := openFixtureRepo(t)
	tasks, err := repo.ListView(ViewLogbook, "10d", 0)
	if err != nil {
		t.Fatal(err)
	}
	if !taskExists(tasks, "todo-completed") {
		t.Fatalf("expected completed task in logbook period")
	}
	if !taskExists(tasks, "todo-canceled") {
		t.Fatalf("expected canceled task in logbook period")
	}
}

func TestListViewLogbookPeriodUppercaseUnit(t *testing.T) {
	repo := openFixtureRepo(t)
	tasks, err := repo.ListView(ViewLogbook, "10D", 0)
	if err != nil {
		t.Fatal(err)
	}
	if !taskExists(tasks, "todo-completed") {
		t.Fatalf("expected completed task in logbook period")
	}
	if !taskExists(tasks, "todo-canceled") {
		t.Fatalf("expected canceled task in logbook period")
	}
}
