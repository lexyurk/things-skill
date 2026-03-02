package cli

import (
	"context"
	"fmt"
	"strings"

	"github.com/spf13/cobra"

	"github.com/lexyurk/things-skill/internal/thingsdb"
	"github.com/lexyurk/things-skill/internal/thingsurl"
)

func (a *app) addWriteCommands(rootCmd *cobra.Command) {
	todoCmd := &cobra.Command{
		Use:   "todo",
		Short: "Create, update, or delete todos",
	}
	projectCmd := &cobra.Command{
		Use:   "project",
		Short: "Create, update, or delete projects",
	}

	a.addTodoWriteCommands(todoCmd)
	a.addProjectWriteCommands(projectCmd)
	rootCmd.AddCommand(todoCmd, projectCmd)

	var (
		showID    string
		showQuery string
		showTags  []string
	)
	showCmd := &cobra.Command{
		Use:   "show",
		Short: "Show a specific item or list in Things app",
		RunE: func(_ *cobra.Command, _ []string) error {
			if strings.TrimSpace(showID) == "" && strings.TrimSpace(showQuery) == "" {
				return fmt.Errorf("provide --id or --query")
			}
			url := thingsurl.ShowURL(showID, showQuery, showTags)
			if err := a.executeURL(context.Background(), url); err != nil {
				return err
			}
			return a.printResult(map[string]string{"url": url}, "Opened Things view")
		},
	}
	showCmd.Flags().StringVar(&showID, "id", "", "Item/list ID (inbox,today,upcoming,anytime,someday,logbook,...)")
	showCmd.Flags().StringVar(&showQuery, "query", "", "Quick-find query")
	showCmd.Flags().StringSliceVar(&showTags, "filter-tags", nil, "Filter tags")
	rootCmd.AddCommand(showCmd)

	var appSearchQuery string
	appSearchCmd := &cobra.Command{
		Use:   "app-search",
		Short: "Search for items in the Things app UI",
		RunE: func(_ *cobra.Command, _ []string) error {
			if err := requireFlag("query", appSearchQuery); err != nil {
				return err
			}
			url := thingsurl.SearchURL(appSearchQuery)
			if err := a.executeURL(context.Background(), url); err != nil {
				return err
			}
			return a.printResult(map[string]string{"url": url}, fmt.Sprintf("Searching for %q in Things", appSearchQuery))
		},
	}
	appSearchCmd.Flags().StringVar(&appSearchQuery, "query", "", "Search query")
	rootCmd.AddCommand(appSearchCmd)

	var (
		jsonData   string
		jsonReveal bool
	)
	jsonCmd := &cobra.Command{
		Use:   "json",
		Short: "Execute advanced Things URL JSON operations",
		RunE: func(cmd *cobra.Command, _ []string) error {
			if err := requireFlag("data", jsonData); err != nil {
				return err
			}
			return a.withRepository(func(repo *thingsdb.Repository) error {
				token, err := repo.AuthToken()
				if err != nil {
					return err
				}
				var reveal *bool
				if cmd.Flags().Changed("reveal") {
					reveal = &jsonReveal
				}
				url := thingsurl.JSONURL(jsonData, token, reveal)
				if err := a.executeURL(context.Background(), url); err != nil {
					return err
				}
				return a.printResult(map[string]string{"url": url}, "JSON command sent to Things")
			})
		},
	}
	jsonCmd.Flags().StringVar(&jsonData, "data", "", "JSON payload")
	jsonCmd.Flags().BoolVar(&jsonReveal, "reveal", false, "Reveal created/updated item")
	rootCmd.AddCommand(jsonCmd)
}

