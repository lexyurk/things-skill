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
		"title=Test%20Todo",
		"notes=Test%20notes",
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
	if contains(url, "title=Test+Todo") || contains(url, "notes=Test+notes") {
		t.Fatalf("spaces should be percent-encoded, got: %s", url)
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

func TestBuildURLSpaceEncodingAndLiteralPlus(t *testing.T) {
	url := BuildURL("search", map[string]any{
		"query": "Buy milk + eggs",
	})
	if !contains(url, "query=Buy%20milk%20%2B%20eggs") {
		t.Fatalf("expected RFC 3986 encoding for query, got: %s", url)
	}
	if contains(url, "query=Buy+milk") {
		t.Fatalf("did not expect application/x-www-form-urlencoded space encoding: %s", url)
	}
}

func contains(s string, part string) bool {
	return strings.Contains(s, part)
}
