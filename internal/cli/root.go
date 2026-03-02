package cli

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"github.com/spf13/cobra"

	"github.com/lexyurk/things-skill/internal/format"
	"github.com/lexyurk/things-skill/internal/thingsdb"
	"github.com/lexyurk/things-skill/internal/thingsurl"
)

type app struct {
	dbPath string
	output string
	dryRun bool
}

func Execute() error {
	a := &app{}
	rootCmd := newRootCommand(a)
	return rootCmd.Execute()
}

func newRootCommand(a *app) *cobra.Command {
	rootCmd := &cobra.Command{
		Use:   "things",
		Short: "Things 3 CLI with MCP-style operations",
		Long:  "A Go CLI for Things 3 that mirrors the capabilities of the Things MCP server.",
	}

	rootCmd.PersistentFlags().StringVar(&a.dbPath, "db-path", "", "Path to Things SQLite database (defaults to THINGSDB/standard paths)")
	rootCmd.PersistentFlags().StringVar(&a.output, "format", "text", "Output format: text or json")
	rootCmd.PersistentFlags().BoolVar(&a.dryRun, "dry-run", false, "Print URL for write commands without executing")

	a.addReadCommands(rootCmd)
	a.addWriteCommands(rootCmd)

	return rootCmd
}

func (a *app) withRepository(run func(*thingsdb.Repository) error) error {
	repo, err := thingsdb.Open(a.dbPath)
	if err != nil {
		return err
	}
	defer repo.Close()
	return run(repo)
}

func (a *app) printResult(data any, text string) error {
	switch strings.ToLower(a.output) {
	case "text":
		fmt.Println(text)
		return nil
	case "json":
		encoded, err := json.MarshalIndent(data, "", "  ")
		if err != nil {
			return err
		}
		fmt.Println(string(encoded))
		return nil
	default:
		return errors.New("--format must be either text or json")
	}
}

func (a *app) executeURL(ctx context.Context, url string) error {
	if a.dryRun {
		fmt.Println(url)
		return nil
	}
	executor := thingsurl.DefaultExecutor{}
	return executor.Execute(ctx, url)
}

func (a *app) printTasks(tasks []thingsdb.Task) error {
	if strings.ToLower(a.output) == "json" {
		return a.printResult(tasks, "")
	}
	return a.printResult(tasks, format.RenderTasks(tasks))
}

func (a *app) printAreas(areas []thingsdb.Area) error {
	if strings.ToLower(a.output) == "json" {
		return a.printResult(areas, "")
	}
	return a.printResult(areas, format.RenderAreas(areas))
}

func (a *app) printTags(tags []thingsdb.Tag) error {
	if strings.ToLower(a.output) == "json" {
		return a.printResult(tags, "")
	}
	return a.printResult(tags, format.RenderTags(tags))
}