func (a *app) addTodoWriteCommands(todoCmd *cobra.Command) {
	var (
		addTitle     string
		addNotes     string
		addWhen      string
		addDeadline  string
		addTags      []string
		addChecklist []string
		addListID    string
		addListTitle string
		addHeading   string
		addHeadingID string
	)
	addCmd := &cobra.Command{
		Use:   "add",
		Short: "Create a new todo",
		RunE: func(_ *cobra.Command, _ []string) error {
			if err := requireFlag("title", addTitle); err != nil {
				return err
			}
			url := thingsurl.AddTodoURL(thingsurl.AddTodoInput{
				Title:          addTitle,
				Notes:          addNotes,
				When:           addWhen,
				Deadline:       addDeadline,
				Tags:           addTags,
				ChecklistItems: addChecklist,
				ListID:         addListID,
				ListTitle:      addListTitle,
				Heading:        addHeading,
				HeadingID:      addHeadingID,
			})
			if err := a.executeURL(context.Background(), url); err != nil {
				return err
			}
			return a.printResult(map[string]string{"url": url}, fmt.Sprintf("Created todo: %s", addTitle))
		},
	}
	addCmd.Flags().StringVar(&addTitle, "title", "", "Todo title")
	addCmd.Flags().StringVar(&addNotes, "notes", "", "Notes")
	addCmd.Flags().StringVar(&addWhen, "when", "", "When value (today,tomorrow,anytime,someday,YYYY-MM-DD,YYYY-MM-DD@HH:MM)")
	addCmd.Flags().StringVar(&addDeadline, "deadline", "", "Deadline YYYY-MM-DD")
	addCmd.Flags().StringSliceVar(&addTags, "tags", nil, "Tags")
	addCmd.Flags().StringSliceVar(&addChecklist, "checklist-items", nil, "Checklist item titles")
	addCmd.Flags().StringVar(&addListID, "list-id", "", "Project/area UUID")
	addCmd.Flags().StringVar(&addListTitle, "list", "", "Project/area title")
	addCmd.Flags().StringVar(&addHeading, "heading", "", "Heading title")
	addCmd.Flags().StringVar(&addHeadingID, "heading-id", "", "Heading UUID")
	todoCmd.AddCommand(addCmd)

	var (
		updateID        string
		updateTitle     string
		updateNotes     string
		updateWhen      string
		updateDeadline  string
		updateTags      []string
		updateCompleted bool
		updateCanceled  bool
		updateList      string
		updateListID    string
		updateHeading   string
		updateHeadingID string
	)
	updateCmd := &cobra.Command{
		Use:   "update",
		Short: "Update an existing todo",
		RunE: func(cmd *cobra.Command, _ []string) error {
			if err := requireFlag("id", updateID); err != nil {
				return err
			}
			return a.withRepository(func(repo *thingsdb.Repository) error {
				token, err := repo.AuthToken()
				if err != nil {
					return err
				}
				if token == "" {
					return fmt.Errorf("things URL auth token unavailable; enable Things URLs in app settings")
				}

				var completed *bool
				if cmd.Flags().Changed("completed") {
					completed = &updateCompleted
				}
				var canceled *bool
				if cmd.Flags().Changed("canceled") {
					canceled = &updateCanceled
				}

				url := thingsurl.UpdateTodoURL(thingsurl.UpdateTodoInput{
					ID:        updateID,
					AuthToken: token,
					Title:     updateTitle,
					Notes:     updateNotes,
					When:      updateWhen,
					Deadline:  updateDeadline,
					Tags:      updateTags,
					Completed: completed,
					Canceled:  canceled,
					List:      updateList,
					ListID:    updateListID,
					Heading:   updateHeading,
					HeadingID: updateHeadingID,
				})
				if err := a.executeURL(context.Background(), url); err != nil {
					return err
				}
				return a.printResult(map[string]string{"url": url}, fmt.Sprintf("Updated todo: %s", updateID))
			})
		},
	}
	updateCmd.Flags().StringVar(&updateID, "id", "", "Todo UUID")
	updateCmd.Flags().StringVar(&updateTitle, "title", "", "New title")
	updateCmd.Flags().StringVar(&updateNotes, "notes", "", "New notes")
	updateCmd.Flags().StringVar(&updateWhen, "when", "", "New when value")
	updateCmd.Flags().StringVar(&updateDeadline, "deadline", "", "New deadline")
	updateCmd.Flags().StringSliceVar(&updateTags, "tags", nil, "Replacement tags")
	updateCmd.Flags().BoolVar(&updateCompleted, "completed", false, "Set completed true/false")
	updateCmd.Flags().BoolVar(&updateCanceled, "canceled", false, "Set canceled true/false")
	updateCmd.Flags().StringVar(&updateList, "list", "", "Move to list title")
	updateCmd.Flags().StringVar(&updateListID, "list-id", "", "Move to list UUID")
	updateCmd.Flags().StringVar(&updateHeading, "heading", "", "Move to heading title")
	updateCmd.Flags().StringVar(&updateHeadingID, "heading-id", "", "Move to heading UUID")
	todoCmd.AddCommand(updateCmd)

	var deleteID string
	deleteCmd := &cobra.Command{
		Use:   "delete",
		Short: "Delete todo (soft-delete: marks canceled)",
		RunE: func(_ *cobra.Command, _ []string) error {
			if err := requireFlag("id", deleteID); err != nil {
				return err
			}
			return a.withRepository(func(repo *thingsdb.Repository) error {
				token, err := repo.AuthToken()
				if err != nil {
					return err
				}
				if token == "" {
					return fmt.Errorf("things URL auth token unavailable; enable Things URLs in app settings")
				}
				canceled := true
				url := thingsurl.UpdateTodoURL(thingsurl.UpdateTodoInput{
					ID:        deleteID,
					AuthToken: token,
					Canceled:  &canceled,
				})
				if err := a.executeURL(context.Background(), url); err != nil {
					return err
				}
				return a.printResult(map[string]string{"url": url}, fmt.Sprintf("Todo %s canceled (Things soft delete)", deleteID))
			})
		},
	}
	deleteCmd.Flags().StringVar(&deleteID, "id", "", "Todo UUID")
	todoCmd.AddCommand(deleteCmd)
}

