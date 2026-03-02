package cli

import (
	"fmt"
	"strings"

	"github.com/spf13/cobra"

	"github.com/lexyurk/things-skill/internal/thingsdb"
)

func (a *app) addReadCommands(rootCmd *cobra.Command) {
	var (
		logbookPeriod string
		logbookLimit  int
	)

	listCmd := &cobra.Command{
		Use:   "list [inbox|today|upcoming|anytime|someday|logbook|trash]",
		Short: "List items from a Things view (defaults to inbox)",
		Args:  cobra.MaximumNArgs(1),
		RunE: func(_ *cobra.Command, args []string) error {
			view := "inbox"
			if len(args) == 1 {
				view = strings.ToLower(args[0])
			}
			return a.withRepository(func(repo *thingsdb.Repository) error {
				tasks, err := repo.ListView(view, logbookPeriod, logbookLimit)
				if err != nil {
					return err
				}
				return a.printTasks(tasks)
			})
		},
	}
	listCmd.Flags().StringVar(&logbookPeriod, "period", "", "Logbook period filter (e.g. 7d, 1w)")
	listCmd.Flags().IntVar(&logbookLimit, "limit", 50, "Logbook max item count")
	rootCmd.AddCommand(listCmd)

	var (
		todosProjectUUID string
		todosHeadingUUID string
		todosInclude     bool
	)
	todosCmd := &cobra.Command{
		Use:   "todos",
		Short: "Get todos, optionally filtered by project",
		RunE: func(_ *cobra.Command, _ []string) error {
			return a.withRepository(func(repo *thingsdb.Repository) error {
				tasks, err := repo.Todos(todosProjectUUID, todosInclude, todosHeadingUUID)
				if err != nil {
					return err
				}
				if len(tasks) == 0 {
					return a.printResult(tasks, "No todos found")
				}
				return a.printTasks(tasks)
			})
		},
	}
	todosCmd.Flags().StringVar(&todosProjectUUID, "project", "", "Project UUID filter")
	todosCmd.Flags().StringVar(&todosHeadingUUID, "heading", "", "Heading UUID filter")
	todosCmd.Flags().BoolVar(&todosInclude, "include-items", true, "Include checklist items")
	rootCmd.AddCommand(todosCmd)

	var projectsInclude bool
	projectsCmd := &cobra.Command{
		Use:   "projects",
		Short: "Get all projects",
		RunE: func(_ *cobra.Command, _ []string) error {
			return a.withRepository(func(repo *thingsdb.Repository) error {
				projects, err := repo.Projects(projectsInclude)
				if err != nil {
					return err
				}
				if len(projects) == 0 {
					return a.printResult(projects, "No projects found")
				}
				return a.printTasks(projects)
			})
		},
	}
	projectsCmd.Flags().BoolVar(&projectsInclude, "include-items", false, "Include tasks inside each project")
	rootCmd.AddCommand(projectsCmd)

	var areasInclude bool
	areasCmd := &cobra.Command{
		Use:   "areas",
		Short: "Get all areas",
		RunE: func(_ *cobra.Command, _ []string) error {
			return a.withRepository(func(repo *thingsdb.Repository) error {
				areas, err := repo.Areas(areasInclude)
				if err != nil {
					return err
				}
				return a.printAreas(areas)
			})
		},
	}
	areasCmd.Flags().BoolVar(&areasInclude, "include-items", false, "Include items in each area")
	rootCmd.AddCommand(areasCmd)

	var tagsInclude bool
	tagsCmd := &cobra.Command{
		Use:   "tags",
		Short: "Get all tags",
		RunE: func(_ *cobra.Command, _ []string) error {
			return a.withRepository(func(repo *thingsdb.Repository) error {
				tags, err := repo.Tags(tagsInclude)
				if err != nil {
					return err
				}
				return a.printTags(tags)
			})
		},
	}
	tagsCmd.Flags().BoolVar(&tagsInclude, "include-items", false, "Include tagged items")
	rootCmd.AddCommand(tagsCmd)

	var taggedTag string
	taggedCmd := &cobra.Command{
		Use:   "tagged",
		Short: "Get items with a specific tag",
		RunE: func(_ *cobra.Command, _ []string) error {
			if err := requireFlag("tag", taggedTag); err != nil {
				return err
			}
			return a.withRepository(func(repo *thingsdb.Repository) error {
				tasks, err := repo.TaggedItems(taggedTag)
				if err != nil {
					return err
				}
				if len(tasks) == 0 {
					return a.printResult(tasks, fmt.Sprintf("No items found with tag %q", taggedTag))
				}
				return a.printTasks(tasks)
			})
		},
	}
	taggedCmd.Flags().StringVar(&taggedTag, "tag", "", "Tag title")
	rootCmd.AddCommand(taggedCmd)

	var headingsProject string
	headingsCmd := &cobra.Command{
		Use:   "headings",
		Short: "Get headings",
		RunE: func(_ *cobra.Command, _ []string) error {
			return a.withRepository(func(repo *thingsdb.Repository) error {
				headings, err := repo.Headings(headingsProject)
				if err != nil {
					return err
				}
				if len(headings) == 0 {
					return a.printResult(headings, "No headings found")
				}
				return a.printTasks(headings)
			})
		},
	}
	headingsCmd.Flags().StringVar(&headingsProject, "project", "", "Project UUID")
	rootCmd.AddCommand(headingsCmd)

	var searchQuery string
	searchCmd := &cobra.Command{
		Use:   "search",
		Short: "Search todos by title/notes",
		RunE: func(_ *cobra.Command, _ []string) error {
			if err := requireFlag("query", searchQuery); err != nil {
				return err
			}
			return a.withRepository(func(repo *thingsdb.Repository) error {
				tasks, err := repo.Search(searchQuery)
				if err != nil {
					return err
				}
				if len(tasks) == 0 {
					return a.printResult(tasks, fmt.Sprintf("No todos found matching %q", searchQuery))
				}
				return a.printTasks(tasks)
			})
		},
	}
	searchCmd.Flags().StringVar(&searchQuery, "query", "", "Search query")
	rootCmd.AddCommand(searchCmd)

	var advanced thingsdb.SearchAdvancedFilter
	searchAdvancedCmd := &cobra.Command{
		Use:   "search-advanced",
		Short: "Search with advanced Things filters",
		RunE: func(_ *cobra.Command, _ []string) error {
			return a.withRepository(func(repo *thingsdb.Repository) error {
				tasks, err := repo.SearchAdvanced(advanced)
				if err != nil {
					return err
				}
				if len(tasks) == 0 {
					return a.printResult(tasks, "No matching todos found")
				}
				return a.printTasks(tasks)
			})
		},
	}
	searchAdvancedCmd.Flags().StringVar(&advanced.Status, "status", "", "Status: incomplete|completed|canceled")
	searchAdvancedCmd.Flags().StringVar(&advanced.StartDate, "start-date", "", "Start date filter: true|false|past|future|YYYY-MM-DD")
	searchAdvancedCmd.Flags().StringVar(&advanced.Deadline, "deadline", "", "Deadline filter: true|false|past|future|YYYY-MM-DD")
	searchAdvancedCmd.Flags().StringVar(&advanced.Tag, "tag", "", "Tag title")
	searchAdvancedCmd.Flags().StringVar(&advanced.Area, "area", "", "Area UUID")
	searchAdvancedCmd.Flags().StringVar(&advanced.Type, "type", "", "Type: to-do|project|heading")
	searchAdvancedCmd.Flags().StringVar(&advanced.Last, "last", "", "Created in last period (e.g. 3d, 1w, 2m, 1y)")
	rootCmd.AddCommand(searchAdvancedCmd)

	var recentPeriod string
	recentCmd := &cobra.Command{
		Use:   "recent",
		Short: "Get recently created items",
		RunE: func(_ *cobra.Command, _ []string) error {
			if err := requireFlag("period", recentPeriod); err != nil {
				return err
			}
			return a.withRepository(func(repo *thingsdb.Repository) error {
				tasks, err := repo.Recent(recentPeriod)
				if err != nil {
					return err
				}
				if len(tasks) == 0 {
					return a.printResult(tasks, fmt.Sprintf("No items found in the last %s", recentPeriod))
				}
				return a.printTasks(tasks)
			})
		},
	}
	recentCmd.Flags().StringVar(&recentPeriod, "period", "", "Time period (e.g. 3d, 1w, 2m, 1y)")
	rootCmd.AddCommand(recentCmd)
}
