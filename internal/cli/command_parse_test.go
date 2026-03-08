package cli

import "testing"

func TestCommandTreeHasCoreCommands(t *testing.T) {
	a := &app{}
	root := newRootCommand(a)

	expected := []string{
		"list",
		"todos",
		"projects",
		"areas",
		"tags",
		"search",
		"search-advanced",
		"recent",
		"todo",
		"project",
		"show",
		"app-search",
		"json",
	}
	for _, command := range expected {
		if _, _, err := root.Find([]string{command}); err != nil {
			t.Fatalf("expected command %q in tree: %v", command, err)
		}
	}
}

func TestTodoAddDryRun(t *testing.T) {
	a := &app{}
	root := newRootCommand(a)
	root.SetArgs([]string{"--dry-run", "todo", "add", "--title", "Test Todo"})
	if err := root.Execute(); err != nil {
		t.Fatalf("expected dry-run todo add to succeed: %v", err)
	}
}

func TestTodoDeleteRequiresID(t *testing.T) {
	a := &app{}
	root := newRootCommand(a)
	root.SetArgs([]string{"todo", "delete"})
	if err := root.Execute(); err == nil {
		t.Fatal("expected missing id error")
	}
}
