package thingsdb

import (
	"database/sql"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	_ "modernc.org/sqlite"
)

func fixtureRoot(t *testing.T) string {
	t.Helper()
	_, current, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("unable to determine test file path")
	}
	return filepath.Join(filepath.Dir(current), "..", "..", "testdata")
}

func createFixtureDB(t *testing.T) string {
	t.Helper()
	root := fixtureRoot(t)
	schemaSQL, err := os.ReadFile(filepath.Join(root, "schema.sql"))
	if err != nil {
		t.Fatal(err)
	}
	seedSQL, err := os.ReadFile(filepath.Join(root, "seed.sql"))
	if err != nil {
		t.Fatal(err)
	}

	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "things-fixture.sqlite")
	db, err := sql.Open("sqlite", "file:"+dbPath+"?mode=rwc")
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()

	if _, err := db.Exec(string(schemaSQL)); err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec(string(seedSQL)); err != nil {
		t.Fatal(err)
	}
	return dbPath
}

func openFixtureRepo(t *testing.T) *Repository {
	t.Helper()
	repo, err := OpenPath(createFixtureDB(t))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		_ = repo.Close()
	})
	return repo
}

func taskExists(tasks []Task, uuid string) bool {
	for _, task := range tasks {
		if task.UUID == uuid {
			return true
		}
	}
	return false
}

func TestInbox(t *testing.T) {
	repo := openFixtureRepo(t)
	tasks, err := repo.Inbox()
	if err != nil {
		t.Fatal(err)
	}
	if !taskExists(tasks, "todo-inbox") {
		t.Fatalf("expected inbox task to be present: %#v", tasks)
	}
}

func TestAnytimeFiltersSomedayProjects(t *testing.T) {
	repo := openFixtureRepo(t)
	tasks, err := repo.Anytime()
	if err != nil {
		t.Fatal(err)
	}
	if taskExists(tasks, "todo-anytime-someday-project") {
		t.Fatalf("expected someday project task to be filtered from anytime view")
	}
	if taskExists(tasks, "todo-heading-someday") {
		t.Fatalf("expected heading-based someday task to be filtered from anytime view")
	}
	if !taskExists(tasks, "todo-anytime-active") {
		t.Fatalf("expected active anytime task to remain in anytime view")
	}
}

func TestSomedayIncludesInheritedTasks(t *testing.T) {
	repo := openFixtureRepo(t)
	tasks, err := repo.Someday()
	if err != nil {
		t.Fatal(err)
	}
	if !taskExists(tasks, "todo-anytime-someday-project") {
		t.Fatalf("expected anytime task from someday project in someday view")
	}
	if !taskExists(tasks, "todo-heading-someday") {
		t.Fatalf("expected heading-based task from someday project in someday view")
	}
}

func TestTodayComposition(t *testing.T) {
	repo := openFixtureRepo(t)
	tasks, err := repo.Today()
	if err != nil {
		t.Fatal(err)
	}
	if !taskExists(tasks, "todo-today-regular") {
		t.Fatalf("expected regular today task")
	}
	if !taskExists(tasks, "todo-unconfirmed-scheduled") {
		t.Fatalf("expected unconfirmed scheduled task")
	}
	if !taskExists(tasks, "todo-overdue") {
		t.Fatalf("expected overdue task")
	}
}

func TestAuthToken(t *testing.T) {
	repo := openFixtureRepo(t)
	token, err := repo.AuthToken()
	if err != nil {
		t.Fatal(err)
	}
	if token != "test-auth-token" {
		t.Fatalf("expected auth token, got %q", token)
	}
}

func TestGetByUUIDReturnsAnyTaskState(t *testing.T) {
	repo := openFixtureRepo(t)
	tests := []struct {
		name    string
		uuid    string
		status  string
		trashed bool
	}{
		{
			name:    "completed task",
			uuid:    "todo-completed",
			status:  "completed",
			trashed: false,
		},
		{
			name:    "canceled task",
			uuid:    "todo-canceled",
			status:  "canceled",
			trashed: false,
		},
		{
			name:    "trashed task",
			uuid:    "todo-trash",
			status:  "incomplete",
			trashed: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			task, err := repo.GetByUUID(tt.uuid)
			if err != nil {
				t.Fatal(err)
			}
			if task == nil {
				t.Fatalf("expected task %q to be returned", tt.uuid)
			}
			if task.UUID != tt.uuid {
				t.Fatalf("expected uuid %q, got %q", tt.uuid, task.UUID)
			}
			if task.Status != tt.status {
				t.Fatalf("expected status %q, got %q", tt.status, task.Status)
			}
			if task.Trashed != tt.trashed {
				t.Fatalf("expected trashed=%v, got %v", tt.trashed, task.Trashed)
			}
		})
	}
}

func TestOpenPathEscapesURIReservedCharacters(t *testing.T) {
	tests := []struct {
		name     string
		filename string
	}{
		{
			name:     "question_mark",
			filename: "things?fixture.sqlite",
		},
		{
			name:     "hash",
			filename: "things#fixture.sqlite",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			originalPath := createFixtureDB(t)
			escapedPath := filepath.Join(filepath.Dir(originalPath), tc.filename)
			if err := os.Rename(originalPath, escapedPath); err != nil {
				t.Fatal(err)
			}

			repo, err := OpenPath(escapedPath)
			if err != nil {
				t.Fatalf("OpenPath(%q) failed: %v", escapedPath, err)
			}
			t.Cleanup(func() {
				_ = repo.Close()
			})

			token, err := repo.AuthToken()
			if err != nil {
				t.Fatal(err)
			}
			if token != "test-auth-token" {
				t.Fatalf("expected auth token from escaped path db, got %q", token)
			}

			_, err = repo.db.Exec(`PRAGMA user_version = 1`)
			if err == nil {
				t.Fatalf("expected read-only database mode for %q", escapedPath)
			}
			if !strings.Contains(strings.ToLower(err.Error()), "readonly") {
				t.Fatalf("expected readonly error, got %v", err)
			}
		})
	}
}

func TestOpenPathWithRelativePath(t *testing.T) {
	absolutePath := createFixtureDB(t)
	dbDir := filepath.Dir(absolutePath)
	relativePath := filepath.Join(".", filepath.Base(absolutePath))

	originalWD, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	if err := os.Chdir(dbDir); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		_ = os.Chdir(originalWD)
	})

	repo, err := OpenPath(relativePath)
	if err != nil {
		t.Fatalf("OpenPath(%q) failed: %v", relativePath, err)
	}
	t.Cleanup(func() {
		_ = repo.Close()
	})

	token, err := repo.AuthToken()
	if err != nil {
		t.Fatal(err)
	}
	if token != "test-auth-token" {
		t.Fatalf("expected auth token from relative path db, got %q", token)
	}
}
