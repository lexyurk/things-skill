package format

import (
	"fmt"
	"strings"

	"github.com/lexyurk/things-skill/internal/thingsdb"
)

func RenderTasks(tasks []thingsdb.Task) string {
	if len(tasks) == 0 {
		return "No items found"
	}
	parts := make([]string, 0, len(tasks))
	for _, task := range tasks {
		var b strings.Builder
		fmt.Fprintf(&b, "Title: %s\n", task.Title)
		fmt.Fprintf(&b, "UUID: %s\n", task.UUID)
		fmt.Fprintf(&b, "Type: %s\n", task.Type)
		if task.Status != "" {
			fmt.Fprintf(&b, "Status: %s\n", task.Status)
		}
		if task.Start != "" {
			fmt.Fprintf(&b, "List: %s\n", task.Start)
		}
		if task.StartDate != "" {
			fmt.Fprintf(&b, "Start Date: %s\n", task.StartDate)
		}
		if task.Deadline != "" {
			fmt.Fprintf(&b, "Deadline: %s\n", task.Deadline)
		}
		if task.StopDate != "" {
			fmt.Fprintf(&b, "Completed: %s\n", task.StopDate)
		}
		if task.Created != "" {
			fmt.Fprintf(&b, "Created: %s\n", task.Created)
		}
		if task.Modified != "" {
			fmt.Fprintf(&b, "Modified: %s\n", task.Modified)
		}
		if task.Notes != "" {
			fmt.Fprintf(&b, "Notes: %s\n", task.Notes)
		}
		if task.ProjectName != "" {
			fmt.Fprintf(&b, "Project: %s\n", task.ProjectName)
		}
		if task.HeadingName != "" {
			fmt.Fprintf(&b, "Heading: %s\n", task.HeadingName)
		}
		if task.AreaTitle != "" {
			fmt.Fprintf(&b, "Area: %s\n", task.AreaTitle)
		}
		if len(task.Tags) > 0 {
			fmt.Fprintf(&b, "Tags: %s\n", strings.Join(task.Tags, ", "))
		}
		if len(task.Checklist) > 0 {
			b.WriteString("Checklist:\n")
			for _, item := range task.Checklist {
				marker := "☐"
				if item.Status == "completed" {
					marker = "✓"
				}
				fmt.Fprintf(&b, "  %s %s\n", marker, item.Title)
			}
		}
		if len(task.Items) > 0 {
			b.WriteString("Items:\n")
			for _, item := range task.Items {
				fmt.Fprintf(&b, "  - %s (%s)\n", item.Title, item.Type)
			}
		}
		parts = append(parts, strings.TrimSpace(b.String()))
	}
	return strings.Join(parts, "\n\n---\n\n")
}

func RenderAreas(areas []thingsdb.Area) string {
	if len(areas) == 0 {
		return "No areas found"
	}
	parts := make([]string, 0, len(areas))
	for _, area := range areas {
		var b strings.Builder
		fmt.Fprintf(&b, "Title: %s\n", area.Title)
		fmt.Fprintf(&b, "UUID: %s\n", area.UUID)
		if len(area.Tags) > 0 {
			fmt.Fprintf(&b, "Tags: %s\n", strings.Join(area.Tags, ", "))
		}
		if len(area.Items) > 0 {
			b.WriteString("Items:\n")
			for _, item := range area.Items {
				fmt.Fprintf(&b, "  - %s (%s)\n", item.Title, item.Type)
			}
		}
		parts = append(parts, strings.TrimSpace(b.String()))
	}
	return strings.Join(parts, "\n\n---\n\n")
}

func RenderTags(tags []thingsdb.Tag) string {
	if len(tags) == 0 {
		return "No tags found"
	}
	parts := make([]string, 0, len(tags))
	for _, tag := range tags {
		var b strings.Builder
		fmt.Fprintf(&b, "Title: %s\n", tag.Title)
		fmt.Fprintf(&b, "UUID: %s\n", tag.UUID)
		if tag.Shortcut != "" {
			fmt.Fprintf(&b, "Shortcut: %s\n", tag.Shortcut)
		}
		if len(tag.Items) > 0 {
			b.WriteString("Tagged Items:\n")
			for _, item := range tag.Items {
				fmt.Fprintf(&b, "  - %s (%s)\n", item.Title, item.Type)
			}
		}
		parts = append(parts, strings.TrimSpace(b.String()))
	}
	return strings.Join(parts, "\n\n---\n\n")
}
