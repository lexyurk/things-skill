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

func openMutatedFixtureRepo(t *testing.T, mutate func(*sql.DB) error) *Repository {
	t.Helper()

	dbPath := createFixtureDB(t)
	db, err := sql.Open("sqlite", "file:"+dbPath+"?mode=rw")
	if err != nil {
		t.Fatal(err)
	}
	if err := mutate(db); err != nil {
		_ = db.Close()
		t.Fatal(err)
	}
	if err := db.Close(); err != nil {
		t.Fatal(err)
	}

	repo, err := OpenPath(dbPath)
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

func TestProjectItemsPreserveDatabaseIndexOrder(t *testing.T) {
	repo := openFixtureRepo(t)
	projects, err := repo.Projects(true)
	if err != nil {
		t.Fatal(err)
	}

	var activeProject *Task
	for i := range projects {
		if projects[i].UUID == "project-active" {
			activeProject = &projects[i]
			break
		}
	}
	if activeProject == nil {
		t.Fatalf("expected active project to exist")
	}
	if len(activeProject.Items) < 2 {
		t.Fatalf("expected active project to include heading and task, got %#v", activeProject.Items)
	}

	if activeProject.Items[0].UUID != "heading-active" || activeProject.Items[1].UUID != "todo-anytime-active" {
		t.Fatalf(
			"expected project items to follow database index order [heading-active, todo-anytime-active], got [%s, %s]",
			activeProject.Items[0].UUID,
			activeProject.Items[1].UUID,
		)
	}
}

func TestProjectItemsDoNotDuplicateHeadingTodos(t *testing.T) {
	repo := openFixtureRepo(t)
	projects, err := repo.Projects(true)
	if err != nil {
		t.Fatal(err)
	}

	var somedayProject *Task
	for i := range projects {
		if projects[i].UUID == "project-someday" {
			somedayProject = &projects[i]
			break
		}
	}
	if somedayProject == nil {
		t.Fatalf("expected someday project to exist")
	}

	if taskExists(somedayProject.Items, "todo-heading-someday") {
		t.Fatalf("expected heading-based todo to be nested only under heading")
	}

	var somedayHeading *Task
	for i := range somedayProject.Items {
		if somedayProject.Items[i].UUID == "heading-someday" {
			somedayHeading = &somedayProject.Items[i]
			break
		}
	}
	if somedayHeading == nil {
		t.Fatalf("expected heading-someday to be included in project items")
	}
	if !taskExists(somedayHeading.Items, "todo-heading-someday") {
		t.Fatalf("expected heading-based todo to exist under heading items")
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

func TestTrashProjectIncludesTrashedChildItems(t *testing.T) {
	repo := openMutatedFixtureRepo(t, func(db *sql.DB) error {
		if _, err := db.Exec(`
INSERT INTO TMTask (uuid, type, trashed, title, status, start, creationDate, userModificationDate, "index", todayIndex, rt1_recurrenceRule)
VALUES ('project-trash-parent', 1, 1, 'Trashed Project', 0, 1, strftime('%s','now','-2 day'), strftime('%s','now','-1 day'), 1000, 0, NULL)
`); err != nil {
			return err
		}
		_, err := db.Exec(`
INSERT INTO TMTask (uuid, type, trashed, title, status, project, start, creationDate, userModificationDate, "index", todayIndex, rt1_recurrenceRule)
VALUES ('todo-trash-child', 0, 1, 'Trashed Child', 0, 'project-trash-parent', 1, strftime('%s','now','-2 day'), strftime('%s','now','-1 day'), 1001, 0, NULL)
`)
		return err
	})

	tasks, err := repo.Trash()
	if err != nil {
		t.Fatal(err)
	}

	var project *Task
	for i := range tasks {
		if tasks[i].UUID == "project-trash-parent" {
			project = &tasks[i]
			break
		}
	}
	if project == nil {
		t.Fatalf("expected trashed project in trash view")
	}
	if !taskExists(project.Items, "todo-trash-child") {
		t.Fatalf("expected trashed child item in trashed project's items")
	}
}

func TestLogbookCompletedProjectIncludesCompletedChildItems(t *testing.T) {
	repo := openMutatedFixtureRepo(t, func(db *sql.DB) error {
		if _, err := db.Exec(`
INSERT INTO TMTask (uuid, type, trashed, title, status, start, stopDate, creationDate, userModificationDate, "index", todayIndex, rt1_recurrenceRule)
VALUES ('project-logbook-parent', 1, 0, 'Completed Project', 3, 1, strftime('%s','now','-1 day'), strftime('%s','now','-8 day'), strftime('%s','now','-1 day'), 1010, 0, NULL)
`); err != nil {
			return err
		}
		_, err := db.Exec(`
INSERT INTO TMTask (uuid, type, trashed, title, status, project, start, stopDate, creationDate, userModificationDate, "index", todayIndex, rt1_recurrenceRule)
VALUES ('todo-logbook-child', 0, 0, 'Completed Child', 3, 'project-logbook-parent', 1, strftime('%s','now','-1 day'), strftime('%s','now','-6 day'), strftime('%s','now','-1 day'), 1011, 0, NULL)
`)
		return err
	})

	tasks, err := repo.Logbook()
	if err != nil {
		t.Fatal(err)
	}

	var project *Task
	for i := range tasks {
		if tasks[i].UUID == "project-logbook-parent" {
			project = &tasks[i]
			break
		}
	}
	if project == nil {
		t.Fatalf("expected completed project in logbook view")
	}
	if !taskExists(project.Items, "todo-logbook-child") {
		t.Fatalf("expected completed child item in completed project's items")
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