func (a *app) addProjectWriteCommands(projectCmd *cobra.Command) {
	var (
		addTitle    string
		addNotes    string
		addWhen     string
		addDeadline string
		addTags     []string
		addAreaID   string
		addArea     string
		addTodos    []string
	)
	addCmd := &cobra.Command{
		Use:   "add",
		Short: "Create a new project",
		RunE: func(_ *cobra.Command, _ []string) error {
			if err := requireFlag("title", addTitle); err != nil {
				return err
			}
			url := thingsurl.AddProjectURL(thingsurl.AddProjectInput{
				Title:     addTitle,
				Notes:     addNotes,
				When:      addWhen,
				Deadline:  addDeadline,
				Tags:      addTags,
				AreaID:    addAreaID,
				AreaTitle: addArea,
				Todos:     addTodos,
			})
			if err := a.executeURL(context.Background(), url); err != nil {
				return err
			}
			return a.printResult(map[string]string{"url": url}, fmt.Sprintf("Created project: %s", addTitle))
		},
	}
	addCmd.Flags().StringVar(&addTitle, "title", "", "Project title")
	addCmd.Flags().StringVar(&addNotes, "notes", "", "Project notes")
	addCmd.Flags().StringVar(&addWhen, "when", "", "When value")
	addCmd.Flags().StringVar(&addDeadline, "deadline", "", "Deadline")
	addCmd.Flags().StringSliceVar(&addTags, "tags", nil, "Tags")
	addCmd.Flags().StringVar(&addAreaID, "area-id", "", "Area UUID")
	addCmd.Flags().StringVar(&addArea, "area", "", "Area title")
	addCmd.Flags().StringSliceVar(&addTodos, "to-dos", nil, "Initial todo titles")
	projectCmd.AddCommand(addCmd)

	var (
		updateID        string
		updateTitle     string
		updateNotes     string
		updateWhen      string
		updateDeadline  string
		updateTags      []string
		updateCompleted bool
		updateCanceled  bool
	)
	updateCmd := &cobra.Command{
		Use:   "update",
		Short: "Update an existing project",
		RunE: func(cmd *cobra.Command, _ []string) error {
			if err := requireFlag("id", updateID); err != nil {
				return err
			}
			return a.withRepository(func(repo *thingsdb.Repository) error {
				token, err := repo.AuthToken()
				if err != nil {
					return err
				}
				if token == "" {
					return fmt.Errorf("things URL auth token unavailable; enable Things URLs in app settings")
				}

				var completed *bool
				if cmd.Flags().Changed("completed") {
					completed = &updateCompleted
				}
				var canceled *bool
				if cmd.Flags().Changed("canceled") {
					canceled = &updateCanceled
				}

				url := thingsurl.UpdateProjectURL(thingsurl.UpdateProjectInput{
					ID:        updateID,
					AuthToken: token,
					Title:     updateTitle,
					Notes:     updateNotes,
					When:      updateWhen,
					Deadline:  updateDeadline,
					Tags:      updateTags,
					Completed: completed,
					Canceled:  canceled,
				})
				if err := a.executeURL(context.Background(), url); err != nil {
					return err
				}
				return a.printResult(map[string]string{"url": url}, fmt.Sprintf("Updated project: %s", updateID))
			})
		},
	}
	updateCmd.Flags().StringVar(&updateID, "id", "", "Project UUID")
	updateCmd.Flags().StringVar(&updateTitle, "title", "", "New title")
	updateCmd.Flags().StringVar(&updateNotes, "notes", "", "New notes")
	updateCmd.Flags().StringVar(&updateWhen, "when", "", "New when value")
	updateCmd.Flags().StringVar(&updateDeadline, "deadline", "", "New deadline")
	updateCmd.Flags().StringSliceVar(&updateTags, "tags", nil, "Replacement tags")
	updateCmd.Flags().BoolVar(&updateCompleted, "completed", false, "Set completed true/false")
	updateCmd.Flags().BoolVar(&updateCanceled, "canceled", false, "Set canceled true/false")
	projectCmd.AddCommand(updateCmd)

	var deleteID string
	deleteCmd := &cobra.Command{
		Use:   "delete",
		Short: "Delete project (soft-delete: marks canceled)",
		RunE: func(_ *cobra.Command, _ []string) error {
			if err := requireFlag("id", deleteID); err != nil {
				return err
			}
			return a.withRepository(func(repo *thingsdb.Repository) error {
				token, err := repo.AuthToken()
				if err != nil {
					return err
				}
				if token == "" {
					return fmt.Errorf("things URL auth token unavailable; enable Things URLs in app settings")
				}
				canceled := true
				url := thingsurl.UpdateProjectURL(thingsurl.UpdateProjectInput{
					ID:        deleteID,
					AuthToken: token,
					Canceled:  &canceled,
				})
				if err := a.executeURL(context.Background(), url); err != nil {
					return err
				}
				return a.printResult(map[string]string{"url": url}, fmt.Sprintf("Project %s canceled (Things soft delete)", deleteID))
			})
		},
	}
	deleteCmd.Flags().StringVar(&deleteID, "id", "", "Project UUID")
	projectCmd.AddCommand(deleteCmd)
}
