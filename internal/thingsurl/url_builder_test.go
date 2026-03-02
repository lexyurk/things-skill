package thingsurl

import (
	"strings"
	"testing"
)

func TestAddTodoURL(t *testing.T) {
	url := AddTodoURL(AddTodoInput{
		Title:          "Test Todo",
		Notes:          "Test notes",
		When:           "today",
		Deadline:       "2099-12-31",
		Tags:           []string{"work", "urgent"},
		ChecklistItems: []string{"First", "Second"},
		ListID:         "project-1",
		HeadingID:      "heading-1",
	})

	expectedContains := []string{
		"things:///add?",
		"title=Test+Todo",
		"notes=Test+notes",
		"when=today",
		"deadline=2099-12-31",
		"tags=work%2Curgent",
		"checklist-items=First%0ASecond",
		"list-id=project-1",
		"heading-id=heading-1",
	}
	for _, part := range expectedContains {
		if !contains(url, part) {
			t.Fatalf("url missing %q: %s", part, url)
		}
	}
}

func TestUpdateTodoURLIncludesToken(t *testing.T) {
	completed := true
	url := UpdateTodoURL(UpdateTodoInput{
		ID:        "todo-1",
		AuthToken: "auth-token",
		Title:     "Updated",
		Completed: &completed,
	})
	if !contains(url, "auth-token=auth-token") {
		t.Fatalf("expected auth token in update url: %s", url)
	}
	if !contains(url, "completed=true") {
		t.Fatalf("expected completed flag in update url: %s", url)
	}
}

func TestShowURL(t *testing.T) {
	url := ShowURL("today", "", []string{"work", "home"})
	if !contains(url, "things:///show?") {
		t.Fatalf("expected show command url: %s", url)
	}
	if !contains(url, "id=today") || !contains(url, "filter=work%2Chome") {
		t.Fatalf("expected id and filter in url: %s", url)
	}
}

func contains(s string, part string) bool {
	return strings.Contains(s, part)
}
